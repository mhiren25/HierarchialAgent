"""
Log Investigation Team - Analyzes logs and compares orders
"""
from typing import List, Dict, Any, Optional
from langchain_core.tools import tool
from langchain_core.messages import SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
import json
import re
from datetime import datetime, timedelta
from dateutil import parser as date_parser

# Log investigation tools
@tool
def fetch_order_logs(order_id: str, order_date: str = None) -> str:
    """
    Fetch system logs for a specific order ID on a given date.
    
    Args:
        order_id: The order identifier to fetch logs for
        order_date: Optional date in format YYYY-MM-DD or natural language. If not provided, uses current date.
        
    Returns:
        JSON string containing log entries for the order
    """
    # Parse the date
    if order_date:
        try:
            parsed_date = date_parser.parse(order_date)
        except:
            parsed_date = datetime.now()
    else:
        parsed_date = datetime.now()
    
    date_str = parsed_date.strftime('%Y-%m-%d')
    
    # Mock logs with dynamic dates - replace with actual log service (ELK, Splunk, CloudWatch, etc.)
    # Generate timestamps based on the provided date
    base_time = parsed_date.replace(hour=10, minute=0, second=0, microsecond=0)
    
    mock_logs = {
        "GOOD001": {
            "order_id": "GOOD001",
            "order_date": date_str,
            "status": "completed",
            "events": [
                {"timestamp": (base_time).isoformat() + "Z", "event": "order_created", "status": "success", "duration_ms": 45},
                {"timestamp": (base_time + timedelta(seconds=15)).isoformat() + "Z", "event": "payment_validated", "status": "success", "duration_ms": 230},
                {"timestamp": (base_time + timedelta(seconds=45)).isoformat() + "Z", "event": "inventory_reserved", "status": "success", "duration_ms": 120},
                {"timestamp": (base_time + timedelta(minutes=1, seconds=30)).isoformat() + "Z", "event": "order_fulfilled", "status": "success", "duration_ms": 450},
                {"timestamp": (base_time + timedelta(minutes=5)).isoformat() + "Z", "event": "shipment_created", "status": "success", "duration_ms": 890}
            ],
            "errors": [],
            "warnings": [],
            "total_duration_ms": 1735
        },
        "BAD001": {
            "order_id": "BAD001",
            "order_date": date_str,
            "status": "failed",
            "events": [
                {"timestamp": (base_time + timedelta(hours=1)).isoformat() + "Z", "event": "order_created", "status": "success", "duration_ms": 52},
                {"timestamp": (base_time + timedelta(hours=1, seconds=12)).isoformat() + "Z", "event": "payment_validated", "status": "success", "duration_ms": 245},
                {"timestamp": (base_time + timedelta(hours=1, minutes=1, seconds=30)).isoformat() + "Z", "event": "inventory_check", "status": "failed", "duration_ms": 78000}
            ],
            "errors": [
                {
                    "timestamp": (base_time + timedelta(hours=1, minutes=1, seconds=30)).isoformat() + "Z",
                    "error_code": "INV_001",
                    "error": "InsufficientInventoryError", 
                    "message": "Product SKU-456 out of stock. Available: 0, Requested: 1",
                    "stack_trace": "inventory_service.reserve() line 234"
                }
            ],
            "warnings": [
                {
                    "timestamp": (base_time + timedelta(hours=1, minutes=1, seconds=28)).isoformat() + "Z",
                    "warning": "InventoryLow", 
                    "message": "Product SKU-456 stock critically low (0 units remaining)"
                }
            ],
            "total_duration_ms": 78297
        },
        "GOOD002": {
            "order_id": "GOOD002",
            "order_date": date_str,
            "status": "completed",
            "events": [
                {"timestamp": (base_time + timedelta(hours=2)).isoformat() + "Z", "event": "order_created", "status": "success", "duration_ms": 48},
                {"timestamp": (base_time + timedelta(hours=2, seconds=18)).isoformat() + "Z", "event": "payment_validated", "status": "success", "duration_ms": 198},
                {"timestamp": (base_time + timedelta(hours=2, seconds=55)).isoformat() + "Z", "event": "inventory_reserved", "status": "success", "duration_ms": 145},
                {"timestamp": (base_time + timedelta(hours=2, minutes=2, seconds=10)).isoformat() + "Z", "event": "order_fulfilled", "status": "success", "duration_ms": 520}
            ],
            "errors": [],
            "warnings": [],
            "total_duration_ms": 911
        }
    }
    
    result = mock_logs.get(order_id, {
        "error": f"Order {order_id} not found in logs",
        "searched_date": date_str
    })
    return json.dumps(result, indent=2)

@tool
def compare_order_execution(order_specs: str) -> str:
    """
    Compare execution paths of multiple orders to identify differences.
    Supports orders from same or different dates.
    
    Args:
        order_specs: JSON string with order specifications. Format:
                    '[{"order_id": "GOOD001", "date": "2025-10-18"}, {"order_id": "BAD001", "date": "2025-10-19"}]'
                    Or simple comma-separated: "GOOD001,BAD001" (uses current date for all)
        
    Returns:
        JSON string with detailed comparison analysis
    """
    # Parse order specifications
    try:
        # Try parsing as JSON first
        specs = json.loads(order_specs)
        if isinstance(specs, list):
            order_list = specs
        else:
            order_list = [specs]
    except json.JSONDecodeError:
        # Fallback to comma-separated format
        ids = [oid.strip() for oid in order_specs.split(",")]
        order_list = [{"order_id": oid, "date": None} for oid in ids]
    
    all_logs = {}
    order_dates = {}
    
    for spec in order_list:
        if isinstance(spec, dict):
            order_id = spec.get("order_id")
            date = spec.get("date")
        else:
            order_id = spec
            date = None
        
        log_data = json.loads(fetch_order_logs.invoke({"order_id": order_id, "order_date": date}))
        all_logs[order_id] = log_data
        order_dates[order_id] = log_data.get("order_date", "unknown")
    
    comparison = {
        "orders_compared": list(all_logs.keys()),
        "order_dates": order_dates,
        "same_day_comparison": len(set(order_dates.values())) == 1,
        "execution_summary": {},
        "key_differences": [],
        "timing_analysis": {},
        "failure_points": []
    }
    
    # Analyze each order
    for order_id, logs in all_logs.items():
        if "error" not in logs:
            comparison["execution_summary"][order_id] = {
                "order_date": logs.get("order_date"),
                "status": logs.get("status"),
                "total_events": len(logs.get("events", [])),
                "total_duration_ms": logs.get("total_duration_ms", 0),
                "error_count": len(logs.get("errors", [])),
                "warning_count": len(logs.get("warnings", []))
            }
            
            # Track timing
            comparison["timing_analysis"][order_id] = {
                "order_date": logs.get("order_date"),
                "duration_ms": logs.get("total_duration_ms", 0),
                "avg_event_duration": logs.get("total_duration_ms", 0) / max(len(logs.get("events", [])), 1)
            }
            
            # Track failures
            if logs.get("status") == "failed":
                comparison["failure_points"].append({
                    "order_id": order_id,
                    "order_date": logs.get("order_date"),
                    "failed_at": logs["events"][-1]["event"] if logs.get("events") else "unknown",
                    "errors": logs.get("errors", []),
                    "warnings": logs.get("warnings", [])
                })
    
    # Identify differences
    if len(all_logs) >= 2:
        events_by_order = {
            oid: [e["event"] for e in logs.get("events", [])]
            for oid, logs in all_logs.items()
            if "error" not in logs
        }
        
        all_events = set()
        for events in events_by_order.values():
            all_events.update(events)
        
        for event in all_events:
            present_in = [oid for oid, events in events_by_order.items() if event in events]
            if len(present_in) != len(events_by_order):
                comparison["key_differences"].append({
                    "event": event,
                    "present_in": present_in,
                    "missing_from": [oid for oid in events_by_order.keys() if oid not in present_in]
                })
    
    # Add date-based insights
    if not comparison["same_day_comparison"]:
        comparison["date_insights"] = {
            "note": "Orders are from different dates - comparing cross-day patterns",
            "dates_analyzed": list(set(order_dates.values()))
        }
    
    return json.dumps(comparison, indent=2)

@tool
def analyze_failure_pattern(order_id: str, order_date: str = None) -> str:
    """
    Deep analysis of failure patterns for a specific order.
    
    Args:
        order_id: Order ID to analyze
        order_date: Optional date in format YYYY-MM-DD or natural language. If not provided, uses current date.
        
    Returns:
        JSON string with failure analysis and root cause
    """
    logs = json.loads(fetch_order_logs.invoke({"order_id": order_id, "order_date": order_date}))
    
    if "error" in logs:
        return json.dumps({"error": logs["error"]})
    
    analysis = {
        "order_id": order_id,
        "order_date": logs.get("order_date"),
        "root_cause": None,
        "error_timeline": [],
        "performance_issues": [],
        "recommendations": []
    }
    
    # Analyze errors
    if logs.get("errors"):
        analysis["root_cause"] = logs["errors"][0]
        analysis["error_timeline"] = logs["errors"]
        
        for error in logs["errors"]:
            if "Insufficient" in error.get("message", ""):
                analysis["recommendations"].append(
                    "Check inventory levels and reorder thresholds"
                )
            elif "timeout" in error.get("message", "").lower():
                analysis["recommendations"].append(
                    "Investigate system performance and database query times"
                )
    
    # Analyze performance
    for event in logs.get("events", []):
        if event.get("duration_ms", 0) > 5000:  # Over 5 seconds
            analysis["performance_issues"].append({
                "event": event["event"],
                "timestamp": event.get("timestamp"),
                "duration_ms": event["duration_ms"],
                "severity": "high" if event["duration_ms"] > 30000 else "medium"
            })
    
    # Analyze warnings
    if logs.get("warnings"):
        analysis["warnings_detected"] = logs["warnings"]
        analysis["recommendations"].append(
            "Address warnings before they escalate to errors"
        )
    
    return json.dumps(analysis, indent=2)

def extract_order_info_from_text(text: str) -> List[Dict[str, str]]:
    """
    Extract order IDs and dates from natural language text.
    
    Examples:
        "Compare GOOD001 from yesterday and BAD001 from today"
        "Analyze GOOD001 on 2025-10-18 vs BAD001 on 2025-10-19"
        "Check orders GOOD001, BAD001" (uses current date)
    """
    order_pattern = r'\b([A-Z]+\d+)\b'
    order_ids = re.findall(order_pattern, text)
    
    # Try to extract dates
    date_patterns = [
        r'(\d{4}-\d{2}-\d{2})',  # YYYY-MM-DD
        r'(today|yesterday|tomorrow)',  # Relative dates
        r'(last\s+\w+|this\s+\w+)',  # last week, this month, etc.
    ]
    
    dates_found = []
    for pattern in date_patterns:
        dates_found.extend(re.findall(pattern, text, re.IGNORECASE))
    
    # Match orders with dates if possible
    order_specs = []
    for i, order_id in enumerate(order_ids):
        if i < len(dates_found):
            order_specs.append({
                "order_id": order_id,
                "date": dates_found[i]
            })
        else:
            order_specs.append({
                "order_id": order_id,
                "date": None  # Will use current date
            })
    
    return order_specs

LOG_TEAM_PROMPT = """You are a Log Investigation Specialist with expertise in distributed systems debugging.

**Your Responsibilities:**
1. Fetch and analyze system logs for specific orders
2. Compare execution paths between successful and failed orders (same or different dates)
3. Identify root causes of failures with precise error tracking
4. Provide actionable recommendations

**Available Tools:**
- fetch_order_logs: Retrieve complete log data for an order with optional date
  * Accepts natural language dates: "today", "yesterday", "2025-10-18"
  * Defaults to current date if not specified
  
- compare_order_execution: Side-by-side comparison of multiple orders
  * Can compare orders from same or different dates
  * Accepts JSON format: [{"order_id": "GOOD001", "date": "2025-10-18"}, {"order_id": "BAD001", "date": "2025-10-19"}]
  * Or simple format: "GOOD001,BAD001" (uses current date for all)
  
- analyze_failure_pattern: Deep dive into failure root causes with date support

**Date Handling:**
- Extract dates from user queries (e.g., "yesterday", "2025-10-18", "last week")
- If no date specified, use current date (today)
- Support comparing orders from different dates to identify date-specific patterns
- Always include order_date in your analysis summary

**Analysis Approach:**
1. Extract order IDs and dates from user queries
2. For single orders: Fetch logs with date and analyze timeline
3. For multiple orders: Compare execution paths, note if different dates
4. Always provide: Timeline with dates, errors, warnings, duration analysis, and recommendations

**Output Format:**
- Clear timeline of events with timestamps and dates
- Highlighted failure points
- Performance metrics
- Date-based insights (if comparing across dates)
- Root cause analysis
- Actionable recommendations

**Example Queries:**
- "Compare GOOD001 from yesterday and BAD001 from today"
- "Analyze order BAD001 on 2025-10-18"
- "Compare GOOD001 and BAD001" (uses current date for both)
"""

def create_log_agent(llm: ChatOpenAI):
    """Create the log investigation agent"""
    tools = [fetch_order_logs, compare_order_execution, analyze_failure_pattern]
    
    return create_react_agent(
        llm,
        tools,
        state_modifier=LOG_TEAM_PROMPT
    )
