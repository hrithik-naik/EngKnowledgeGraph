# chat/chat.py - Simple approach with manual tool mapping (1 LLM call per query)
import os
import re
from typing import Optional
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage

# Import your query engine
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from graph.query import QueryEngine


# Initialize Query Engine
def get_query_engine():
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "password")
    return QueryEngine(uri=uri, user=user, password=password)


engine = get_query_engine()


# Initialize Groq model
def get_llm():
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY environment variable not set")
    
    llm = ChatGroq(
        api_key=api_key,
        model="llama-3.1-8b-instant",
        temperature=0
    )
    return llm


# Helper functions that execute graph queries
def execute_query(intent: str, params: dict) -> dict:
    """
    Execute the appropriate graph query based on intent.
    
    Args:
        intent: The type of query (ownership, dependency, blast_radius, etc.)
        params: Parameters for the query
    
    Returns:
        Query results
    """
    try:
        if intent == "get_owner":
            node_id = params.get("node_id")
            owner = engine.get_owner(node_id)
            if owner:
                return {"success": True, "owner": owner}
            return {"success": False, "message": f"No owner found for {node_id}"}
        
        elif intent == "list_nodes":
            node_type = params.get("type", "service")
            nodes = engine.get_nodes(type=node_type)
            return {"success": True, "nodes": nodes, "count": len(nodes)}
        
        elif intent == "downstream":
            node_id = params.get("node_id")
            deps = engine.downstream(node_id)
            return {"success": True, "dependencies": deps, "count": len(deps)}
        
        elif intent == "upstream":
            node_id = params.get("node_id")
            deps = engine.upstream(node_id)
            return {"success": True, "dependents": deps, "count": len(deps)}
        
        elif intent == "blast_radius":
            node_id = params.get("node_id")
            result = engine.blast_radius(node_id)
            if result:
                return {"success": True, "blast_radius": result}
            return {"success": False, "message": f"Node {node_id} not found"}
        
        elif intent == "find_path":
            from_id = params.get("from_id")
            to_id = params.get("to_id")
            path = engine.path(from_id, to_id)
            if path:
                return {"success": True, "path": path}
            return {"success": False, "message": f"No path found between {from_id} and {to_id}"}
        
        elif intent == "get_node":
            node_id = params.get("node_id")
            node = engine.get_node(node_id)
            if node:
                return {"success": True, "node": node}
            return {"success": False, "message": f"Node {node_id} not found"}
        
        elif intent == "team_owns":
            team_name = params.get("team_name")
            # Get team node first
            team_id = f"team-{team_name}"
            # Get all nodes and filter by owner
            services = engine.get_nodes(type="service")
            databases = engine.get_nodes(type="database")
            caches = engine.get_nodes(type="cache")
            
            owned = []
            for node_list in [services, databases, caches]:
                for node in node_list:
                    owner = engine.get_owner(node["id"])
                    if owner and owner["id"] == team_id:
                        owned.append(node)
            
            return {"success": True, "owned": owned, "count": len(owned)}
        
        else:
            return {"success": False, "message": f"Unknown intent: {intent}"}
            
    except Exception as e:
        return {"success": False, "error": str(e)}


# Parse query and determine intent
def parse_query_intent(query: str, conversation_history: list = None) -> dict:
    """
    Use LLM to parse the query and extract intent + parameters.
    This makes only ONE LLM call to understand the query.
    
    Args:
        query: Natural language query
        conversation_history: Previous conversation for context
    
    Returns:
        Dictionary with intent and parameters
    """
    llm = get_llm()
    
    # Build context from conversation history
    context = ""
    if conversation_history:
        context = "Previous conversation:\n"
        for msg in conversation_history[-3:]:  # Last 3 messages for context
            context += f"{msg['role']}: {msg['content']}\n"
    
    system_prompt = """You are a query parser for an Engineering Knowledge Graph system.

Your job is to analyze the user's question and output a JSON object with:
1. "intent": The type of query (one of: get_owner, list_nodes, downstream, upstream, blast_radius, find_path, get_node, team_owns)
2. "params": Parameters needed for the query

Node ID patterns:
- Services: service-<name> (e.g., service-order-service, service-payment-service)
- Databases: database-<name> (e.g., database-payments-db, database-orders-db)
- Caches: cache-<name> (e.g., cache-redis-main)
- Teams: team-<name> (e.g., team-platform-team, team-payments-team)

Examples:

Query: "Who owns the payment service?"
Output: {"intent": "get_owner", "params": {"node_id": "service-payment-service"}}

Query: "List all databases"
Output: {"intent": "list_nodes", "params": {"type": "database"}}

Query: "What does order-service depend on?"
Output: {"intent": "downstream", "params": {"node_id": "service-order-service"}}

Query: "What breaks if redis-main goes down?"
Output: {"intent": "blast_radius", "params": {"node_id": "cache-redis-main"}}

Query: "What depends on users-db?"
Output: {"intent": "upstream", "params": {"node_id": "database-users-db"}}

Query: "How does api-gateway connect to payments-db?"
Output: {"intent": "find_path", "params": {"from_id": "service-api-gateway", "to_id": "database-payments-db"}}

Query: "What does platform-team own?"
Output: {"intent": "team_owns", "params": {"team_name": "platform-team"}}

Query: "Show me all services"
Output: {"intent": "list_nodes", "params": {"type": "service"}}

Now parse this query and return ONLY valid JSON, nothing else:"""
    
    user_message = f"{context}\nUser query: {query}"
    
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_message)
    ]
    
    try:
        response = llm.invoke(messages)
        content = response.content.strip()
        
        # Extract JSON from response (in case LLM adds extra text)
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            import json
            parsed = json.loads(json_match.group())
            return parsed
        else:
            return {"intent": "unknown", "params": {}, "raw_response": content}
            
    except Exception as e:
        return {"intent": "error", "params": {}, "error": str(e)}


# Format the results into natural language
def format_response(query: str, intent: dict, results: dict) -> str:
    """
    Format query results into a natural language response.
    
    Args:
        query: Original query
        intent: Parsed intent
        results: Query results
    
    Returns:
        Formatted response string
    """
    if not results.get("success"):
        return f"❌ {results.get('message', results.get('error', 'Query failed'))}"
    
    intent_type = intent.get("intent")
    
    if intent_type == "get_owner":
        owner = results["owner"]
        return f"The {intent['params']['node_id'].replace('service-', '').replace('database-', '').replace('cache-', '')} is owned by **{owner['name']}** (lead: {owner.get('lead', 'N/A')}, Slack: {owner.get('slack_channel', 'N/A')})."
    
    elif intent_type == "list_nodes":
        nodes = results["nodes"]
        node_type = intent["params"].get("type", "node")
        if not nodes:
            return f"No {node_type}s found in the knowledge graph."
        
        response = f"Found {len(nodes)} {node_type}(s):\n"
        for node in nodes:
            response += f"- **{node['name']}** (ID: {node['id']})\n"
        return response
    
    elif intent_type == "downstream":
        deps = results["dependencies"]
        node_id = intent["params"]["node_id"]
        if not deps:
            return f"{node_id} has no downstream dependencies."
        
        response = f"{node_id} depends on {len(deps)} resource(s):\n"
        for dep in deps:
            response += f"- **{dep['name']}** ({dep['type']})\n"
        return response
    
    elif intent_type == "upstream":
        deps = results["dependents"]
        node_id = intent["params"]["node_id"]
        if not deps:
            return f"Nothing depends on {node_id}."
        
        response = f"{len(deps)} resource(s) depend on {node_id}:\n"
        for dep in deps:
            response += f"- **{dep['name']}** ({dep['type']})\n"
        return response
    
    elif intent_type == "blast_radius":
        blast = results["blast_radius"]
        node = blast["node"]
        
        response = f"**Blast Radius Analysis for {node['name']}:**\n\n"
        response += f"📊 **Impact Summary:**\n"
        response += f"- Downstream dependencies: {len(blast['downstream'])}\n"
        response += f"- Upstream dependents: {len(blast['upstream'])}\n"
        response += f"- Affected teams: {len(blast['teams'])}\n\n"
        
        if blast['upstream']:
            response += f"⚠️ **Services that will break:**\n"
            for svc in blast['upstream'][:5]:  # Show top 5
                response += f"- {svc['name']}\n"
        
        if blast['teams']:
            response += f"\n👥 **Teams to notify:**\n"
            for team in blast['teams']:
                response += f"- {team['name']} (lead: {team.get('lead', 'N/A')})\n"
        
        return response
    
    elif intent_type == "find_path":
        path = results["path"]
        response = f"**Path found:**\n"
        response += " → ".join(path["nodes"])
        return response
    
    elif intent_type == "team_owns":
        owned = results["owned"]
        team_name = intent["params"]["team_name"]
        if not owned:
            return f"Team {team_name} doesn't own any resources."
        
        response = f"**{team_name}** owns {len(owned)} resource(s):\n"
        for resource in owned:
            response += f"- **{resource['name']}** ({resource['type']})\n"
        return response
    
    elif intent_type == "get_node":
        node = results["node"]
        response = f"**{node['name']}** ({node['type']})\n"
        response += f"ID: {node['id']}\n"
        if node.get('metadata'):
            response += f"Metadata: {node['metadata']}\n"
        return response
    
    else:
        return f"Query executed successfully. Results: {results}"


# Main query function - ONLY 1 LLM CALL!
def query_knowledge_graph(query: str, conversation_history: list = None) -> dict:
    """
    Process a natural language query against the knowledge graph.
    Makes only ONE LLM call to parse intent, then executes the query directly.
    
    Args:
        query: Natural language query
        conversation_history: Optional list of previous messages for context
    
    Returns:
        Dictionary containing the answer and metadata
    """
    try:
        # Step 1: Parse intent (1 LLM call)
        intent = parse_query_intent(query, conversation_history)
        
        if intent.get("intent") == "error":
            return {
                "success": False,
                "answer": f"Failed to parse query: {intent.get('error')}",
                "error": intent.get("error")
            }
        
        if intent.get("intent") == "unknown":
            return {
                "success": False,
                "answer": "I couldn't understand your query. Please try rephrasing it.",
                "error": "UNKNOWN_INTENT"
            }
        
        # Step 2: Execute query (no LLM call)
        results = execute_query(intent["intent"], intent["params"])
        
        # Step 3: Format response (no LLM call)
        answer = format_response(query, intent, results)
        
        return {
            "success": True,
            "answer": answer,
            "intent": intent,
            "tool_calls_made": 1  # Only 1 LLM call for parsing
        }
        
    except Exception as e:
        return {
            "success": False,
            "answer": f"An error occurred: {str(e)}",
            "error": str(e)
        }


# Simple test function
if __name__ == "__main__":
    test_queries = [
        "Who owns the payment service?",
        "What does order-service depend on?",
        "List all databases",
        "What breaks if redis-main goes down?",
    ]
    
    print("Testing Knowledge Graph Agent (1 LLM call per query)...\n")
    
    for i, query in enumerate(test_queries, 1):
        print(f"Q{i}: {query}")
        result = query_knowledge_graph(query)
        
        if result['success']:
            print(f"✅ {result['answer']}\n")
        else:
            print(f"❌ {result['error']}\n")
        
        print("-" * 80)