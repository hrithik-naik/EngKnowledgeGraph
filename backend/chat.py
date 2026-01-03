# chat/chat.py - Two-step approach: explicit intent extraction then execution
import os
import json
import re
from typing import Optional, List, Dict, Any
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


# Tool execution functions
def execute_get_owner(node_id: str) -> dict:
    """Get the team that owns a specific resource."""
    try:
        owner = engine.get_owner(node_id)
        if owner:
            return {"success": True, "owner": owner}
        return {"success": False, "message": f"No owner found for {node_id}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def execute_list_nodes(node_type: str = "service") -> dict:
    """List all nodes of a specific type."""
    try:
        nodes = engine.get_nodes(type=node_type)
        return {"success": True, "nodes": nodes, "count": len(nodes)}
    except Exception as e:
        return {"success": False, "error": str(e)}


def execute_get_downstream_dependencies(node_id: str) -> dict:
    """Get all resources that a node depends on."""
    try:
        deps = engine.downstream(node_id)
        return {"success": True, "dependencies": deps, "count": len(deps)}
    except Exception as e:
        return {"success": False, "error": str(e)}


def execute_get_upstream_dependents(node_id: str) -> dict:
    """Get all resources that depend on a specific node."""
    try:
        deps = engine.upstream(node_id)
        return {"success": True, "dependents": deps, "count": len(deps)}
    except Exception as e:
        return {"success": False, "error": str(e)}


def execute_calculate_blast_radius(node_id: str) -> dict:
    """Calculate the blast radius of a node."""
    try:
        result = engine.blast_radius(node_id)
        if result:
            return {"success": True, "blast_radius": result}
        return {"success": False, "message": f"Node {node_id} not found"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def execute_find_path(from_id: str, to_id: str) -> dict:
    """Find the dependency path between two nodes."""
    try:
        path = engine.path(from_id, to_id)
        if path:
            return {"success": True, "path": path}
        return {"success": False, "message": f"No path found between {from_id} and {to_id}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def execute_get_team_resources(team_name: str) -> dict:
    """Get all resources owned by a specific team."""
    try:
        if not team_name.startswith("team-"):
            team_id = f"team-{team_name}"
        else:
            team_id = team_name
        
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
    except Exception as e:
        return {"success": False, "error": str(e)}


def extract_tool_call(query: str, conversation_history: list = None) -> dict:
    """
    Use LLM to extract the tool call needed for the query.
    This is STEP 1 - only extract intent, don't execute yet.
    """
    llm = get_llm()
    
    # Build context
    context = ""
    if conversation_history:
        context = "Previous conversation for context:\n"
        for msg in conversation_history[-4:]:
            context += f"{msg['role']}: {msg['content']}\n"
        context += "\n"
    
    system_prompt = """You are a query intent extractor for an Engineering Knowledge Graph system.

Your ONLY job is to output a JSON object with the tool call needed. Nothing else.

Node ID patterns:
- Services: service-<name> (e.g., service-order-service, service-payment-service, service-api-gateway)
- Databases: database-<name> (e.g., database-orders-db, database-payments-db, database-users-db)
- Caches: cache-<name> (e.g., cache-redis-main)
- Teams: team-<name> (e.g., team-platform-team, team-orders-team)

Available tools and when to use them:

1. find_path - Find dependency path between two nodes
   Use for: "How does X connect to Y?", "What's between X and Y?", "Path from X to Y"
   Format: {"tool": "find_path", "params": {"from_id": "service-X", "to_id": "database-Y"}}

2. calculate_blast_radius - Calculate impact if node fails
   Use for: "What breaks if X fails?", "Blast radius of X", "What's affected if X goes down?"
   Format: {"tool": "calculate_blast_radius", "params": {"node_id": "cache-redis-main"}}

3. get_upstream_dependents - Get what depends on a node (what uses it)
   Use for: "What depends on X?", "What uses X?", "What services use X?", "If X fails what's affected?"
   Format: {"tool": "get_upstream_dependents", "params": {"node_id": "database-users-db"}}

4. get_downstream_dependencies - Get what a node depends on (what it uses)
   Use for: "What does X depend on?", "What does X use?", "What are X's dependencies?"
   Format: {"tool": "get_downstream_dependencies", "params": {"node_id": "service-order-service"}}

5. get_owner - Get team that owns a resource
   Use for: "Who owns X?", "Which team manages X?", "Who should I page if X is down?"
   Format: {"tool": "get_owner", "params": {"node_id": "service-payment-service"}}

6. list_nodes - List all nodes of a type
   Use for: "List all services", "Show all databases", "What teams are there?"
   Format: {"tool": "list_nodes", "params": {"node_type": "service"}}

7. get_team_resources - Get resources owned by a team
   Use for: "What does X team own?", "Show resources of X team", "What databases does X team manage?"
   Format: {"tool": "get_team_resources", "params": {"team_name": "platform-team"}}

IMPORTANT:
- Always use full node IDs with correct prefixes
- "order-service" → "service-order-service"
- "orders-db" → "database-orders-db"
- "redis" or "redis-main" → "cache-redis-main"
- "platform team" or "platform" → "team-platform-team"

Output ONLY valid JSON, no other text.

Examples:

Query: "How does api-gateway connect to orders-db?"
Output: {"tool": "find_path", "params": {"from_id": "service-api-gateway", "to_id": "database-orders-db"}}

Query: "What's between order-service and notification-service?"
Output: {"tool": "find_path", "params": {"from_id": "service-order-service", "to_id": "service-notification-service"}}

Query: "What breaks if redis goes down?"
Output: {"tool": "calculate_blast_radius", "params": {"node_id": "cache-redis-main"}}

Query: "If auth-service fails, what's affected?"
Output: {"tool": "get_upstream_dependents", "params": {"node_id": "service-auth-service"}}

Query: "Who owns payment service?"
Output: {"tool": "get_owner", "params": {"node_id": "service-payment-service"}}

Query: "List all databases"
Output: {"tool": "list_nodes", "params": {"node_type": "database"}}

Query: "What services use redis?"
Output: {"tool": "get_upstream_dependents", "params": {"node_id": "cache-redis-main"}}

Query: "What does the orders team own?"
Output: {"tool": "get_team_resources", "params": {"team_name": "orders-team"}}

Query: "What does order-service depend on?"
Output: {"tool": "get_downstream_dependencies", "params": {"node_id": "service-order-service"}}

Query: "What databases does the orders team manage?"
Output: {"tool": "get_team_resources", "params": {"team_name": "orders-team"}}

Now extract the tool call for this query:"""
    
    user_message = f"{context}Query: {query}"
    
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_message)
    ]
    
    try:
        response = llm.invoke(messages)
        content = response.content.strip()
        
        # Extract JSON
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            parsed = json.loads(json_match.group())
            return parsed
        else:
            return {"tool": "error", "error": "Could not parse tool call", "raw": content}
            
    except Exception as e:
        return {"tool": "error", "error": str(e)}


def execute_tool(tool_name: str, params: dict) -> dict:
    """Execute a tool with given parameters."""
    try:
        if tool_name == "get_owner":
            return execute_get_owner(**params)
        elif tool_name == "list_nodes":
            return execute_list_nodes(**params)
        elif tool_name == "get_downstream_dependencies":
            return execute_get_downstream_dependencies(**params)
        elif tool_name == "get_upstream_dependents":
            return execute_get_upstream_dependents(**params)
        elif tool_name == "calculate_blast_radius":
            return execute_calculate_blast_radius(**params)
        elif tool_name == "find_path":
            return execute_find_path(**params)
        elif tool_name == "get_team_resources":
            return execute_get_team_resources(**params)
        else:
            return {"success": False, "error": f"Unknown tool: {tool_name}"}
    except Exception as e:
        return {"success": False, "error": f"Error executing {tool_name}: {str(e)}"}


def format_results(tool_name: str, results: dict, original_query: str) -> str:
    """Format tool results into natural language."""
    if not results.get("success"):
        return f"❌ {results.get('message', results.get('error', 'Query failed'))}"
    
    if tool_name == "get_owner":
        owner = results["owner"]
        return f"The resource is owned by **{owner['name']}** (lead: {owner.get('lead', 'N/A')}, Slack: {owner.get('slack_channel', 'N/A')})."
    
    elif tool_name == "list_nodes":
        nodes = results["nodes"]
        node_type = results.get("node_type", "node")
        if not nodes:
            return f"No {node_type}s found."
        
        response = f"Found {len(nodes)} {node_type}(s):\n"
        for node in nodes:
            response += f"- **{node['name']}** (ID: {node['id']})\n"
        return response
    
    elif tool_name == "get_downstream_dependencies":
        deps = results["dependencies"]
        if not deps:
            return "No downstream dependencies found."
        
        response = f"Depends on {len(deps)} resource(s):\n"
        for dep in deps:
            # Get type from labels if available
            dep_type = dep.get('type') or (dep.get('labels', ['Unknown'])[0] if dep.get('labels') else 'Unknown')
            response += f"- **{dep['name']}** ({dep_type})\n"
        return response
    
    elif tool_name == "get_upstream_dependents":
        deps = results["dependents"]
        if not deps:
            return "No upstream dependents found."
        
        response = f"{len(deps)} resource(s) depend on this:\n"
        for dep in deps:
            # Get type from labels if available
            dep_type = dep.get('type') or (dep.get('labels', ['Unknown'])[0] if dep.get('labels') else 'Unknown')
            response += f"- **{dep['name']}** ({dep_type})\n"
        return response
    
    elif tool_name == "calculate_blast_radius":
        blast = results["blast_radius"]
        node = blast["node"]
        
        response = f"**Blast Radius Analysis for {node['name']}:**\n\n"
        response += f"📊 **Impact Summary:**\n"
        response += f"- Downstream dependencies: {len(blast['downstream'])}\n"
        response += f"- Upstream dependents: {len(blast['upstream'])}\n"
        response += f"- Affected teams: {len(blast['teams'])}\n\n"
        
        if blast['upstream']:
            response += f"⚠️ **Services that will break:**\n"
            for svc in blast['upstream'][:10]:
                response += f"- {svc['name']}\n"
        
        if blast['teams']:
            response += f"\n👥 **Teams to notify:**\n"
            for team in blast['teams']:
                response += f"- {team['name']} (lead: {team.get('lead', 'N/A')})\n"
        
        return response
    
    elif tool_name == "find_path":
        path = results["path"]
        nodes = path["nodes"]
        return f"**Path found:** {' → '.join(nodes)}"
    
    elif tool_name == "get_team_resources":
        owned = results["owned"]
        if not owned:
            return "Team doesn't own any resources."
        
        response = f"Team owns {len(owned)} resource(s):\n"
        for resource in owned:
            response += f"- **{resource['name']}** ({resource['type']})\n"
        return response
    
    return str(results)


def query_knowledge_graph(query: str, conversation_history: list = None) -> dict:
    """
    Process a natural language query against the knowledge graph.
    
    Args:
        query: Natural language query
        conversation_history: Optional list of previous messages for context
    
    Returns:
        Dictionary containing the answer and metadata
    """
    try:
        # Step 1: Extract tool call using LLM (1 LLM call)
        tool_call = extract_tool_call(query, conversation_history)
        
        if tool_call.get("tool") == "error":
            return {
                "success": False,
                "answer": f"Failed to understand query: {tool_call.get('error')}",
                "error": tool_call.get("error")
            }
        
        tool_name = tool_call.get("tool")
        params = tool_call.get("params", {})
        
        # Step 2: Execute tool (no LLM call)
        results = execute_tool(tool_name, params)
        
        # Step 3: Format results (no LLM call)
        answer = format_results(tool_name, results, query)
        
        return {
            "success": True,
            "answer": answer,
            "tool_call": tool_call,
            "tool_calls_made": 1  # Only 1 LLM call
        }
        
    except Exception as e:
        return {
            "success": False,
            "answer": f"An error occurred: {str(e)}",
            "error": str(e)
        }


# Test function
if __name__ == "__main__":
    test_queries = [
        "How does api-gateway connect to orders-db?",
        "What's between order-service and notification-service?",
        "If auth-service fails, what's affected?",
        "What breaks if redis-main goes down?",
        "List all databases",
        "Who owns payment service?",
    ]
    
    print("Testing Knowledge Graph Agent (Two-step approach)...\n")
    
    conversation_history = []
    
    for i, query in enumerate(test_queries, 1):
        print(f"Q{i}: {query}")
        
        result = query_knowledge_graph(query, conversation_history)
        
        if result['success']:
            print(f"✅ {result['answer']}")
            if 'tool_call' in result:
                print(f"   [Tool: {result['tool_call']['tool']}]")
        else:
            print(f"❌ {result.get('answer', result.get('error'))}")
        
        print("-" * 80)
        
        # Update history
        conversation_history.append({"role": "user", "content": query})
        conversation_history.append({"role": "assistant", "content": result.get('answer', '')})