"""
Database Team - NLP to SQL Query Generation and Execution
"""
from typing import List, Dict, Any
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
import sqlite3
import json
from datetime import datetime

# Database schema
DATABASE_SCHEMA = """
-- Orders Table
CREATE TABLE orders (
    order_id VARCHAR(50) PRIMARY KEY,
    customer_id VARCHAR(50),
    order_date TIMESTAMP,
    total_amount DECIMAL(10, 2),
    status VARCHAR(20), -- completed, failed, pending, cancelled
    payment_status VARCHAR(20), -- paid, pending, failed, refunded
    shipping_address TEXT
);

-- Order Items Table  
CREATE TABLE order_items (
    item_id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id VARCHAR(50),
    product_id VARCHAR(50),
    quantity INTEGER,
    unit_price DECIMAL(10, 2),
    FOREIGN KEY (order_id) REFERENCES orders(order_id)
);

-- Inventory Table
CREATE TABLE inventory (
    product_id VARCHAR(50) PRIMARY KEY,
    product_name VARCHAR(200),
    stock_quantity INTEGER,
    reserved_quantity INTEGER,
    available_quantity INTEGER,
    reorder_threshold INTEGER,
    last_updated TIMESTAMP
);

-- System Logs Table
CREATE TABLE system_logs (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id VARCHAR(50),
    timestamp TIMESTAMP,
    event_type VARCHAR(50),
    status VARCHAR(20),
    error_message TEXT,
    duration_ms INTEGER
);
"""

def get_db_connection():
    """Create in-memory database with sample data"""
    conn = sqlite3.connect(':memory:', check_same_thread=False)
    cursor = conn.cursor()
    
    # Create schema
    cursor.executescript(DATABASE_SCHEMA)
    
    # Insert sample data
    cursor.executescript("""
    INSERT INTO orders VALUES 
        ('GOOD001', 'CUST001', '2025-10-18 10:00:00', 299.99, 'completed', 'paid', '123 Main St'),
        ('BAD001', 'CUST002', '2025-10-18 11:00:00', 499.99, 'failed', 'paid', '456 Oak Ave'),
        ('GOOD002', 'CUST003', '2025-10-18 12:00:00', 149.99, 'completed', 'paid', '789 Pine Rd'),
        ('PEND001', 'CUST004', '2025-10-18 13:00:00', 799.99, 'pending', 'pending', '321 Elm St');
    
    INSERT INTO order_items VALUES 
        (1, 'GOOD001', 'PROD001', 2, 149.99),
        (2, 'BAD001', 'PROD002', 1, 499.99),
        (3, 'GOOD002', 'PROD003', 3, 49.99),
        (4, 'PEND001', 'PROD001', 1, 149.99),
        (5, 'PEND001', 'PROD004', 2, 324.99);
    
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
        (5, 'BAD001', '2025-10-18 11:02:00', 'inventory_check', 'failed', 'Insufficient inventory', 78000),
        (6, 'GOOD002', '2025-10-18 12:00:00', 'order_created', 'success', NULL, 48),
        (7, 'GOOD002', '2025-10-18 12:02:10', 'order_fulfilled', 'success', NULL, 520);
    """)
    
    conn.commit()
    return conn

# Shared connection for the session
_db_conn = None

def get_connection():
    """Get or create database connection"""
    global _db_conn
    if _db_conn is None:
        _db_conn = get_db_connection()
    return _db_conn

@tool
def get_database_schema(table_name: str = None) -> str:
    """
    Get database schema information.
    
    Args:
        table_name: Optional specific table name. If None, returns all schema info.
        
    Returns:
        JSON string with schema information
    """
    if table_name:
        # Extract specific table schema
        lines = DATABASE_SCHEMA.split('\n')
        in_table = False
        table_schema = []
        
        for line in lines:
            if f'CREATE TABLE {table_name}' in line:
                in_table = True
            if in_table:
                table_schema.append(line)
                if ');' in line:
                    break
        
        if table_schema:
            return json.dumps({
                "table": table_name,
                "schema": '\n'.join(table_schema)
            }, indent=2)
        else:
            return json.dumps({"error": f"Table {table_name} not found"})
    
    return json.dumps({
        "tables": ["orders", "order_items", "inventory", "system_logs"],
        "full_schema": DATABASE_SCHEMA
    }, indent=2)

@tool
def text_to_sql(natural_language_query: str) -> str:
    """
    Convert natural language query to SQL.
    
    Args:
        natural_language_query: Natural language description of desired query
        
    Returns:
        JSON string with generated SQL and explanation
    """
    query_lower = natural_language_query.lower()
    
    # Pattern matching for common queries
    if "failed" in query_lower or "error" in query_lower:
        sql = """
SELECT 
    o.order_id,
    o.status,
    o.total_amount,
    sl.error_message,
    sl.timestamp,
    sl.duration_ms
FROM orders o
LEFT JOIN system_logs sl ON o.order_id = sl.order_id
WHERE o.status = 'failed' OR sl.status = 'failed'
ORDER BY sl.timestamp DESC;"""
        explanation = "Retrieves failed orders with error details and timing information"
        
    elif "inventory" in query_lower and ("low" in query_lower or "stock" in query_lower):
        sql = """
SELECT 
    product_id,
    product_name,
    available_quantity,
    reorder_threshold,
    (reorder_threshold - available_quantity) as shortage
FROM inventory
WHERE available_quantity < reorder_threshold
ORDER BY shortage DESC;"""
        explanation = "Finds products with inventory below reorder threshold"
        
    elif "revenue" in query_lower or "total" in query_lower and "amount" in query_lower:
        sql = """
SELECT 
    COUNT(*) as total_orders,
    SUM(total_amount) as total_revenue,
    AVG(total_amount) as avg_order_value,
    MIN(total_amount) as min_order,
    MAX(total_amount) as max_order
FROM orders
WHERE status = 'completed';"""
        explanation = "Calculates revenue statistics for completed orders"
        
    elif "customer" in query_lower and "order" in query_lower:
        sql = """
SELECT 
    customer_id,
    COUNT(*) as order_count,
    SUM(total_amount) as total_spent,
    AVG(total_amount) as avg_order_value
FROM orders
GROUP BY customer_id
ORDER BY total_spent DESC;"""
        explanation = "Analyzes customer order patterns and spending"
        
    elif "product" in query_lower and "popular" in query_lower:
        sql = """
SELECT 
    oi.product_id,
    i.product_name,
    SUM(oi.quantity) as total_sold,
    COUNT(DISTINCT oi.order_id) as order_count
FROM order_items oi
JOIN inventory i ON oi.product_id = i.product_id
GROUP BY oi.product_id, i.product_name
ORDER BY total_sold DESC
LIMIT 10;"""
        explanation = "Identifies top-selling products by quantity"
        
    elif "performance" in query_lower or "duration" in query_lower:
        sql = """
SELECT 
    event_type,
    AVG(duration_ms) as avg_duration,
    MIN(duration_ms) as min_duration,
    MAX(duration_ms) as max_duration,
    COUNT(*) as event_count
FROM system_logs
WHERE duration_ms IS NOT NULL
GROUP BY event_type
ORDER BY avg_duration DESC;"""
        explanation = "Analyzes system performance by event type"
        
    else:
        sql = """
SELECT *
FROM orders
ORDER BY order_date DESC
LIMIT 10;"""
        explanation = "Shows recent orders (default query)"
    
    return json.dumps({
        "sql": sql.strip(),
        "explanation": explanation,
        "natural_language_query": natural_language_query
    }, indent=2)

@tool
def execute_sql(sql_query: str) -> str:
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
            "rows": formatted_results
        }, indent=2)
        
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": str(e),
            "sql": sql_query
        }, indent=2)

@tool
def explain_query(sql_query: str) -> str:
    """
    Get query execution plan without executing.
    
    Args:
        sql_query: SQL query to explain
        
    Returns:
        JSON string with query plan
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute(f"EXPLAIN QUERY PLAN {sql_query}")
        plan = cursor.fetchall()
        
        return json.dumps({
            "valid": True,
            "query_plan": [{"detail": str(row)} for row in plan],
            "message": "Query is valid"
        }, indent=2)
        
    except Exception as e:
        return json.dumps({
            "valid": False,
            "error": str(e),
            "message": "Query validation failed"
        }, indent=2)

DB_TEAM_PROMPT = """You are a Database Query Specialist with expertise in SQL and data analysis.

**Your Responsibilities:**
1. Convert natural language questions to SQL queries
2. Execute queries safely against the database
3. Interpret and explain query results
4. Provide data insights and patterns

**Available Tools:**
- get_database_schema: View table structures and relationships
- text_to_sql: Convert natural language to SQL
- execute_sql: Run SQL queries and get results
- explain_query: Validate SQL and view execution plan

**Database Schema:**
- `orders`: Order records with status and amounts
- `order_items`: Line items for each order
- `inventory`: Product stock levels and thresholds
- `system_logs`: Event logs with timing and errors

**Best Practices:**
1. Always check schema before generating SQL
2. Validate complex queries with EXPLAIN
3. Use JOINs for related data
4. Include relevant WHERE clauses and LIMIT results
5. Provide clear explanations of results
6. Format numbers and dates for readability

**Query Pattern Recognition:**
- Failed orders: Join orders + system_logs
- Inventory issues: Filter by reorder thresholds
- Revenue analysis: Aggregate completed orders
- Performance: Analyze duration_ms in logs"""

def create_db_agent(llm: ChatOpenAI):
    """Create the database query agent"""
    tools = [
        get_database_schema,
        text_to_sql,
        execute_sql,
        explain_query
    ]
    
    return create_react_agent(
        llm,
        tools,
        state_modifier=DB_TEAM_PROMPT
    )
