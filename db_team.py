"""
Database Team - NLP to SQL Query Generation and Execution
Enhanced with LangChain SQL Agent patterns and few-shot prompting
Uses LangGraph v1+ pattern with create_agent from langchain.agents
"""
from typing import List, Dict, Any
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate, FewShotPromptTemplate
from langchain.agents import create_agent
import sqlite3
import json

# Database schema with detailed descriptions
DATABASE_SCHEMA = """
-- Orders Table: Stores customer order information
CREATE TABLE orders (
    order_id VARCHAR(50) PRIMARY KEY,      -- Unique order identifier (e.g., GOOD001, BAD001)
    customer_id VARCHAR(50),                -- Customer identifier
    order_date TIMESTAMP,                   -- When the order was placed
    total_amount DECIMAL(10, 2),           -- Total order value in USD
    status VARCHAR(20),                     -- Order status: completed, failed, pending, cancelled
    payment_status VARCHAR(20),             -- Payment status: paid, pending, failed, refunded
    shipping_address TEXT                   -- Customer shipping address
);

-- Order Items Table: Line items for each order
CREATE TABLE order_items (
    item_id INTEGER PRIMARY KEY,            -- Unique item identifier
    order_id VARCHAR(50),                   -- Foreign key to orders table
    product_id VARCHAR(50),                 -- Product identifier
    quantity INTEGER,                       -- Quantity ordered
    unit_price DECIMAL(10, 2),             -- Price per unit in USD
    FOREIGN KEY (order_id) REFERENCES orders(order_id)
);

-- Inventory Table: Product stock information
CREATE TABLE inventory (
    product_id VARCHAR(50) PRIMARY KEY,     -- Unique product identifier
    product_name VARCHAR(200),              -- Product name/description
    stock_quantity INTEGER,                 -- Total stock available
    reserved_quantity INTEGER,              -- Stock reserved for pending orders
    available_quantity INTEGER,             -- Stock available for new orders
    reorder_threshold INTEGER,              -- Minimum stock level before reorder
    last_updated TIMESTAMP                  -- Last inventory update timestamp
);

-- System Logs Table: Event logs for debugging and analysis
CREATE TABLE system_logs (
    log_id INTEGER PRIMARY KEY,             -- Unique log entry identifier
    order_id VARCHAR(50),                   -- Related order ID (if applicable)
    timestamp TIMESTAMP,                    -- When the event occurred
    event_type VARCHAR(50),                 -- Type of event (order_created, payment_validated, etc.)
    status VARCHAR(20),                     -- Event status: success, failed, pending
    error_message TEXT,                     -- Error details if status is failed
    duration_ms INTEGER                     -- Event processing time in milliseconds
);
"""

# Few-shot examples for better SQL generation
FEW_SHOT_EXAMPLES = [
    {
        "input": "Show me all failed orders",
        "query": """SELECT order_id, customer_id, order_date, total_amount, status 
FROM orders 
WHERE status = 'failed' 
ORDER BY order_date DESC;""",
        "explanation": "Filter orders by status='failed' and sort by most recent"
    },
    {
        "input": "Count how many orders each customer has",
        "query": """SELECT customer_id, COUNT(*) as order_count, SUM(total_amount) as total_spent
FROM orders 
GROUP BY customer_id 
ORDER BY order_count DESC;""",
        "explanation": "Use GROUP BY to aggregate orders per customer"
    },
    {
        "input": "Which products have low inventory?",
        "query": """SELECT product_id, product_name, available_quantity, reorder_threshold
FROM inventory 
WHERE available_quantity < reorder_threshold 
ORDER BY available_quantity ASC;""",
        "explanation": "Compare available_quantity with reorder_threshold"
    },
    {
        "input": "Show me orders with their items",
        "query": """SELECT o.order_id, o.customer_id, o.total_amount, 
       oi.product_id, oi.quantity, oi.unit_price
FROM orders o
JOIN order_items oi ON o.order_id = oi.order_id
ORDER BY o.order_date DESC
LIMIT 10;""",
        "explanation": "Use JOIN to combine orders with their line items"
    },
    {
        "input": "What's the total revenue from completed orders?",
        "query": """SELECT 
    COUNT(*) as total_orders,
    SUM(total_amount) as total_revenue,
    AVG(total_amount) as avg_order_value
FROM orders 
WHERE status = 'completed';""",
        "explanation": "Use aggregate functions (SUM, AVG, COUNT) for statistics"
    },
    {
        "input": "Show me orders that failed with error messages",
        "query": """SELECT o.order_id, o.status, sl.error_message, sl.timestamp
FROM orders o
LEFT JOIN system_logs sl ON o.order_id = sl.order_id
WHERE o.status = 'failed' AND sl.error_message IS NOT NULL
ORDER BY sl.timestamp DESC;""",
        "explanation": "Use LEFT JOIN to get error details from system_logs"
    }
]

# Create few-shot prompt template
EXAMPLE_PROMPT = PromptTemplate(
    input_variables=["input", "query", "explanation"],
    template="Question: {input}\nSQL Query: {query}\nExplanation: {explanation}"
)

FEW_SHOT_PROMPT = FewShotPromptTemplate(
    examples=FEW_SHOT_EXAMPLES,
    example_prompt=EXAMPLE_PROMPT,
    prefix="""You are a SQL expert. Given an input question, create a syntactically correct SQLite query.

Database Schema:
{schema}

Here are some examples of questions and their corresponding SQL queries:
""",
    suffix="""Question: {input}
SQL Query:""",
    input_variables=["input", "schema"]
)

def get_db_connection():
    """Create a database connection with sample data"""
    conn = sqlite3.connect(':memory:', check_same_thread=False)
    cursor = conn.cursor()
    
    # Create tables
    cursor.executescript(DATABASE_SCHEMA)
    
    # Insert sample data
    cursor.executescript("""
    INSERT INTO orders VALUES 
        ('GOOD001', 'CUST001', '2025-10-18 10:00:00', 299.99, 'completed', 'paid', '123 Main St'),
        ('BAD001', 'CUST002', '2025-10-18 11:00:00', 499.99, 'failed', 'paid', '456 Oak Ave'),
        ('GOOD002', 'CUST003', '2025-10-18 12:00:00', 149.99, 'completed', 'paid', '789 Pine Rd'),
        ('PEND001', 'CUST004', '2025-10-18 13:00:00', 799.99, 'pending', 'pending', '321 Elm St'),
        ('GOOD003', 'CUST001', '2025-10-19 14:00:00', 599.99, 'completed', 'paid', '123 Main St');
    
    INSERT INTO order_items VALUES 
        (1, 'GOOD001', 'PROD001', 2, 149.99),
        (2, 'BAD001', 'PROD002', 1, 499.99),
        (3, 'GOOD002', 'PROD003', 3, 49.99),
        (4, 'PEND001', 'PROD001', 1, 149.99),
        (5, 'PEND001', 'PROD004', 2, 324.99),
        (6, 'GOOD003', 'PROD003', 5, 119.99);
    
    INSERT INTO inventory VALUES 
        ('PROD001', 'Premium Widget A', 100, 10, 90, 20, '2025-10-18 09:00:00'),
        ('PROD002', 'Deluxe Widget B', 0, 0, 0, 10, '2025-10-18 09:00:00'),
        ('PROD003', 'Standard Widget C', 150, 5, 145, 30, '2025-10-18 09:00:00'),
        ('PROD004', 'Elite Widget D', 50, 3, 47, 15, '2025-10-18 09:00:00');
    
    INSERT INTO system_logs VALUES 
        (1, 'GOOD001', '2025-10-18 10:00:00', 'order_created', 'success', NULL, 45),
        (2, 'GOOD001', '2025-10-18 10:00:15', 'payment_validated', 'success', NULL, 230),
        (3, 'GOOD001', '2025-10-18 10:05:00', 'order_shipped', 'success', NULL, 890),
        (4, 'BAD001', '2025-10-18 11:00:00', 'order_created', 'success', NULL, 52),
        (5, 'BAD001', '2025-10-18 11:02:00', 'inventory_check', 'failed', 'Insufficient inventory for PROD002', 78000),
        (6, 'GOOD002', '2025-10-18 12:00:00', 'order_created', 'success', NULL, 48),
        (7, 'GOOD002', '2025-10-18 12:02:10', 'order_fulfilled', 'success', NULL, 520);
    """)
    
    conn.commit()
    return conn

# Shared connection for the session
_db_conn = None
_sql_database = None

def get_connection():
    """Get or create database connection"""
    global _db_conn
    if _db_conn is None:
        _db_conn = get_db_connection()
    return _db_conn

def get_sql_database():
    """Get SQLDatabase instance for LangChain"""
    global _sql_database
    if _sql_database is None:
        conn = get_connection()
        _sql_database = SQLDatabase.from_uri("sqlite:///", engine=conn)
    return _sql_database

@tool
def list_tables() -> str:
    """
    List all tables in the database with their descriptions.
    
    Returns:
        JSON string with table names and descriptions
    """
    tables = {
        "orders": "Customer order information with status and payment details",
        "order_items": "Line items for each order with product and quantity",
        "inventory": "Product stock levels and availability",
        "system_logs": "Event logs for debugging and monitoring"
    }
    return json.dumps({"tables": tables}, indent=2)

@tool
def describe_table(table_name: str) -> str:
    """
    Get detailed schema information for a specific table.
    
    Args:
        table_name: Name of the table to describe
        
    Returns:
        JSON string with column details and descriptions
    """
    table_descriptions = {
        "orders": {
            "columns": [
                {"name": "order_id", "type": "VARCHAR(50)", "description": "Unique order identifier"},
                {"name": "customer_id", "type": "VARCHAR(50)", "description": "Customer identifier"},
                {"name": "order_date", "type": "TIMESTAMP", "description": "Order placement date"},
                {"name": "total_amount", "type": "DECIMAL", "description": "Total order value in USD"},
                {"name": "status", "type": "VARCHAR(20)", "description": "completed, failed, pending, cancelled"},
                {"name": "payment_status", "type": "VARCHAR(20)", "description": "paid, pending, failed, refunded"},
                {"name": "shipping_address", "type": "TEXT", "description": "Shipping address"}
            ],
            "sample_query": "SELECT * FROM orders WHERE status = 'completed' LIMIT 5"
        },
        "order_items": {
            "columns": [
                {"name": "item_id", "type": "INTEGER", "description": "Unique item ID"},
                {"name": "order_id", "type": "VARCHAR(50)", "description": "Foreign key to orders"},
                {"name": "product_id", "type": "VARCHAR(50)", "description": "Product identifier"},
                {"name": "quantity", "type": "INTEGER", "description": "Quantity ordered"},
                {"name": "unit_price", "type": "DECIMAL", "description": "Price per unit"}
            ],
            "sample_query": "SELECT * FROM order_items WHERE order_id = 'GOOD001'"
        },
        "inventory": {
            "columns": [
                {"name": "product_id", "type": "VARCHAR(50)", "description": "Product identifier"},
                {"name": "product_name", "type": "VARCHAR(200)", "description": "Product name"},
                {"name": "stock_quantity", "type": "INTEGER", "description": "Total stock"},
                {"name": "reserved_quantity", "type": "INTEGER", "description": "Reserved for orders"},
                {"name": "available_quantity", "type": "INTEGER", "description": "Available for sale"},
                {"name": "reorder_threshold", "type": "INTEGER", "description": "Reorder level"}
            ],
            "sample_query": "SELECT * FROM inventory WHERE available_quantity < reorder_threshold"
        },
        "system_logs": {
            "columns": [
                {"name": "log_id", "type": "INTEGER", "description": "Log entry ID"},
                {"name": "order_id", "type": "VARCHAR(50)", "description": "Related order"},
                {"name": "timestamp", "type": "TIMESTAMP", "description": "Event time"},
                {"name": "event_type", "type": "VARCHAR(50)", "description": "Event name"},
                {"name": "status", "type": "VARCHAR(20)", "description": "success or failed"},
                {"name": "error_message", "type": "TEXT", "description": "Error details"},
                {"name": "duration_ms", "type": "INTEGER", "description": "Processing time"}
            ],
            "sample_query": "SELECT * FROM system_logs WHERE status = 'failed'"
        }
    }
    
    if table_name.lower() in table_descriptions:
        return json.dumps(table_descriptions[table_name.lower()], indent=2)
    else:
        return json.dumps({"error": f"Table {table_name} not found"})

@tool
def generate_sql_with_examples(question: str) -> str:
    """
    Generate SQL query from natural language using few-shot examples.
    
    Args:
        question: Natural language question
        
    Returns:
        JSON string with generated SQL and explanation
    """
    try:
        # Use few-shot prompt to generate SQL
        prompt = FEW_SHOT_PROMPT.format(input=question, schema=DATABASE_SCHEMA)
        
        # For demo, use pattern matching with examples
        question_lower = question.lower()
        
        # Match against examples
        for example in FEW_SHOT_EXAMPLES:
            if any(word in question_lower for word in example["input"].lower().split()):
                return json.dumps({
                    "sql": example["query"],
                    "explanation": example["explanation"],
                    "confidence": "high",
                    "matched_example": example["input"]
                }, indent=2)
        
        # Fallback generation
        if "failed" in question_lower or "error" in question_lower:
            sql = """SELECT o.order_id, o.status, sl.error_message, sl.timestamp
FROM orders o
LEFT JOIN system_logs sl ON o.order_id = sl.order_id
WHERE o.status = 'failed' OR sl.status = 'failed'
ORDER BY sl.timestamp DESC;"""
            explanation = "Query failed orders with error details"
            
        elif "inventory" in question_lower and "low" in question_lower:
            sql = """SELECT product_id, product_name, available_quantity, reorder_threshold
FROM inventory
WHERE available_quantity < reorder_threshold
ORDER BY available_quantity ASC;"""
            explanation = "Find products below reorder threshold"
            
        elif "revenue" in question_lower or "total" in question_lower:
            sql = """SELECT COUNT(*) as total_orders, SUM(total_amount) as total_revenue, AVG(total_amount) as avg_order
FROM orders
WHERE status = 'completed';"""
            explanation = "Calculate revenue statistics"
            
        else:
            sql = "SELECT * FROM orders ORDER BY order_date DESC LIMIT 10;"
            explanation = "Show recent orders"
        
        return json.dumps({
            "sql": sql.strip(),
            "explanation": explanation,
            "confidence": "medium"
        }, indent=2)
        
    except Exception as e:
        return json.dumps({"error": str(e)})

@tool
def execute_sql_query(sql_query: str) -> str:
    """
    Execute SQL query and return results.
    
    Args:
        sql_query: SQL query to execute
        
    Returns:
        JSON string with query results
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Safety check
        sql_lower = sql_query.lower().strip()
        if any(word in sql_lower for word in ['drop', 'delete', 'update', 'insert', 'alter']):
            return json.dumps({
                "success": False,
                "error": "Only SELECT queries are allowed for safety"
            })
        
        cursor.execute(sql_query)
        results = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description] if cursor.description else []
        
        # Format results
        formatted_results = []
        for row in results:
            formatted_results.append(dict(zip(columns, row)))
        
        return json.dumps({
            "success": True,
            "columns": columns,
            "row_count": len(formatted_results),
            "rows": formatted_results[:100],  # Limit to 100 rows
            "truncated": len(formatted_results) > 100
        }, indent=2)
        
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": str(e),
            "sql": sql_query
        }, indent=2)

DB_TEAM_PROMPT = """You are a Database Query Specialist with expertise in SQL and data analysis.

**Database Schema:**
{schema}

**Available Tools:**
1. list_tables: See all tables and their descriptions
2. describe_table: Get detailed column information for a table
3. generate_sql_with_examples: Create SQL using few-shot examples
4. execute_sql_query: Run the SQL query and get results

**Few-Shot Examples:**
{examples}

**Best Practices:**
1. Always check table schema before generating SQL
2. Use the few-shot examples as templates
3. Use JOINs for related data across tables
4. Include appropriate WHERE clauses and LIMIT results
5. Format numbers and dates for readability
6. Explain the query logic

**Query Pattern Recognition:**
- "failed orders" → JOIN orders + system_logs, filter by status
- "low inventory" → Filter inventory where available < threshold
- "revenue" / "total" → Use SUM/COUNT/AVG aggregates
- "customer orders" → GROUP BY customer_id
- "product sales" → JOIN order_items with product info

**Response Format:**
1. Show the SQL query in a code block
2. Execute the query
3. Present results in a clear table format
4. Provide insights or summary of findings"""

def create_db_agent(llm: ChatOpenAI):
    """
    Create the database query agent using LangGraph v1+ pattern.
    Uses create_agent from langchain.agents (recommended for LangGraph v1+)
    """
    from langchain.agents import create_agent
    
    tools = [
        list_tables,
        describe_table,
        generate_sql_with_examples,
        execute_sql_query
    ]
    
    # Format examples for prompt
    examples_text = "\n\n".join([
        f"Q: {ex['input']}\nSQL: {ex['query']}\nWhy: {ex['explanation']}"
        for ex in FEW_SHOT_EXAMPLES[:3]  # Show first 3 examples
    ])
    
    system_prompt = DB_TEAM_PROMPT.format(
        schema=DATABASE_SCHEMA,
        examples=examples_text
    )
    
    # Create agent using the new recommended approach
    agent = create_agent(
        llm=llm,
        tools=tools,
        prompt=system_prompt
    )
    
    return agent
