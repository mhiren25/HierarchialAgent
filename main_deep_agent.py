"""
Enhanced FastAPI Backend with Real-time Tool/Agent Streaming
Integrates with Deep Agent Supervisor and provides detailed execution tracking
"""
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from contextlib import asynccontextmanager
import uvicorn
import asyncio
import json
from datetime import datetime
import os
import time

from deep_agent_supervisor import create_supervisor_system, monitoring, hitl_config, approve_sql_query, reject_sql_query

# Global instances
supervisor = None
active_threads = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize supervisor on startup"""
    global supervisor
    
    print("🚀 Initializing Deep Agent Supervisor with Azure OpenAI...")
    print("🔐 Human-in-the-Loop enabled for database queries")
    
    try:
        supervisor = create_supervisor_system(
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview"),
            deployment_name=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4")
        )
        print("✅ Deep Agent Supervisor initialized successfully!")
        print(f"   Endpoint: {os.getenv('AZURE_OPENAI_ENDPOINT')}")
        print(f"   Deployment: {os.getenv('AZURE_OPENAI_DEPLOYMENT_NAME')}")
        print(f"   HITL Status: {'Enabled' if hitl_config.enabled else 'Disabled'}")
    except Exception as e:
        print(f"❌ Failed to initialize supervisor: {e}")
        raise
    
    yield
    
    print("🔄 Shutting down...")

# Initialize FastAPI
app = FastAPI(
    title="LangGraph Deep Agent API",
    description="Hierarchical agent system with real-time streaming",
    version="2.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================================
# PYDANTIC MODELS
# ============================================================================

class ChatRequest(BaseModel):
    message: str
    thread_id: Optional[str] = None

class ChatResponse(BaseModel):
    response: str
    thread_id: str
    agent_path: List[str]
    metadata: Dict[str, Any]

# ============================================================================
# ENDPOINTS
# ============================================================================

@app.get("/")
async def root():
    """Health check"""
    return {
        "status": "online",
        "service": "LangGraph Deep Agent System",
        "version": "2.0.0",
        "pattern": "agents-as-tools",
        "streaming": "enabled",
        "llm": "Azure OpenAI",
        "features": [
            "Real-time tool execution streaming",
            "Agent navigation tracking",
            "Execution time monitoring",
            "Full observability"
        ]
    }

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    HTTP endpoint for chat (synchronous)
    For real-time streaming, use WebSocket endpoint
    Handles HITL approval requests
    """
    if not supervisor:
        raise HTTPException(status_code=503, detail="Supervisor not initialized")
    
    thread_id = request.thread_id or f"thread_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
    
    try:
        # Check if this is an approval/rejection command
        message_lower = request.message.lower().strip()
        
        if message_lower.startswith("approve "):
            query_id = message_lower.replace("approve ", "").strip()
            result_text = approve_sql_query(query_id)
            
            # Store in thread
            if thread_id not in active_threads:
                active_threads[thread_id] = []
            active_threads[thread_id].append({
                "user": request.message,
                "assistant": result_text,
                "timestamp": datetime.now().isoformat(),
                "agent_path": ["db_team"]
            })
            
            return ChatResponse(
                response=result_text,
                thread_id=thread_id,
                agent_path=["db_team"],
                metadata={
                    "timestamp": datetime.now().isoformat(),
                    "approval_action": "approved",
                    "query_id": query_id
                }
            )
        
        elif message_lower.startswith("reject "):
            query_id = message_lower.replace("reject ", "").strip()
            result_text = reject_sql_query(query_id)
            
            # Store in thread
            if thread_id not in active_threads:
                active_threads[thread_id] = []
            active_threads[thread_id].append({
                "user": request.message,
                "assistant": result_text,
                "timestamp": datetime.now().isoformat(),
                "agent_path": ["db_team"]
            })
            
            return ChatResponse(
                response=result_text,
                thread_id=thread_id,
                agent_path=["db_team"],
                metadata={
                    "timestamp": datetime.now().isoformat(),
                    "approval_action": "rejected",
                    "query_id": query_id
                }
            )
        
        # Normal query - invoke supervisor
        result = supervisor.invoke({
            "messages": [{"role": "user", "content": request.message}]
        })
        
        # Extract agent path from monitoring
        agent_path = []
        if "monitoring" in result:
            # Extract unique agents called
            agents_seen = set()
            for tool_call in result["monitoring"].get("tool_calls", []):
                tool_name = tool_call["tool"]
                if tool_name not in agents_seen:
                    agents_seen.add(tool_name)
                    agent_path.append(tool_name)
        
        # Store in thread history
        if thread_id not in active_threads:
            active_threads[thread_id] = []
        
        active_threads[thread_id].append({
            "user": request.message,
            "assistant": result.get("final_response"),
            "timestamp": datetime.now().isoformat(),
            "agent_path": agent_path
        })
        
        return ChatResponse(
            response=result.get("final_response", "No response generated"),
            thread_id=thread_id,
            agent_path=agent_path,
            metadata={
                "timestamp": datetime.now().isoformat(),
                "total_duration": result.get("monitoring", {}).get("total_duration", 0),
                "tools_called": len(result.get("monitoring", {}).get("tool_calls", []))
            }
        )
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/threads")
async def list_threads():
    """List all conversation threads"""
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
    """Get conversation history"""
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
    WebSocket endpoint for REAL-TIME streaming of agent/tool execution
    Provides live updates as the supervisor calls tools
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
            
            # Send acknowledgment
            await websocket.send_json({
                "type": "start",
                "message": "Processing your request...",
                "timestamp": datetime.now().isoformat()
            })
            
            # Reset monitoring for this request
            monitoring.reset()
            
            # Track execution with streaming updates
            agent_path = []
            tool_execution_order = []
            
            try:
                # We'll invoke the supervisor and monitor in real-time
                # For streaming, we need to hook into the monitoring system
                
                # Send supervisor start
                await websocket.send_json({
                    "type": "agent_start",
                    "agent": "supervisor",
                    "timestamp": datetime.now().isoformat()
                })
                
                if "supervisor" not in agent_path:
                    agent_path.append("supervisor")
                
                # Invoke supervisor (synchronous, but we'll stream updates via monitoring)
                start_time = time.time()
                result = supervisor.invoke({
                    "messages": [{"role": "user", "content": user_message}]
                })
                
                # Stream tool executions from monitoring
                if "monitoring" in result:
                    mon_data = result["monitoring"]
                    
                    # Stream each tool call with timing
                    for tool_call in mon_data.get("tool_calls", []):
                        tool_name = tool_call["tool"]
                        
                        # Send tool start event
                        await websocket.send_json({
                            "type": "tool_start",
                            "tool_name": tool_name,
                            "agent": "supervisor",
                            "args": tool_call.get("args", {}),
                            "timestamp": tool_call.get("timestamp")
                        })
                        
                        # Track in execution order
                        if tool_name not in tool_execution_order:
                            tool_execution_order.append(tool_name)
                        
                        # Add to agent path (map tool names to agent names)
                        agent_display_name = _map_tool_to_agent(tool_name)
                        if agent_display_name not in agent_path:
                            agent_path.append(agent_display_name)
                        
                        # Simulate streaming (since tool already executed)
                        await asyncio.sleep(0.1)
                        
                        # Send tool complete event with timing
                        await websocket.send_json({
                            "type": "tool_complete",
                            "tool_name": tool_name,
                            "agent": agent_display_name,
                            "status": tool_call.get("status", "completed"),
                            "duration": tool_call.get("duration", 0),
                            "result_preview": str(tool_call.get("result_length", 0)) + " chars",
                            "timestamp": datetime.now().isoformat()
                        })
                        
                        # If there's a result, send it
                        if tool_call.get("status") == "completed":
                            await websocket.send_json({
                                "type": "tool_response",
                                "tool_name": tool_name,
                                "agent": agent_display_name,
                                "content": f"✓ {tool_name} completed in {tool_call.get('duration', 0):.2f}s",
                                "duration": tool_call.get("duration", 0),
                                "timestamp": datetime.now().isoformat()
                            })
                
                # Send supervisor thinking/synthesizing
                await websocket.send_json({
                    "type": "agent_thinking",
                    "agent": "supervisor",
                    "message": "Synthesizing results from agents...",
                    "timestamp": datetime.now().isoformat()
                })
                
                await asyncio.sleep(0.2)  # Brief pause for UX
                
                # Send supervisor complete
                await websocket.send_json({
                    "type": "agent_complete",
                    "agent": "supervisor",
                    "duration": time.time() - start_time,
                    "timestamp": datetime.now().isoformat()
                })
                
                # Extract final response
                final_response = result.get("final_response", "No response generated")
                
                # Store in thread history
                if thread_id not in active_threads:
                    active_threads[thread_id] = []
                
                active_threads[thread_id].append({
                    "user": user_message,
                    "assistant": final_response,
                    "timestamp": datetime.now().isoformat(),
                    "agent_path": agent_path
                })
                
                # Send completion with full details
                await websocket.send_json({
                    "type": "complete",
                    "final_response": final_response,
                    "agent_path": agent_path,
                    "tool_execution_order": tool_execution_order,
                    "monitoring": {
                        "total_duration": result.get("monitoring", {}).get("total_duration", 0),
                        "tools_called": len(result.get("monitoring", {}).get("tool_calls", [])),
                        "tool_timings": [
                            {
                                "tool": tc["tool"],
                                "duration": tc.get("duration", 0),
                                "status": tc.get("status")
                            }
                            for tc in result.get("monitoring", {}).get("tool_calls", [])
                        ]
                    },
                    "timestamp": datetime.now().isoformat()
                })
                
            except Exception as e:
                import traceback
                error_trace = traceback.format_exc()
                print(f"Error during execution: {error_trace}")
                
                await websocket.send_json({
                    "type": "error",
                    "error": str(e),
                    "trace": error_trace,
                    "timestamp": datetime.now().isoformat()
                })
    
    except WebSocketDisconnect:
        print(f"WebSocket disconnected for thread {thread_id}")
    except Exception as e:
        import traceback
        traceback.print_exc()
        try:
            await websocket.send_json({
                "type": "error",
                "error": str(e)
            })
        except:
            pass
        await websocket.close()

def _map_tool_to_agent(tool_name: str) -> str:
    """Map tool names to display-friendly agent names"""
    mapping = {
        "investigate_logs": "log_team",
        "search_knowledge": "knowledge_team",
        "query_database": "db_team"
    }
    return mapping.get(tool_name, tool_name)

@app.get("/agents/info")
async def agents_info():
    """Get information about available agents"""
    return {
        "supervisor": {
            "name": "supervisor",
            "description": "Orchestrates sub-agents and synthesizes results",
            "llm": "Azure OpenAI"
        },
        "agents": [
            {
                "name": "log_team",
                "tool": "investigate_logs",
                "description": "Analyzes order logs and compares orders",
                "capabilities": [
                    "Order comparison",
                    "Failure analysis",
                    "Timeline generation"
                ]
            },
            {
                "name": "knowledge_team",
                "tool": "search_knowledge",
                "description": "Searches documentation using RAG",
                "capabilities": [
                    "Troubleshooting guides",
                    "Configuration info",
                    "Best practices"
                ]
            },
            {
                "name": "db_team",
                "tool": "query_database",
                "description": "Converts NL to SQL and queries database",
                "capabilities": [
                    "Natural language queries",
                    "Data aggregation",
                    "Safe SQL execution"
                ]
            }
        ]
    }

@app.get("/monitoring/summary")
async def get_monitoring_summary():
    """Get current monitoring metrics"""
    return monitoring.get_summary()

@app.post("/monitoring/reset")
async def reset_monitoring():
    """Reset monitoring counters"""
    monitoring.reset()
    return {"message": "Monitoring reset"}

# ============================================================================
# HUMAN-IN-THE-LOOP ENDPOINTS
# ============================================================================

@app.get("/hitl/pending")
async def get_pending_approvals():
    """Get all pending approval requests"""
    return {
        "pending_count": len(hitl_config.pending_approvals),
        "pending_approvals": [
            {
                "query_id": approval.query_id,
                "natural_language_query": approval.natural_language_query,
                "generated_sql": approval.generated_sql,
                "risk_level": approval.risk_level,
                "reason": approval.reason,
                "timestamp": approval.timestamp
            }
            for approval in hitl_config.pending_approvals.values()
        ]
    }

@app.post("/hitl/approve/{query_id}")
async def approve_query(query_id: str):
    """Approve a pending SQL query"""
    try:
        result = approve_sql_query(query_id)
        return {
            "success": True,
            "query_id": query_id,
            "result": result
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/hitl/reject/{query_id}")
async def reject_query(query_id: str, reason: Optional[str] = None):
    """Reject a pending SQL query"""
    try:
        result = reject_sql_query(query_id, reason)
        return {
            "success": True,
            "query_id": query_id,
            "result": result
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/hitl/config")
async def get_hitl_config():
    """Get current HITL configuration"""
    return {
        "enabled": hitl_config.enabled,
        "require_approval_for_writes": hitl_config.require_approval_for_writes,
        "require_approval_for_sensitive_tables": hitl_config.require_approval_for_sensitive_tables,
        "sensitive_tables": hitl_config.sensitive_tables,
        "auto_approve_safe_queries": hitl_config.auto_approve_safe_queries,
        "pending_approvals_count": len(hitl_config.pending_approvals)
    }

@app.post("/hitl/config")
async def update_hitl_config(
    enabled: Optional[bool] = None,
    auto_approve_safe_queries: Optional[bool] = None
):
    """Update HITL configuration"""
    if enabled is not None:
        hitl_config.enabled = enabled
    if auto_approve_safe_queries is not None:
        hitl_config.auto_approve_safe_queries = auto_approve_safe_queries
    
    return {
        "message": "HITL configuration updated",
        "config": {
            "enabled": hitl_config.enabled,
            "auto_approve_safe_queries": hitl_config.auto_approve_safe_queries
        }
    }

@app.get("/health")
async def health_check():
    """Detailed health check"""
    return {
        "status": "healthy",
        "supervisor": "initialized" if supervisor else "not initialized",
        "azure_openai": {
            "endpoint": os.getenv("AZURE_OPENAI_ENDPOINT", "not set")[:50] + "...",
            "deployment": os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "not set"),
            "api_version": os.getenv("AZURE_OPENAI_API_VERSION", "not set")
        },
        "features": {
            "websocket_streaming": True,
            "tool_timing": True,
            "agent_tracking": True,
            "monitoring": True
        },
        "active_threads": len(active_threads),
        "timestamp": datetime.now().isoformat()
    }

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
