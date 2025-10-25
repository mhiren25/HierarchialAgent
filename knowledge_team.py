"""
Knowledge Team - RAG with Vector Database
"""
from typing import List, Dict, Any
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langgraph.prebuilt import create_react_agent
import json

# Initialize vector store with sample documents
_vector_store = None

def get_vector_store():
    """Initialize and return vector store with knowledge base"""
    global _vector_store
    
    if _vector_store is not None:
        return _vector_store
    
    # Sample knowledge base documents
    sample_docs = [
        Document(
            page_content="""Order Processing Workflow:
1. Order Creation: Customer submits order through API or UI
2. Payment Validation: 3DS authentication for orders >$500
3. Inventory Check: System reserves items from available stock
4. Fulfillment: Warehouse picks and packs items
5. Shipment: Carrier label generation and tracking
6. Completion: Order marked as shipped, customer notified

Common timeout values:
- Payment: 30 seconds
- Inventory reservation: 5 minutes
- Fulfillment: 2 hours""",
            metadata={"source": "order_process_guide.pdf", "type": "workflow", "version": "2.1"}
        ),
        Document(
            page_content="""Common Order Failures and Solutions:

InsufficientInventoryError (INV_001):
- Cause: Requested quantity exceeds available stock
- Solution: Check inventory levels, update stock, or notify customer
- Prevention: Set reorder thresholds, enable backorder options

PaymentDeclinedError (PAY_002):
- Cause: Card declined, insufficient funds, or fraud detection
- Solution: Request alternative payment method
- Prevention: Pre-authorization checks, fraud scoring

TimeoutError (SYS_003):
- Cause: External service not responding within timeout window
- Solution: Retry with exponential backoff
- Prevention: Increase timeout values, implement circuit breakers

AddressValidationError (ADDR_004):
- Cause: Invalid or undeliverable shipping address
- Solution: Request address correction from customer
- Prevention: Real-time address validation during checkout""",
            metadata={"source": "troubleshooting_guide.pdf", "type": "errors", "version": "3.0"}
        ),
        Document(
            page_content="""System Configuration and Thresholds:

Inventory Management:
- Reorder threshold: When available quantity < 20 units
- Critical stock level: Less than 5 units
- Reservation timeout: 5 minutes (300 seconds)
- Auto-release: Reserved items released if order not completed

Performance Targets:
- API response time: < 200ms (p95)
- Payment processing: < 2 seconds (p99)
- Order placement: < 5 seconds end-to-end
- Database query: < 100ms (p95)

Alert Thresholds:
- Error rate: > 1% triggers warning
- Response time: > 500ms triggers investigation
- Queue depth: > 1000 messages triggers scaling""",
            metadata={"source": "system_config.pdf", "type": "configuration", "version": "4.2"}
        ),
        Document(
            page_content="""Payment Processing Guidelines:

3D Secure (3DS) Authentication:
- Required for: Transactions over $500, high-risk customers
- Flow: Customer redirected to bank for verification
- Timeout: 5 minutes for customer to complete
- Failure handling: Order cancelled, customer notified

Payment Methods:
- Credit/Debit Cards: Visa, Mastercard, Amex
- Digital Wallets: PayPal, Apple Pay, Google Pay
- Bank Transfers: ACH (US), SEPA (EU)

Fraud Detection:
- Velocity checks: Max 3 orders per hour per customer
- CVV verification: Required for all card transactions
- Address verification: AVS check for billing address
- Risk scoring: Machine learning model scores each transaction""",
            metadata={"source": "payment_guide.pdf", "type": "payment", "version": "2.5"}
        ),
        Document(
            page_content="""Monitoring and Observability:

Key Metrics:
- Order success rate: Target > 99%
- Average order value: Track daily trends
- Cart abandonment rate: Target < 30%
- Fulfillment time: Target < 24 hours

System Health Indicators:
- API availability: Target 99.9% uptime
- Database connections: Monitor pool utilization
- Queue lag: Process messages within 1 minute
- Error logs: Analyze patterns for recurring issues

Alerting Rules:
- Critical: System down, payment gateway offline
- High: Error rate spike, performance degradation
- Medium: Individual order failures, timeout warnings
- Low: Inventory low, slow queries detected

Logging Best Practices:
- Include order_id in all log entries
- Log timestamps in ISO 8601 format
- Capture full error stack traces
- Tag logs by service and environment""",
            metadata={"source": "operations_manual.pdf", "type": "monitoring", "version": "1.8"}
        ),
    ]
    
    try:
        embeddings = OpenAIEmbeddings()
        _vector_store = FAISS.from_documents(sample_docs, embeddings)
        return _vector_store
    except Exception as e:
        print(f"Error initializing vector store: {e}")
        return None

@tool
def search_knowledge_base(query: str, top_k: int = 3) -> str:
    """
    Search the knowledge base using semantic similarity.
    
    Args:
        query: Natural language search query
        top_k: Number of top results to return (default: 3)
        
    Returns:
        JSON string with relevant documents and metadata
    """
    vector_store = get_vector_store()
    if not vector_store:
        return json.dumps({"error": "Knowledge base not available"})
    
    try:
        results = vector_store.similarity_search_with_score(query, k=top_k)
        
        formatted_results = {
            "query": query,
            "results_count": len(results),
            "documents": []
        }
        
        for i, (doc, score) in enumerate(results):
            formatted_results["documents"].append({
                "rank": i + 1,
                "content": doc.page_content,
                "metadata": doc.metadata,
                "relevance_score": round(1 - score, 3)  # Convert distance to similarity
            })
        
        return json.dumps(formatted_results, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})

@tool
def search_by_document_type(doc_type: str, query: str = None) -> str:
    """
    Search knowledge base filtered by document type.
    
    Args:
        doc_type: Type of document (workflow, errors, configuration, payment, monitoring)
        query: Optional search query within the document type
        
    Returns:
        JSON string with matching documents
    """
    vector_store = get_vector_store()
    if not vector_store:
        return json.dumps({"error": "Knowledge base not available"})
    
    try:
        # Get all documents
        if query:
            all_docs = vector_store.similarity_search(query, k=10)
        else:
            all_docs = vector_store.similarity_search("", k=100)
        
        # Filter by type
        filtered = [
            {
                "content": doc.page_content,
                "metadata": doc.metadata
            }
            for doc in all_docs
            if doc.metadata.get("type") == doc_type
        ]
        
        return json.dumps({
            "document_type": doc_type,
            "query": query,
            "results_count": len(filtered),
            "documents": filtered[:5]  # Limit to 5 results
        }, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})

@tool
def get_troubleshooting_guide(error_code: str = None) -> str:
    """
    Get troubleshooting information for specific error codes or general guide.
    
    Args:
        error_code: Optional error code to search for (e.g., INV_001, PAY_002)
        
    Returns:
        JSON string with troubleshooting information
    """
    if error_code:
        query = f"error code {error_code} troubleshooting solution"
    else:
        query = "common order failures troubleshooting"
    
    return search_knowledge_base.invoke({"query": query, "top_k": 2})

@tool
def get_configuration_info(config_topic: str) -> str:
    """
    Retrieve system configuration information.
    
    Args:
        config_topic: Configuration topic (inventory, performance, alerts, timeouts)
        
    Returns:
        JSON string with configuration details
    """
    query = f"{config_topic} configuration thresholds settings"
    return search_by_document_type.invoke({
        "doc_type": "configuration",
        "query": query
    })

KNOWLEDGE_TEAM_PROMPT = """You are a Knowledge Retrieval Specialist with access to comprehensive documentation.

**Your Responsibilities:**
1. Search documentation and troubleshooting guides
2. Retrieve system configuration information
3. Provide context on workflows and processes
4. Cite sources and document versions

**Available Tools:**
- search_knowledge_base: Semantic search across all documentation
- search_by_document_type: Filter by document type (workflow, errors, configuration, payment, monitoring)
- get_troubleshooting_guide: Get error-specific troubleshooting steps
- get_configuration_info: Retrieve configuration and threshold values

**Document Types Available:**
- Workflow: Order processing flows and procedures
- Errors: Common failures and solutions
- Configuration: System settings and thresholds
- Payment: Payment processing rules
- Monitoring: Observability and alerting

**Best Practices:**
1. Use semantic search for conceptual queries
2. Use filtered search for specific document types
3. Always cite source documents and versions
4. Provide relevant excerpts with context
5. Include actionable recommendations from docs"""

def create_knowledge_agent(llm: ChatOpenAI):
    """Create the knowledge retrieval agent"""
    tools = [
        search_knowledge_base,
        search_by_document_type,
        get_troubleshooting_guide,
        get_configuration_info
    ]
    
    return create_react_agent(
        llm,
        tools,
        state_modifier=KNOWLEDGE_TEAM_PROMPT
    )
