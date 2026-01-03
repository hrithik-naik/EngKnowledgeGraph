# backend/app.py

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="EngKnowledgeGraph Backend")


class QueryRequest(BaseModel):
    query: str


class QueryResponse(BaseModel):
    answer: str


@app.post("/query", response_model=QueryResponse)
def query_graph(request: QueryRequest):
    # Placeholder logic
    return QueryResponse(
        answer=f"Received query: {request.query}"
    )
