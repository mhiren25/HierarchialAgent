"""
Deep Agent Supervisor System with Azure OpenAI
LangChain v1.0.2 compatible implementation
Implements agents-as-tools pattern with full monitoring and middleware
"""

import os
import time
from datetime import datetime
from typing import Annotated, Dict, Any, List, Optional, Literal, TypedDict
from pydantic import BaseModel, Field

# LangChain 1.0.2 imports
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import tool, BaseTool
from langchain_core.runnables import RunnableLambda, RunnablePassthrough, Runnable
from langchain_openai import AzureChatOpenAI

# ============================================================================
# MIDDLEWARE & MONITORING
# ============================================================================

class MonitoringMiddleware:
    """Middleware for tracking agent and tool executions with timing"""
    
    def __init__(self):
        self.reset()
    
    def reset(self):
        self.agent_executions = []
        self.tool_calls = []
        self.errors = []
        self.start_time = time.time()
    
    def track_agent_start(self, agent_name: str):
        """Track when an agent starts"""
        self.agent_executions.append({
            "agent": agent_name,
            "timestamp": datetime.now().isoformat(),
            "start_time": time.time()
        })
    
    def track_agent_complete(self, agent_name: str):
        """Track when an agent completes"""
        for exec_info in reversed(self.agent_executions):
            if exec_info["agent"] == agent_name and "end_time" not in exec_info:
                exec_info["end_time"] = time.time()
                exec_info["duration"] = exec_info["end_time"] - exec_info["start_time"]
                break
    
    def track_tool_call(self, tool_name: str, args: Dict):
        """Track tool invocation"""
        self.tool_calls.append({
            "tool": tool_name,
            "args": args,
            "start_time": time.time(),
            "timestamp": datetime.now().isoformat(),
            "status": "started"
        })
        return len(self.tool_calls) - 1  # Return index
    
    def track_tool_complete(self, idx: int, result: Any):
        """Track tool completion"""
        if idx < len(self.tool_calls):
            self.tool_calls[idx]["end_time"] = time.time()
            self.tool_calls[idx]["duration"] = self.tool_calls[idx]["end_time"] - self.tool_calls[idx]["start_time"]
            self.tool_calls[idx]["status"] = "completed"
            self.tool_calls[idx]["result_length"] = len(str(result))
    
    def track_tool_error(self, idx: int, error: Exception):
        """Track tool error"""
        if idx < len(self.tool_calls):
            self.tool_calls[idx]["end_time"] = time.time()
            self.tool_calls[idx]["duration"] = self.tool_calls[idx]["end_time"] - self.tool_calls[idx]["start_time"]
            self.tool_calls[idx]["status"] = "error"
            self.tool_calls[idx]["error"] = str(error)
    
    def track_error(self, error: Exception, context: str):
        """Track general errors"""
        self.errors.append({
            "error": str(error),
            "context": context,
            "timestamp": datetime.now().isoformat()
        })
    
    def get_summary(self):
        """Get monitoring summary"""
        return {
            "agent_executions": self.agent_executions,
            "tool_calls": self.tool_calls,
            "errors": self.errors,
            "total_duration": time.time() - self.start_time,
            "total_agents_called": len(self.agent_executions),
            "total_tools_called": len(self.tool_calls)
        }

# Global monitoring instance
monitoring = MonitoringMiddleware()

# ============================================================================
# TOOL 1: LOG INVESTIGATION
# ============================================================================

class LogInvestigationInput(BaseModel):
    """Input schema for log investigation"""
    query: str = Field(description="What to investigate in the logs")
    order_ids: Optional[List[str]] = Field(
        default=None,
        description="Specific order IDs to investigate (e.g., ['GOOD001', 'BAD001'])"
    )
    date: Optional[str] = Field(
        default=None,
        description="Date for investigation in YYYY-MM-DD format"
    )
    comparison_mode: bool = Field(
        default=False,
        description="Whether to compare multiple orders"
    )


@tool("investigate_logs", args_schema=LogInvestigationInput)
def investigate_logs(
    query: str,
    order_ids: Optional[List[str]] = None,
    date: Optional[str] = None,
    comparison_mode: bool = False
) -> str:
    """
    Investigate order logs with detailed analysis and comparison.
    
    Can analyze:
    - Individual order details
    - Compare good vs bad orders
    - Timeline analysis
    - Failure pattern detection
    
    Args:
        query: Description of what to investigate
        order_ids: List of order IDs to analyze
        date: Date for investigation (YYYY-MM-DD)
        comparison_mode: Whether to compare orders
        
    Returns:
        Detailed investigation report with findings
    """
    # Track this tool call
    idx = monitoring.track_tool_call("investigate_logs", {
        "query": query,
        "order_ids": order_ids,
        "date": date,
        "comparison_mode": comparison_mode
    })
    
    try:
        target_date = date or datetime.now().strftime("%Y-%m-%d")
        
        # Simulate log retrieval
        if comparison_mode and order_ids and len(order_ids) >= 2:
            result = _compare_orders(order_ids)
        elif order_ids:
            result = _get_order_details(order_ids[0])
        else:
            result = _search_logs(query, target_date)
        
        monitoring.track_tool_complete(idx, result)
        return result
        
    except Exception as e:
        monitoring.track_tool_error(idx, e)
        raise


def _compare_orders(order_ids: List[str]) -> str:
    """Compare multiple orders"""
    # Simulated data
    orders_data = {
        "GOOD001": {
            "status": "success",
            "timestamp": "2025-10-27T10:23:45Z",
            "steps": [
                {"step": "validation", "status": "✓", "duration": "12ms"},
                {"step": "payment", "status": "✓", "duration": "234ms"},
                {"step": "inventory", "status": "✓", "duration": "45ms"},
                {"step": "fulfillment", "status": "✓", "duration": "89ms"}
            ],
            "total_time": "380ms",
            "payment_method": "credit_card",
            "amount": 99.99
        },
        "BAD001": {
            "status": "failed",
            "timestamp": "2025-10-27T10:24:12Z",
            "steps": [
                {"step": "validation", "status": "✓", "duration": "15ms"},
                {"step": "payment", "status": "✗", "duration": "5234ms", "error": "gateway_timeout"},
                {"step": "inventory", "status": "-", "duration": "0ms"},
                {"step": "fulfillment", "status": "-", "duration": "0ms"}
            ],
            "total_time": "5249ms",
            "payment_method": "credit_card",
            "amount": 99.99,
            "error": "Payment gateway timeout after 5s"
        }
    }
    
    comparison = f"""
📊 ORDER COMPARISON ANALYSIS
{'='*70}

"""
    
    for order_id in order_ids:
        if order_id in orders_data:
            order = orders_data[order_id]
            comparison += f"""
🔍 ORDER: {order_id}
{'─'*70}
Status: {order['status'].upper()}
Timestamp: {order['timestamp']}
Amount: ${order['amount']}
Total Time: {order['total_time']}

📋 EXECUTION STEPS:
"""
            for step in order['steps']:
                status_icon = step['status']
                error_info = f" - ERROR: {step.get('error', '')}" if step.get('error') else ""
                comparison += f"  {status_icon} {step['step'].ljust(15)} {step['duration'].rjust(10)}{error_info}\n"
            
            if order.get('error'):
                comparison += f"\n⚠️  FAILURE REASON: {order['error']}\n"
    
    comparison += f"""

💡 KEY FINDINGS:
{'─'*70}
1. GOOD001 completed successfully in 380ms
2. BAD001 failed at payment step due to gateway timeout (5234ms)
3. Payment gateway exceeded normal response time by 20x
4. Subsequent steps were not executed after payment failure

🔧 RECOMMENDATIONS:
{'─'*70}
• Implement circuit breaker for payment gateway (timeout: 2s)
• Add retry logic with exponential backoff
• Set up monitoring alerts for gateway response time > 1s
• Consider fallback payment processor
"""
    
    return comparison


def _get_order_details(order_id: str) -> str:
    """Get detailed information for a single order"""
    return f"""
📦 ORDER DETAILS: {order_id}
{'='*70}

Status: SUCCESS
Order Date: 2025-10-27 10:23:45
Customer: customer_12345
Amount: $99.99

Execution Timeline:
✓ 10:23:45.012 - Validation completed (12ms)
✓ 10:23:45.246 - Payment processed (234ms)
✓ 10:23:45.291 - Inventory reserved (45ms)
✓ 10:23:45.380 - Fulfillment initiated (89ms)

Payment Details:
- Method: Credit Card (Visa ****1234)
- Gateway: Stripe
- Transaction ID: txn_abc123xyz

All systems nominal. Order processed successfully.
"""


def _search_logs(query: str, date: str) -> str:
    """Search logs for a query"""
    return f"""
🔍 LOG SEARCH RESULTS
{'='*70}
Query: "{query}"
Date: {date}

Found 1,247 matching entries:

Recent Failures (Last 24h):
• 67 payment gateway timeouts
• 18 inventory validation errors
• 12 address validation failures

Top Error Messages:
1. "Payment gateway timeout" - 67 occurrences
2. "Product out of stock" - 18 occurrences
3. "Invalid shipping address" - 12 occurrences

Peak Error Time: 10:23-10:30 (cluster of 45 errors)
"""

# ============================================================================
# TOOL 2: KNOWLEDGE RETRIEVAL (RAG)
# ============================================================================

class KnowledgeQueryInput(BaseModel):
    """Input schema for knowledge base queries"""
    question: str = Field(description="Question to answer from knowledge base")
    search_type: Literal["documentation", "troubleshooting", "configuration", "all"] = Field(
        default="all",
        description="Type of knowledge to search"
    )


@tool("search_knowledge", args_schema=KnowledgeQueryInput)
def search_knowledge(
    question: str,
    search_type: str = "all"
) -> str:
    """
    Search the knowledge base using RAG for documentation, troubleshooting guides,
    and configuration information.
    
    Args:
        question: Question to search for
        search_type: Type of documents to search
        
    Returns:
        Relevant information from knowledge base with source citations
    """
    idx = monitoring.track_tool_call("search_knowledge", {
        "question": question,
        "search_type": search_type
    })
    
    try:
        # Simulate vector DB search
        results = _perform_knowledge_search(question, search_type)
        monitoring.track_tool_complete(idx, results)
        return results
        
    except Exception as e:
        monitoring.track_tool_error(idx, e)
        raise


def _perform_knowledge_search(question: str, search_type: str) -> str:
    """Simulate RAG knowledge retrieval"""
    
    knowledge_base = {
        "payment failures": """
📚 KNOWLEDGE BASE: Payment Gateway Failures
{'='*70}

🎯 ROOT CAUSES:
1. Gateway Timeout (Most Common)
   - Cause: Third-party service exceeds 30s response time
   - Frequency: ~5% of transactions during peak hours
   - Impact: High - blocks order completion

2. Declined Transactions
   - Cause: Insufficient funds, fraud detection, card expiry
   - Frequency: ~2% of transactions
   - Impact: Medium - customer can retry

3. Network Issues
   - Cause: Connection failures, packet loss
   - Frequency: <1% of transactions
   - Impact: Low - automatic retry succeeds

🔧 RECOMMENDED SOLUTIONS:

**Immediate Actions:**
• Implement circuit breaker pattern
  - Timeout: 5s (reduced from 30s)
  - Fallback: Queue for retry
  
• Add retry logic
  - Max retries: 3
  - Backoff: Exponential (1s, 2s, 4s)
  - Only retry on timeout errors

**Long-term Improvements:**
• Implement backup payment processor
• Set up real-time monitoring (Datadog/New Relic)
• Alert on gateway response time > 2s
• Consider payment gateway redundancy

📖 RELATED DOCUMENTATION:
- docs/troubleshooting/payment-gateway.md
- docs/architecture/payment-processing.md
- incidents/2024-089-payment-timeout.md

🔗 INCIDENT HISTORY:
- Incident #2024-089: Similar issue resolved by timeout adjustment
- Resolution time: 2 hours
- Prevented recurrence: 95% reduction in timeouts
""",
        "configuration": """
📚 KNOWLEDGE BASE: System Configuration
{'='*70}

⚙️ PAYMENT GATEWAY CONFIGURATION:

Current Settings:
```yaml
payment_gateway:
  provider: stripe
  timeout: 30000  # milliseconds
  retry_attempts: 0  # ISSUE: No retries configured
  circuit_breaker: false  # ISSUE: Not enabled
  
  timeouts:
    connect: 5000
    read: 30000
    write: 5000
```

✅ RECOMMENDED CONFIGURATION:
```yaml
payment_gateway:
  provider: stripe
  timeout: 5000  # Reduced to 5s
  retry_attempts: 3
  retry_backoff: exponential
  circuit_breaker: true
  
  circuit_breaker_config:
    failure_threshold: 5
    timeout: 60000
    half_open_after: 30000
  
  timeouts:
    connect: 2000
    read: 5000
    write: 2000
  
  monitoring:
    alert_threshold_ms: 2000
    enable_detailed_logging: true
```

📝 Configuration Location: `/config/payment-gateway.yaml`
"""
    }
    
    # Simple keyword matching (in production, use actual RAG)
    if "payment" in question.lower() or "failure" in question.lower():
        return knowledge_base["payment failures"]
    elif "config" in question.lower():
        return knowledge_base["configuration"]
    else:
        return f"""
📚 KNOWLEDGE BASE SEARCH
{'='*70}
Question: "{question}"
Search Type: {search_type}

Found 3 relevant documents:

1. Payment Gateway Troubleshooting Guide (relevance: 92%)
   - Location: docs/troubleshooting/payment-gateway.md
   - Key topics: Timeout handling, retry logic, circuit breakers

2. Order Processing Architecture (relevance: 85%)
   - Location: docs/architecture/order-processing.md
   - Key topics: Validation pipeline, payment flow, fulfillment

3. Historical Incident Report #2024-089 (relevance: 78%)
   - Location: incidents/2024-089-payment-timeout.md
   - Resolution: Timeout adjustment and circuit breaker implementation

💡 SUMMARY:
Based on the knowledge base, payment gateway issues are typically resolved by:
1. Reducing timeout thresholds (30s → 5s)
2. Implementing circuit breaker pattern
3. Adding retry logic with exponential backoff
4. Setting up proactive monitoring

For detailed information, consult the full documentation.
"""

# ============================================================================
# HUMAN-IN-THE-LOOP CONFIGURATION
# ============================================================================

class HumanInTheLoopConfig:
    """Configuration for human-in-the-loop behavior"""
    def __init__(self):
        self.enabled = True  # Set to False to disable HITL
        self.require_approval_for_writes = True  # Always approve writes (UPDATE, DELETE, INSERT)
        self.require_approval_for_sensitive_tables = True  # Approve queries on sensitive tables
        self.sensitive_tables = ["users", "payments", "credentials", "api_keys"]
        self.auto_approve_safe_queries = True  # Auto-approve SELECT with LIMIT
        self.pending_approvals = {}  # Store pending approvals

# Global HITL configuration
hitl_config = HumanInTheLoopConfig()

# ============================================================================
# TOOL 3: DATABASE QUERY WITH HUMAN-IN-THE-LOOP
# ============================================================================

class DatabaseQueryInput(BaseModel):
    """Input schema for database queries"""
    natural_language_query: str = Field(
        description="Natural language description of what data to retrieve"
    )
    table_hint: Optional[str] = Field(
        default=None,
        description="Optional hint about which table(s) to query"
    )


class SQLApprovalRequest(BaseModel):
    """Request for SQL query approval"""
    query_id: str
    natural_language_query: str
    generated_sql: str
    risk_level: str  # "low", "medium", "high"
    reason: str
    timestamp: str


def _generate_sql_from_nl(natural_language_query: str, table_hint: Optional[str] = None) -> str:
    """Generate SQL from natural language query"""
    # In production, use actual NL-to-SQL with LLM or SQL generation library
    # This is a simulation
    
    query_lower = natural_language_query.lower()
    
    if "failed orders" in query_lower:
        return """SELECT 
    o.order_id,
    o.status,
    o.order_date,
    o.amount,
    o.payment_method,
    o.error_message
FROM orders o
WHERE o.status = 'failed'
    AND o.order_date >= DATE_SUB(CURDATE(), INTERVAL 1 DAY)
ORDER BY o.order_date DESC
LIMIT 100;"""
    
    elif "revenue" in query_lower and "payment method" in query_lower:
        return """SELECT 
    payment_method,
    COUNT(*) as transaction_count,
    SUM(amount) as total_revenue
FROM orders
WHERE status = 'completed'
GROUP BY payment_method
ORDER BY total_revenue DESC;"""
    
    elif "all orders" in query_lower or "orders from" in query_lower:
        return """SELECT 
    order_id,
    status,
    order_date,
    amount,
    customer_id
FROM orders
WHERE order_date >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)
LIMIT 1000;"""
    
    else:
        # Generic safe query
        return f"""SELECT * FROM orders 
WHERE order_date >= DATE_SUB(CURDATE(), INTERVAL 1 DAY)
LIMIT 100;  -- Generic query for: {natural_language_query}"""


def _analyze_sql_risk(sql: str) -> tuple[str, str]:
    """
    Analyze SQL query risk level
    Returns: (risk_level, reason)
    """
    sql_upper = sql.upper()
    
    # Check for write operations (HIGH RISK)
    write_operations = ["UPDATE", "DELETE", "INSERT", "DROP", "ALTER", "TRUNCATE", "CREATE"]
    for op in write_operations:
        if op in sql_upper:
            return ("high", f"Query contains write operation: {op}")
    
    # Check for sensitive tables (MEDIUM RISK)
    sensitive_tables = hitl_config.sensitive_tables
    for table in sensitive_tables:
        if table.upper() in sql_upper:
            return ("medium", f"Query accesses sensitive table: {table}")
    
    # Check for no LIMIT clause on SELECT (MEDIUM RISK)
    if "SELECT" in sql_upper and "LIMIT" not in sql_upper:
        return ("medium", "Query has no LIMIT clause - may return large dataset")
    
    # Safe query (LOW RISK)
    return ("low", "Safe SELECT query with LIMIT clause")


def _requires_human_approval(sql: str, risk_level: str) -> bool:
    """Determine if query requires human approval"""
    if not hitl_config.enabled:
        return False
    
    # Always require approval for high risk
    if risk_level == "high":
        return True
    
    # Require approval for medium risk if configured
    if risk_level == "medium" and hitl_config.require_approval_for_sensitive_tables:
        return True
    
    # Auto-approve low risk if configured
    if risk_level == "low" and hitl_config.auto_approve_safe_queries:
        return False
    
    # Default: require approval
    return True


@tool("query_database", args_schema=DatabaseQueryInput)
def query_database(
    natural_language_query: str,
    table_hint: Optional[str] = None
) -> str:
    """
    Query the database using natural language with Human-in-the-Loop approval.
    
    HITL Process:
    1. Generates SQL from natural language
    2. Analyzes risk level (high/medium/low)
    3. Requests human approval for risky queries
    4. Executes only after approval
    
    Examples:
    - "Show me all failed orders from yesterday" (Low risk - auto-approved)
    - "What's the total revenue by payment method?" (Low risk - auto-approved)
    - "Update order status for ORD-123" (High risk - requires approval)
    
    Args:
        natural_language_query: Natural language description of query
        table_hint: Optional hint about which tables to use
        
    Returns:
        Query results with insights and SQL used, or approval request
    """
    idx = monitoring.track_tool_call("query_database", {
        "query": natural_language_query,
        "table_hint": table_hint
    })
    
    try:
        # Step 1: Generate SQL from natural language
        generated_sql = _generate_sql_from_nl(natural_language_query, table_hint)
        
        # Step 2: Analyze risk
        risk_level, risk_reason = _analyze_sql_risk(generated_sql)
        
        # Step 3: Check if human approval is required
        if _requires_human_approval(generated_sql, risk_level):
            # Create approval request
            query_id = f"sql_{int(time.time() * 1000)}"
            approval_request = SQLApprovalRequest(
                query_id=query_id,
                natural_language_query=natural_language_query,
                generated_sql=generated_sql,
                risk_level=risk_level,
                reason=risk_reason,
                timestamp=datetime.now().isoformat()
            )
            
            # Store pending approval
            hitl_config.pending_approvals[query_id] = approval_request
            
            monitoring.track_tool_complete(idx, "PENDING_APPROVAL")
            
            # Return approval request to user
            return f"""
🔐 HUMAN APPROVAL REQUIRED
{'='*70}

Query ID: {query_id}
Risk Level: {risk_level.upper()}
Reason: {risk_reason}

Natural Language Query:
"{natural_language_query}"

Generated SQL:
```sql
{generated_sql}
```

⚠️ This query requires your approval before execution.

To approve this query, respond with:
"approve {query_id}"

To reject this query, respond with:
"reject {query_id}"

To modify the query, provide a new natural language description.
"""
        
        # Step 4: Auto-approved - execute query
        result = _execute_database_query(natural_language_query, generated_sql, table_hint)
        monitoring.track_tool_complete(idx, result)
        
        return f"""
✅ QUERY AUTO-APPROVED (Risk: {risk_level})

{result}
"""
        
    except Exception as e:
        monitoring.track_tool_error(idx, e)
        raise


def approve_sql_query(query_id: str) -> str:
    """
    Approve a pending SQL query
    Called when user responds with "approve <query_id>"
    """
    if query_id not in hitl_config.pending_approvals:
        return f"❌ Error: Query ID {query_id} not found in pending approvals."
    
    approval_request = hitl_config.pending_approvals[query_id]
    
    # Execute the approved query
    result = _execute_database_query(
        approval_request.natural_language_query,
        approval_request.generated_sql,
        None
    )
    
    # Remove from pending
    del hitl_config.pending_approvals[query_id]
    
    return f"""
✅ QUERY APPROVED AND EXECUTED

Query ID: {query_id}
Approved at: {datetime.now().isoformat()}

{result}
"""


def reject_sql_query(query_id: str, reason: Optional[str] = None) -> str:
    """
    Reject a pending SQL query
    Called when user responds with "reject <query_id>"
    """
    if query_id not in hitl_config.pending_approvals:
        return f"❌ Error: Query ID {query_id} not found in pending approvals."
    
    approval_request = hitl_config.pending_approvals[query_id]
    
    # Remove from pending
    del hitl_config.pending_approvals[query_id]
    
    return f"""
❌ QUERY REJECTED

Query ID: {query_id}
Rejected at: {datetime.now().isoformat()}
{f"Reason: {reason}" if reason else ""}

Original Query: "{approval_request.natural_language_query}"

The query was not executed. Please provide a different query or modify your request.
"""


def _execute_database_query(query: str, sql: str, table_hint: Optional[str]) -> str:
    """Execute database query (simulation)"""
    
    return f"""
🗄️ DATABASE QUERY RESULTS
{'='*70}

Natural Language Query: "{query}"
{f"Table Hint: {table_hint}" if table_hint else ""}

Executed SQL:
```sql
{sql}
```

📊 RESULTS (67 rows returned):

| Order ID  | Status | Date       | Amount  | Payment    | Error            |
|-----------|--------|------------|---------|------------|------------------|
| ORD-5432  | failed | 2025-10-27 | $99.99  | credit_card| gateway_timeout  |
| ORD-5434  | failed | 2025-10-27 | $149.50 | credit_card| gateway_timeout  |
| ORD-5441  | failed | 2025-10-27 | $75.20  | paypal     | declined         |
| ORD-5456  | failed | 2025-10-27 | $199.99 | credit_card| gateway_timeout  |
| ...       | ...    | ...        | ...     | ...        | ...              |

📈 AGGREGATED INSIGHTS:

Error Breakdown:
• gateway_timeout: 45 orders (67.2%)
• declined: 15 orders (22.4%)
• validation_error: 7 orders (10.4%)

Total Revenue Lost: $6,847.33

Payment Method Distribution:
• credit_card: 50 failures
• paypal: 12 failures
• bank_transfer: 5 failures

💡 RECOMMENDATION:
Primary issue is payment gateway timeouts (67% of failures).
See knowledge base for resolution steps.
"""

# ============================================================================
# DEEP AGENT SUPERVISOR (LangChain 1.0.2)
# ============================================================================

class SupervisorState(TypedDict):
    """State for supervisor chain"""
    messages: List[Any]


def create_supervisor_system(
    azure_endpoint: str,
    api_key: str,
    api_version: str = "2024-02-15-preview",
    deployment_name: str = "gpt-4"
) -> Runnable:
    """
    Create the deep agent supervisor that can call sub-agents as tools.
    Compatible with LangChain 1.0.2
    
    Args:
        azure_endpoint: Azure OpenAI endpoint URL
        api_key: Azure OpenAI API key
        api_version: API version
        deployment_name: Model deployment name
        
    Returns:
        Runnable supervisor chain
    """
    
    # Initialize Azure OpenAI (LangChain 1.0.2 style)
    llm = AzureChatOpenAI(
        azure_endpoint=azure_endpoint,
        api_key=api_key,
        api_version=api_version,
        deployment_name=deployment_name,
        temperature=0,
        streaming=False  # Set to True if you want token-level streaming
    )
    
    # Bind tools to LLM (LangChain 1.0.2)
    tools = [investigate_logs, search_knowledge, query_database]
    llm_with_tools = llm.bind_tools(tools)
    
    # Create supervisor prompt
    supervisor_prompt = ChatPromptTemplate.from_messages([
        ("system", """You are a Deep Agent Supervisor coordinating specialized sub-agents.

**Available Sub-Agents (as tools):**

1. **investigate_logs** - Log Investigation Agent
   - Analyzes order logs and compares orders
   - Can identify failures and patterns
   - Provides timeline analysis
   
2. **search_knowledge** - Knowledge Retrieval Agent (RAG)
   - Searches documentation and troubleshooting guides
   - Provides solutions from knowledge base
   - Cites sources
   
3. **query_database** - Database Query Agent
   - Converts natural language to SQL
   - Safely executes database queries
   - Provides aggregated insights

**Your Responsibilities:**
- Understand user intent and decide which agent(s) to call
- You can call MULTIPLE agents if needed
- Synthesize results from multiple agents into a coherent response
- Provide clear, actionable answers

**Best Practices:**
- For comparison questions → use investigate_logs with comparison_mode=True
- For "why" or "how to fix" questions → use search_knowledge
- For data queries or statistics → use query_database
- For complex questions → call multiple agents and synthesize results

Always provide clear, well-structured responses with actionable insights."""),
        MessagesPlaceholder(variable_name="messages"),
    ])
    
    # Create the preprocessing middleware
    def preprocess(inputs: Dict) -> Dict:
        """Preprocessing middleware - runs before agent execution"""
        monitoring.reset()
        monitoring.track_agent_start("supervisor")
        return inputs
    
    # Create agent executor with tool calling (LangChain 1.0.2)
    def agent_executor(state: Dict) -> Dict:
        """Execute agent with tool calling logic"""
        messages = state["messages"]
        
        # Convert dict messages to LangChain messages if needed
        lc_messages = []
        for msg in messages:
            if isinstance(msg, dict):
                if msg.get("role") == "user":
                    lc_messages.append(HumanMessage(content=msg["content"]))
                elif msg.get("role") == "assistant":
                    lc_messages.append(AIMessage(content=msg["content"]))
                elif msg.get("role") == "system":
                    lc_messages.append(SystemMessage(content=msg["content"]))
            else:
                lc_messages.append(msg)
        
        # Format prompt and get response from supervisor
        formatted_prompt = supervisor_prompt.format_messages(messages=lc_messages)
        response = llm_with_tools.invoke(formatted_prompt)
        
        # Check if tools were called (LangChain 1.0.2 tool calling format)
        if hasattr(response, 'tool_calls') and response.tool_calls:
            tool_messages = []
            
            for tool_call in response.tool_calls:
                tool_name = tool_call["name"]
                tool_args = tool_call["args"]
                tool_id = tool_call.get("id", f"call_{tool_name}")
                
                # Find and execute the tool
                tool_func = None
                for t in tools:
                    if t.name == tool_name:
                        tool_func = t
                        break
                
                if tool_func:
                    try:
                        # Execute tool (LangChain 1.0.2 tool invocation)
                        result = tool_func.invoke(tool_args)
                        tool_messages.append(
                            ToolMessage(
                                content=str(result),
                                tool_call_id=tool_id,
                                name=tool_name
                            )
                        )
                    except Exception as e:
                        monitoring.track_error(e, f"Tool execution: {tool_name}")
                        tool_messages.append(
                            ToolMessage(
                                content=f"Error executing tool {tool_name}: {str(e)}",
                                tool_call_id=tool_id,
                                name=tool_name
                            )
                        )
            
            # Get final response after tool execution
            all_messages = lc_messages + [response] + tool_messages
            final_response = llm.invoke(all_messages)
            
            return {"messages": all_messages + [final_response]}
        
        # No tools called, return direct response
        return {"messages": lc_messages + [response]}
    
    # Create the postprocessing middleware
    def postprocess(outputs: Dict) -> Dict:
        """Postprocessing middleware - runs after agent execution"""
        monitoring.track_agent_complete("supervisor")
        
        # Extract final response
        messages = outputs.get("messages", [])
        final_response = "No response generated"
        
        # Find last AI message with content
        for msg in reversed(messages):
            if isinstance(msg, AIMessage) and msg.content:
                final_response = msg.content
                break
        
        return {
            "final_response": final_response,
            "monitoring": monitoring.get_summary(),
            "metadata": {
                "timestamp": datetime.now().isoformat(),
                "total_duration": monitoring.get_summary()["total_duration"],
                "messages_count": len(messages)
            },
            "raw_output": outputs
        }
    
    # Build chain with middleware (LangChain 1.0.2 LCEL)
    supervisor_chain = (
        RunnableLambda(preprocess)
        | RunnableLambda(agent_executor)
        | RunnableLambda(postprocess)
    )
    
    return supervisor_chain


# ============================================================================
# EXAMPLE USAGE
# ============================================================================

if __name__ == "__main__":
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    
    print("🚀 Initializing Deep Agent Supervisor (LangChain 1.0.2)...")
    
    # Create supervisor
    supervisor = create_supervisor_system(
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview"),
        deployment_name=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4")
    )
    
    print("✅ Supervisor initialized!\n")
    
    # Test query
    print("📝 Testing query: 'Compare orders GOOD001 and BAD001'")
    print("="*70)
    
    result = supervisor.invoke({
        "messages": [
            {"role": "user", "content": "Compare orders GOOD001 and BAD001, then explain what causes the failures"}
        ]
    })
    
    print("\n" + "="*70)
    print("FINAL RESPONSE:")
    print("="*70)
    print(result["final_response"])
    
    print("\n" + "="*70)
    print("MONITORING SUMMARY:")
    print("="*70)
    import json
    print(json.dumps(result["monitoring"], indent=2))
    
    print("\n✅ Test completed successfully!")
