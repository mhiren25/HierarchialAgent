"""
Hierarchical LangGraph Teams Agent - Using Official LangGraph Patterns
Based on LangGraph's multi-agent supervisor example
"""
from typing import Annotated, Literal, Sequence
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, END, START
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver
from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
import functools
import operator

# State definition
class AgentState(TypedDict):
    """The agent state with messages and next routing"""
    messages: Annotated[Sequence[BaseMessage], operator.add]
    next: str

# Supervisor system prompt
SUPERVISOR_PROMPT = """You are a supervisor managing three specialized agent teams:

1. **log_team**: Analyzes system logs, compares orders (good vs bad), identifies failures
   
2. **knowledge_team**: Retrieves information from RAG knowledge base
   
3. **db_team**: Converts natural language to SQL and queries database

Your job is to route the user's query to the appropriate team.

Routing guidelines:
- Order IDs (GOOD001, BAD001) or "compare orders" → log_team
- "show", "list", "count", "total", "statistics" → db_team  
- "what", "why", "explain", "how" → knowledge_team

Respond with ONLY: log_team, knowledge_team, db_team, or FINISH"""

def create_supervisor_node(llm: ChatOpenAI, members: list[str]):
    """
    Create a supervisor node that routes to different team members.
    """
    options = ["FINISH"] + members
    system_prompt = SUPERVISOR_PROMPT.format(options=", ".join(options))
    
    def supervisor_node(state: AgentState) -> dict:
        """Supervisor that routes to teams"""
        messages = state["messages"]
        
        # Get the last user message
        user_query = ""
        for msg in reversed(messages):
            if hasattr(msg, 'type') and msg.type == 'human':
                user_query = msg.content.lower()
                break
        
        if not user_query:
            return {"next": "FINISH"}
        
        # Count AI responses AFTER the last user message (this turn only)
        ai_count_this_turn = 0
        for msg in reversed(messages):
            if hasattr(msg, 'type'):
                if msg.type == 'human':
                    break  # Stop counting when we hit the user message
                if msg.type == 'ai':
                    ai_count_this_turn += 1
        
        # If we already got a response this turn, finish
        if ai_count_this_turn > 0:
            return {"next": "FINISH"}
        
        # Simple keyword-based routing
        import re
        
        # Check for order IDs
        has_order_ids = bool(re.search(r'\b[A-Z]+\d+\b', user_query))
        
        # Route based on keywords
        if has_order_ids or "compare" in user_query:
            return {"next": "log_team"}
        
        if any(word in user_query for word in ["show", "list", "count", "total", "all orders", "statistics", "revenue", "how many"]):
            return {"next": "db_team"}
        
        if any(word in user_query for word in ["what", "why", "explain", "how", "causes", "guide", "documentation"]):
            return {"next": "knowledge_team"}
        
        # Fallback: Ask LLM
        routing_prompt = f"{system_prompt}\n\nUser query: {user_query}\n\nWhich team?"
        response = llm.invoke([SystemMessage(content=routing_prompt)])
        
        content = response.content.strip().lower()
        
        if "log" in content:
            return {"next": "log_team"}
        elif "knowledge" in content:
            return {"next": "knowledge_team"}
        elif "db" in content or "database" in content:
            return {"next": "db_team"}
        else:
            return {"next": "FINISH"}
    
    return supervisor_node

def create_team_node(agent, name: str):
    """
    Create a node for a team agent.
    This wraps the agent execution and adds the agent name to messages.
    """
    def team_node(state: AgentState) -> dict:
        result = agent.invoke(state)
        
        # Tag the messages with the agent name
        if isinstance(result, dict) and "messages" in result:
            for msg in result["messages"]:
                msg.name = name
        
        return result
    
    return team_node

def create_hierarchical_graph(llm: ChatOpenAI):
    """
    Create the hierarchical supervisor graph using official LangGraph patterns.
    Based on: https://langchain-ai.github.io/langgraph/tutorials/multi_agent/agent_supervisor/
    """
    
    # Import team agents
    from log_team import create_log_agent
    from knowledge_team import create_knowledge_agent
    from db_team import create_db_agent
    
    # Create team agents
    log_agent = create_log_agent(llm)
    knowledge_agent = create_knowledge_agent(llm)
    db_agent = create_db_agent(llm)
    
    # Define team members
    members = ["log_team", "knowledge_team", "db_team"]
    
    # Create supervisor node
    supervisor_node = create_supervisor_node(llm, members)
    
    # Build the graph
    workflow = StateGraph(AgentState)
    
    # Add nodes
    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("log_team", create_team_node(log_agent, "log_team"))
    workflow.add_node("knowledge_team", create_team_node(knowledge_agent, "knowledge_team"))
    workflow.add_node("db_team", create_team_node(db_agent, "db_team"))
    
    # Add edges from teams back to supervisor
    for member in members:
        workflow.add_edge(member, "supervisor")
    
    # Add conditional edges from supervisor
    conditional_map = {member: member for member in members}
    conditional_map["FINISH"] = END
    
    workflow.add_conditional_edges(
        "supervisor",
        lambda x: x["next"],
        conditional_map
    )
    
    # Set entry point
    workflow.add_edge(START, "supervisor")
    
    # Add memory for conversation persistence
    memory = MemorySaver()
    
    return workflow.compile(checkpointer=memory)

def create_agent_system(openai_api_key: str, model: str = "gpt-4o-mini"):
    """
    Create and return the complete hierarchical agent system.
    
    This follows the official LangGraph multi-agent supervisor pattern:
    https://langchain-ai.github.io/langgraph/tutorials/multi_agent/agent_supervisor/
    
    Args:
        openai_api_key: OpenAI API key
        model: Model to use (default: gpt-4o-mini)
    
    Returns:
        Compiled LangGraph with supervisor and teams
    """
    llm = ChatOpenAI(
        api_key=openai_api_key,
        model=model,
        temperature=0
    )
    
    return create_hierarchical_graph(llm)

# Alternative: Hierarchical Teams Pattern
def create_hierarchical_teams_graph(llm: ChatOpenAI):
    """
    Alternative implementation using hierarchical teams.
    This is another official LangGraph pattern where teams can have sub-agents.
    
    Based on: https://langchain-ai.github.io/langgraph/tutorials/multi_agent/hierarchical_agent_teams/
    """
    from langgraph.graph import StateGraph
    
    # Import teams
    from log_team import create_log_agent
    from knowledge_team import create_knowledge_agent
    from db_team import create_db_agent
    
    # Create individual team graphs (these could have their own sub-agents)
    log_team_graph = create_log_agent(llm)
    knowledge_team_graph = create_knowledge_agent(llm)
    db_team_graph = create_db_agent(llm)
    
    # Create top-level supervisor
    members = ["log_team", "knowledge_team", "db_team"]
    supervisor_node = create_supervisor_node(llm, members)
    
    # Build hierarchical structure
    workflow = StateGraph(AgentState)
    
    # Add supervisor
    workflow.add_node("supervisor", supervisor_node)
    
    # Add team nodes (each could be a sub-graph)
    workflow.add_node("log_team", create_team_node(log_team_graph, "log_team"))
    workflow.add_node("knowledge_team", create_team_node(knowledge_team_graph, "knowledge_team"))
    workflow.add_node("db_team", create_team_node(db_team_graph, "db_team"))
    
    # Connect teams to supervisor
    for member in members:
        workflow.add_edge(member, "supervisor")
    
    # Supervisor conditional routing
    workflow.add_conditional_edges(
        "supervisor",
        lambda x: x["next"],
        {
            "log_team": "log_team",
            "knowledge_team": "knowledge_team", 
            "db_team": "db_team",
            "FINISH": END
        }
    )
    
    workflow.add_edge(START, "supervisor")
    
    return workflow.compile(checkpointer=MemorySaver())

"""
NOTES ON LANGGRAPH PATTERNS:

1. There is NO "langgraph_supervisor" package - that doesn't exist
2. The official patterns are:
   - Multi-Agent Supervisor: https://langchain-ai.github.io/langgraph/tutorials/multi_agent/agent_supervisor/
   - Hierarchical Teams: https://langchain-ai.github.io/langgraph/tutorials/multi_agent/hierarchical_agent_teams/

3. Key LangGraph concepts used here:
   - StateGraph: Main graph structure
   - create_react_agent: Creates agents with tools (from langgraph.prebuilt)
   - MemorySaver: Built-in checkpointing for conversation memory
   - Conditional edges: Route based on state
   - MessagesState / custom TypedDict: State management

4. This implementation follows the official examples from LangGraph documentation
"""
