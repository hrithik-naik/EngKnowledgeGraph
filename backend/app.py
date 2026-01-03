# backend/app.py
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
import sys
import os

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from chat import query_knowledge_graph


app = FastAPI(title="EngKnowledgeGraph Backend")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class Message(BaseModel):
    role: str  # "user" or "assistant"
    content: str


class QueryRequest(BaseModel):
    query: str
    conversation_history: Optional[List[Message]] = None


class QueryResponse(BaseModel):
    answer: str
    success: bool
    tool_calls_made: Optional[int] = None
    error: Optional[str] = None


@app.get("/")
def root():
    api_key_set = bool(os.getenv("GOOGLE_API_KEY"))

    try:
        test_result = "eee"
    except Exception as e:
        test_result = str(e)

    return {
        "message": "Engineering Knowledge Graph API",
        "google_api_key_loaded": api_key_set,
        "chat_test_result": test_result,
        "endpoints": {
            "/query": "POST - Query the knowledge graph",
            "/health": "GET - Health check",
        },
    }


@app.get("/health")
def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "eng-knowledge-graph"}


@app.post("/query", response_model=QueryResponse)
def query_graph(request: QueryRequest):
    """
    Query the knowledge graph using natural language.
    
    The agent will automatically:
    - Parse the query intent
    - Call appropriate graph query functions
    - Handle edge cases (missing data, invalid queries)
    - Support follow-up questions using conversation history
    """
    try:
        # Convert conversation history to proper format
        history = None
        if request.conversation_history:
            history = [
                {"role": msg.role, "content": msg.content}
                for msg in request.conversation_history
            ]
        
        # Query the knowledge graph using the LangGraph agent
        result = query_knowledge_graph(
            query=request.query,
            conversation_history=history
        )
        
        return QueryResponse(
            answer=result["answer"],
            success=result["success"],
            tool_calls_made=result.get("tool_calls_made"),
            error=result.get("error")
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error processing query: {str(e)}"
        )


# Optional: Add endpoints for direct graph queries (for debugging)
@app.get("/debug/nodes/{node_type}")
def debug_get_nodes(node_type: str):
    """Debug endpoint to list all nodes of a specific type"""
    from graph.query import QueryEngine
    
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "password")
    
    engine = QueryEngine(uri=uri, user=user, password=password)
    
    try:
        nodes = engine.get_nodes(type=node_type)
        return {"type": node_type, "count": len(nodes), "nodes": nodes}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        engine.close()


