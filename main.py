"""
FastAPI Backend with LangGraph Integration
"""
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import uvicorn
import asyncio
import json
from datetime import datetime
import os

from supervisor_agent import create_agent_system
from langchain_core.messages import HumanMessage, AIMessage

# Initialize FastAPI
app = FastAPI(title="Hierarchical LangGraph Agent API")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models
class ChatRequest(BaseModel):
    message: str
    thread_id: Optional[str] = None

class ChatResponse(BaseModel):
    response: str
    thread_id: str
    agent_path: List[str]
    metadata: Dict[str, Any]

# Global agent system
agent_system = None
active_threads = {}

def initialize_agent():
    """Initialize the LangGraph agent system"""
    global agent_system
    
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
        raise ValueError("OPENAI_API_KEY environment variable not set")
    
    agent_system = create_agent_system(
        openai_api_key=openai_api_key,
        model="gpt-4o-mini"
    )
    print("✅ Agent system initialized")

@app.on_event("startup")
async def startup_event():
    """Initialize agent on startup"""
    initialize_agent()

@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "online",
        "service": "Hierarchical LangGraph Agent",
        "version": "1.0.0"
    }

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Process chat messages through the hierarchical agent system
    """
    if not agent_system:
        raise HTTPException(status_code=503, detail="Agent system not initialized")
    
    # Generate thread ID if not provided
    thread_id = request.thread_id or f"thread_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
    
    try:
        # Prepare input
        config = {"configurable": {"thread_id": thread_id}}
        input_state = {
            "messages": [HumanMessage(content=request.message)]
        }
        
        # Track agent path and collect all outputs
        agent_path = []
        all_messages = []
        
        # Execute agent graph and collect ALL events
        for event in agent_system.stream(input_state, config, stream_mode="updates"):
            for node_name, node_output in event.items():
                if node_name not in agent_path:
                    agent_path.append(node_name)
                
                # Collect messages from each node
                if "messages" in node_output and node_output["messages"]:
                    for msg in node_output["messages"]:
                        if hasattr(msg, 'content') and msg.content:
                            all_messages.append(msg)
        
        # Get the final response - last AI message
        response_content = "No response generated"
        if all_messages:
            # Get the last message that has actual content
            for msg in reversed(all_messages):
                if hasattr(msg, 'content') and msg.content and len(msg.content.strip()) > 0:
                    response_content = msg.content
                    break
        
        # Store thread
        if thread_id not in active_threads:
            active_threads[thread_id] = []
        active_threads[thread_id].append({
            "user": request.message,
            "assistant": response_content,
            "timestamp": datetime.now().isoformat(),
            "agent_path": agent_path
        })
        
        return ChatResponse(
            response=response_content,
            thread_id=thread_id,
            agent_path=agent_path,
            metadata={
                "timestamp": datetime.now().isoformat(),
                "message_count": len(active_threads[thread_id])
            }
        )
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/threads")
async def list_threads():
    """List all active conversation threads"""
    return {
        "threads": [
            {
                "thread_id": tid,
                "message_count": len(messages),
                "last_activity": messages[-1]["timestamp"] if messages else None
            }
            for tid, messages in active_threads.items()
        ]
    }

@app.get("/threads/{thread_id}")
async def get_thread(thread_id: str):
    """Get conversation history for a specific thread"""
    if thread_id not in active_threads:
        raise HTTPException(status_code=404, detail="Thread not found")
    
    return {
        "thread_id": thread_id,
        "messages": active_threads[thread_id]
    }

@app.delete("/threads/{thread_id}")
async def delete_thread(thread_id: str):
    """Delete a conversation thread"""
    if thread_id in active_threads:
        del active_threads[thread_id]
        return {"message": f"Thread {thread_id} deleted"}
    raise HTTPException(status_code=404, detail="Thread not found")

@app.websocket("/ws/{thread_id}")
async def websocket_endpoint(websocket: WebSocket, thread_id: str):
    """
    WebSocket endpoint for streaming responses
    """
    await websocket.accept()
    
    try:
        while True:
            # Receive message
            data = await websocket.receive_text()
            message_data = json.loads(data)
            user_message = message_data.get("message", "")
            
            if not user_message:
                continue
            
            # Prepare input
            config = {"configurable": {"thread_id": thread_id}}
            input_state = {
                "messages": [HumanMessage(content=user_message)]
            }
            
            # Stream agent execution
            agent_path = []
            
            for event in agent_system.stream(input_state, config, stream_mode="updates"):
                for node_name, node_output in event.items():
                    agent_path.append(node_name)
                    
                    # Send intermediate updates
                    await websocket.send_json({
                        "type": "agent_update",
                        "agent": node_name,
                        "timestamp": datetime.now().isoformat()
                    })
                    
                    # Send message if available
                    if "messages" in node_output and node_output["messages"]:
                        last_msg = node_output["messages"][-1]
                        if hasattr(last_msg, 'content'):
                            await websocket.send_json({
                                "type": "message_chunk",
                                "content": last_msg.content,
                                "agent": node_name
                            })
            
            # Send completion
            await websocket.send_json({
                "type": "complete",
                "agent_path": agent_path,
                "timestamp": datetime.now().isoformat()
            })
            
    except WebSocketDisconnect:
        print(f"WebSocket disconnected for thread {thread_id}")
    except Exception as e:
        await websocket.send_json({
            "type": "error",
            "error": str(e)
        })
        await websocket.close()

# Debug endpoints
@app.get("/debug/agent-graph")
async def get_agent_graph():
    """Get agent graph structure for debugging"""
    if not agent_system:
        raise HTTPException(status_code=503, detail="Agent system not initialized")
    
    try:
        # Get graph structure
        graph_dict = agent_system.get_graph().to_json()
        return json.loads(graph_dict)
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    # For development
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
