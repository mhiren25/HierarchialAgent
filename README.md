# Hierarchical LangGraph Teams Agent System

A sophisticated multi-agent system built with LangGraph that coordinates specialized teams for log analysis, knowledge retrieval, and database queries.

## Architecture

```
Supervisor Agent
├── Log Investigation Team (compares orders, analyzes failures)
├── Knowledge Team (RAG with vector database)
└── Database Team (NLP to SQL conversion)
```

## Features

- **Hierarchical Agent System**: Supervisor coordinates specialized sub-teams
- **Multi-Order Log Comparison**: Compare good vs bad orders with detailed analysis and date support
- **RAG Knowledge Base**: Semantic search over documentation
- **Natural Language to SQL**: Convert questions to database queries
- **Conversation Continuity**: Multi-turn conversations with context preservation
- **Real-time Streaming**: WebSocket support for live updates
- **Live Agent Communication**: Visual representation of agents working together in real-time
- **Beautiful Modern UI**: Gradient designs, smooth animations, responsive layout
- **Agent Activity Visualization**: See which agents are active and their execution flow
- **Custom Styling**: Tailwind CSS with custom animations and themes

## Project Structure

```
langgraph-teams/
├── backend/
│   ├── supervisor_agent.py      # Main supervisor with routing
│   ├── log_team.py              # Log investigation agent
│   ├── knowledge_team.py        # RAG knowledge agent
│   ├── db_team.py               # Database query agent
│   ├── main.py                  # FastAPI server
│   ├── requirements.txt
│   └── .env
└── frontend/
    ├── src/
    │   └── App.jsx              # React application
    ├── package.json
    └── vite.config.js
```

## Setup Instructions

### Backend Setup

1. **Create virtual environment**:
```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. **Install dependencies**:
```bash
pip install -r requirements.txt

# Verify all dependencies installed correctly (includes python-dateutil for date parsing)
python check_dependencies.py
```

3. **Configure environment**:
```bash
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY
```

4. **Run the server**:
```bash
python main.py
# Or with uvicorn:
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`

### Frontend Setup

1. **Install dependencies**:
```bash
cd frontend
npm install
# or
yarn install
```

2. **Ensure you have all required files**:
```
frontend/
├── src/
│   ├── App.jsx              # Main React component
│   ├── main.jsx             # React entry point
│   └── index.css            # Tailwind CSS + custom styles
├── index.html               # HTML entry point
├── package.json
├── vite.config.js
├── tailwind.config.js       # Tailwind configuration
└── postcss.config.js        # PostCSS configuration
```

3. **Start development server**:
```bash
npm run dev
# or
yarn dev
```

The UI will be available at `http://localhost:5173`

### Quick Setup (Unix/Linux/Mac)

```bash
chmod +x setup.sh
./setup.sh
```

The setup script will:
- Create virtual environment
- Install all dependencies
- Set up configuration files
- Display next steps

## API Endpoints

### HTTP Endpoints

- `POST /chat` - Send chat message
  ```json
  {
    "message": "Compare orders GOOD001 and BAD001",
    "thread_id": "optional_thread_id"
  }
  ```

- `GET /threads` - List all conversation threads
- `GET /threads/{thread_id}` - Get specific thread history
- `DELETE /threads/{thread_id}` - Delete a thread
- `GET /debug/agent-graph` - View agent graph structure

### WebSocket

- `WS /ws/{thread_id}` - Stream agent execution in real-time

## Usage Examples

### 1. Log Analysis

```
"Compare orders GOOD001 and BAD001"
"Analyze the failure for order BAD001"
"What went wrong with order BAD001?"

# With date support:
"Compare GOOD001 from yesterday and BAD001 from today"
"Analyze order BAD001 on 2025-10-18"
"Check GOOD001 on October 18th and GOOD002 on October 19th"
"Compare GOOD001 from 2025-10-15 with BAD001 from 2025-10-18"
"Show me order GOOD001 from last Monday"
```Analyze the failure for order BAD001"
"What went wrong with order BAD001?"
```

### 2. Knowledge Base Queries

```
"What causes InsufficientInventoryError?"
"Explain the order processing workflow"
"What are the payment timeout thresholds?"
"How do I troubleshoot failed orders?"
```

### 3. Database Queries

```
"Show me all failed orders"
"What products have low inventory?"
"Calculate total revenue for completed orders"
"Which customers have the most orders?"
```

### 4. Multi-Agent Workflows

```
"Compare orders GOOD001 and BAD001, then check the documentation for the error codes found"
"Show me failed orders and explain what each error means"
```

## Agent Teams

### Log Investigation Team

**Tools**:
- `fetch_order_logs`: Retrieve logs for specific orders
- `compare_order_execution`: Side-by-side order comparison
- `analyze_failure_pattern`: Deep dive into failure root causes

**Capabilities**:
- Timeline analysis with timestamps
- Error and warning detection
- Performance metrics (duration analysis)
- Root cause identification
- Multi-order comparison

### Knowledge Team

**Tools**:
- `search_knowledge_base`: Semantic search across docs
- `search_by_document_type`: Filter by doc category
- `get_troubleshooting_guide`: Error-specific solutions
- `get_configuration_info`: System settings and thresholds

**Document Types**:
- Workflow documentation
- Error troubleshooting guides
- System configuration
- Payment processing rules
- Monitoring and observability

### Database Team

**Tools**:
- `get_database_schema`: View table structures
- `text_to_sql`: Convert natural language to SQL
- `execute_sql`: Run queries and return results
- `explain_query`: Validate SQL and view execution plan

**Database Schema**:
- `orders`: Order records with status
- `order_items`: Line items for orders
- `inventory`: Product stock levels
- `system_logs`: Event logs with timing

## Customization

### Adding New Tools

1. Define tool in respective team file:
```python
@tool
def my_custom_tool(param: str) -> str:
    """Tool description"""
    # Implementation
    return result
```

2. Add to agent creation:
```python
tools = [...existing_tools, my_custom_tool]
```

### Adding New Teams

1. Create new team file (e.g., `email_team.py`)
2. Import in `supervisor_agent.py`
3. Add to supervisor's team members list
4. Update routing logic

### Modifying Vector Store

Replace FAISS with production vector DB:

```python
# In knowledge_team.py
from langchain_pinecone import Pinecone

vector_store = Pinecone.from_documents(
    documents,
    embeddings,
    index_name="your-index"
)
```

## Monitoring and Debugging

### Enable LangSmith Tracing

Add to `.env`:
```bash
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=your_langsmith_key
LANGCHAIN_PROJECT=langgraph-teams
```

### View Agent Graph

```bash
curl http://localhost:8000/debug/agent-graph
```

### Check Agent Execution Path

The frontend displays the agent execution path for each response, showing which teams were invoked.

## Production Deployment

### Backend

1. **Use production WSGI server**:
```bash
gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker
```

2. **Environment variables**:
- Set `DEBUG=False`
- Configure proper `CORS_ORIGINS`
- Use secrets management for API keys

3. **Database**: Replace SQLite with PostgreSQL/MySQL
4. **Vector Store**: Use managed service (Pinecone, Weaviate)
5. **Caching**: Add Redis for conversation state

### Frontend

```bash
npm run build
# Deploy to Vercel, Netlify, or serve static files
```

## Troubleshooting

### Issue: "Agent system not initialized"
- Check OpenAI API key in `.env`
- Ensure `OPENAI_API_KEY` is set correctly

### Issue: "Vector store not available"
- Check OpenAI embeddings API access
- Verify network connectivity

### Issue: CORS errors
- Add frontend URL to `CORS_ORIGINS` in backend
- Check backend URL in frontend code

### Issue: Slow responses
- Reduce `top_k` in knowledge searches
- Use `gpt-4o-mini` instead of `gpt-4`
- Implement caching for repeated queries

## Performance Tips

1. **Use streaming** for better UX with WebSocket endpoint
2. **Cache vector embeddings** to reduce API calls
3. **Limit conversation history** passed to agents
4. **Use async operations** for parallel tool execution
5. **Implement rate limiting** to prevent abuse

## License

MIT License - Feel free to modify and use for your projects!

## Contributing

Contributions welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Submit a pull request

## Support

For issues and questions:
- Check the troubleshooting section
- Review LangGraph documentation: https://langchain-ai.github.io/langgraph/
- Open an issue on GitHub

---

Built with ❤️ using LangGraph, FastAPI, and React
