# chat/chat.py - Tool-calling approach compatible with Groq
import os
import json
import re
from typing import Optional, List, Dict, Any
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

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
def execute_get_node_info(node_id: str) -> dict:
    """Get information about a specific node by its ID."""
    try:
        node = engine.get_node(node_id)
        if node:
            return {"success": True, "node": node}
        return {"success": False, "message": f"Node {node_id} not found"}
    except Exception as e:
        return {"success": False, "error": str(e)}


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


# Tool registry
TOOL_FUNCTIONS = {
    "get_node_info": execute_get_node_info,
    "get_owner": execute_get_owner,
    "list_nodes": execute_list_nodes,
    "get_downstream_dependencies": execute_get_downstream_dependencies,
    "get_upstream_dependents": execute_get_upstream_dependents,
    "calculate_blast_radius": execute_calculate_blast_radius,
    "find_path": execute_find_path,
    "get_team_resources": execute_get_team_resources
}


def get_tool_descriptions() -> str:
    """Get formatted tool descriptions for the LLM."""
    return """
Available tools:

1. get_node_info(node_id: str)
   - Get information about a specific node
   - Args: node_id (e.g., "service-payment-service")

2. get_owner(node_id: str)
   - Get the team that owns a resource
   - Args: node_id (e.g., "service-payment-service")

3. list_nodes(node_type: str)
   - List all nodes of a type
   - Args: node_type ("service", "database", "cache", or "team")

4. get_downstream_dependencies(node_id: str)
   - Get what a node depends on
   - Args: node_id

5. get_upstream_dependents(node_id: str)
   - Get what depends on a node
   - Args: node_id

6. calculate_blast_radius(node_id: str)
   - Calculate impact if a node goes down
   - Args: node_id

7. find_path(from_id: str, to_id: str)
   - Find dependency path between two nodes
   - Args: from_id, to_id

8. get_team_resources(team_name: str)
   - Get all resources owned by a team
   - Args: team_name (e.g., "platform-team" or just "platform")
"""


def parse_tool_calls(text: str) -> List[Dict[str, Any]]:
    """Parse tool calls from LLM response."""
    tool_calls = []
    
    # Pattern: TOOL_CALL: function_name(arg1="value1", arg2="value2")
    pattern = r'TOOL_CALL:\s*(\w+)\((.*?)\)'
    matches = re.finditer(pattern, text, re.DOTALL)
    
    for match in matches:
        func_name = match.group(1)
        args_str = match.group(2)
        
        # Parse arguments
        args = {}
        arg_pattern = r'(\w+)\s*=\s*"([^"]*)"'
        for arg_match in re.finditer(arg_pattern, args_str):
            args[arg_match.group(1)] = arg_match.group(2)
        
        tool_calls.append({
            "function": func_name,
            "arguments": args
        })
    
    return tool_calls


def execute_tool_call(tool_call: Dict[str, Any]) -> dict:
    """Execute a single tool call."""
    func_name = tool_call["function"]
    args = tool_call["arguments"]
    
    if func_name not in TOOL_FUNCTIONS:
        return {"success": False, "error": f"Unknown function: {func_name}"}
    
    try:
        func = TOOL_FUNCTIONS[func_name]
        result = func(**args)
        return result
    except Exception as e:
        return {"success": False, "error": f"Error executing {func_name}: {str(e)}"}


def format_tool_result(func_name: str, result: dict) -> str:
    """Format tool execution result."""
    if not result.get("success"):
        return f"Error: {result.get('message', result.get('error', 'Unknown error'))}"
    
    if func_name == "get_owner":
        owner = result["owner"]
        return f"Owner: {owner['name']} (lead: {owner.get('lead', 'N/A')}, Slack: {owner.get('slack_channel', 'N/A')})"
    
    elif func_name == "list_nodes":
        nodes = result["nodes"]
        if not nodes:
            return "No nodes found"
        return f"Found {len(nodes)} nodes: " + ", ".join([f"{n['name']} ({n['id']})" for n in nodes[:10]])
    
    elif func_name == "get_downstream_dependencies":
        deps = result["dependencies"]
        if not deps:
            return "No dependencies"
        return f"Dependencies: " + ", ".join([f"{d['name']}" for d in deps])
    
    elif func_name == "get_upstream_dependents":
        deps = result["dependents"]
        if not deps:
            return "No dependents"
        return f"Dependents: " + ", ".join([f"{d['name']}" for d in deps])
    
    elif func_name == "calculate_blast_radius":
        blast = result["blast_radius"]
        upstream_names = [s['name'] for s in blast['upstream']]
        team_names = [t['name'] for t in blast['teams']]
        return f"Blast radius: {len(blast['upstream'])} services affected ({', '.join(upstream_names[:5])}), {len(blast['teams'])} teams ({', '.join(team_names)})"
    
    elif func_name == "find_path":
        path = result["path"]
        return f"Path: {' → '.join(path['nodes'])}"
    
    elif func_name == "get_team_resources":
        owned = result["owned"]
        if not owned:
            return "Team owns no resources"
        return f"Team owns {len(owned)} resources: " + ", ".join([f"{r['name']}" for r in owned])
    
    elif func_name == "get_node_info":
        node = result["node"]
        return f"Node: {node['name']} ({node['type']}, ID: {node['id']})"
    
    return json.dumps(result)


def query_knowledge_graph(query: str, conversation_history: list = None) -> dict:
    """
    Process a natural language query against the knowledge graph using tool calls.
    
    Args:
        query: Natural language query
        conversation_history: Optional list of previous messages for context
    
    Returns:
        Dictionary containing the answer and metadata
    """
    try:
        llm = get_llm()
        
        # Build conversation context
        context = ""
        if conversation_history:
            context = "Previous conversation:\n"
            for msg in conversation_history[-6:]:  # Last 3 exchanges
                role = msg.get("role", "")
                content = msg.get("content", "")
                context += f"{role}: {content}\n"
            context += "\n"
        
        # System prompt
        system_prompt = f"""You are a helpful assistant for querying an Engineering Knowledge Graph.

The graph contains:
- Services: service-<name> (e.g., service-order-service, service-payment-service)
- Databases: database-<name> (e.g., database-orders-db, database-payments-db)
- Caches: cache-<name> (e.g., cache-redis-main)
- Teams: team-<name> (e.g., team-platform-team, team-payments-team)

{get_tool_descriptions()}

IMPORTANT: When you need to use tools, respond with:
TOOL_CALL: function_name(arg1="value1", arg2="value2")

You can make multiple tool calls in one response.

Guidelines:
1. For follow-up questions, use conversation history to understand context
2. Infer full node IDs from short names: "payments" → "service-payment-service", "orders-db" → "database-orders-db"
3. If "that" or "it" is mentioned, refer to the most recent node discussed
4. Common patterns: "payment"/"payments" → "payment-service", "redis" → "redis-main"
5. If unsure about exact ID, try common variations

After tool calls are executed, you'll see the results and can provide a final answer."""
        
        max_iterations = 3
        messages = [SystemMessage(content=system_prompt)]
        tool_calls_made = 0
        
        # Add context and query
        user_message = f"{context}User: {query}"
        messages.append(HumanMessage(content=user_message))
        
        for iteration in range(max_iterations):
            # Get LLM response
            response = llm.invoke(messages)
            tool_calls_made += 1
            
            # Check for tool calls in response
            tool_calls = parse_tool_calls(response.content)
            
            if not tool_calls:
                # No tool calls, this is the final answer
                return {
                    "success": True,
                    "answer": response.content,
                    "tool_calls_made": tool_calls_made
                }
            
            # Execute tool calls
            tool_results = []
            for tool_call in tool_calls:
                result = execute_tool_call(tool_call)
                formatted = format_tool_result(tool_call["function"], result)
                tool_results.append(f"{tool_call['function']}: {formatted}")
            
            # Add tool results to conversation
            results_text = "Tool results:\n" + "\n".join(tool_results)
            messages.append(AIMessage(content=response.content))
            messages.append(HumanMessage(content=results_text + "\n\nProvide a natural language response based on these results. Do NOT make more tool calls."))
        
        # Get final answer after max iterations
        final_response = llm.invoke(messages)
        return {
            "success": True,
            "answer": final_response.content,
            "tool_calls_made": tool_calls_made
        }
        
    except Exception as e:
        return {
            "success": False,
            "answer": f"An error occurred: {str(e)}",
            "error": str(e)
        }


# Add this to your chat.py temporarily to debug

def query_knowledge_graph_debug(query: str, conversation_history: list = None) -> dict:
    """Debug version that prints what's happening."""
    try:
        llm = get_llm()
        
        context = ""
        if conversation_history:
            context = "Previous conversation:\n"
            for msg in conversation_history[-6:]:
                role = msg.get("role", "")
                content = msg.get("content", "")
                context += f"{role}: {content}\n"
            context += "\n"
        
        system_prompt = f"""You are a helpful assistant for querying an Engineering Knowledge Graph.

The graph contains:
- Services: service-<n> (e.g., service-order-service, service-payment-service, service-api-gateway)
- Databases: database-<n> (e.g., database-orders-db, database-payments-db)
- Caches: cache-<n> (e.g., cache-redis-main)
- Teams: team-<n> (e.g., team-platform-team, team-payments-team)

{get_tool_descriptions()}

CRITICAL: You MUST use tools to answer questions. When you need to query the graph, respond with:
TOOL_CALL: function_name(arg1="value1", arg2="value2")

Examples:
- "How does api-gateway connect to orders-db?" → TOOL_CALL: find_path(from_id="service-api-gateway", to_id="database-orders-db")
- "What's between order-service and notification-service?" → TOOL_CALL: find_path(from_id="service-order-service", to_id="service-notification-service")

After tool calls are executed, you'll see the results and should provide a final natural language answer."""
        
        max_iterations = 3
        messages = [SystemMessage(content=system_prompt)]
        tool_calls_made = 0
        
        user_message = f"{context}User: {query}"
        messages.append(HumanMessage(content=user_message))
        
        for iteration in range(max_iterations):
            print(f"\n{'='*80}")
            print(f"ITERATION {iteration + 1}")
            print(f"{'='*80}")
            
            response = llm.invoke(messages)
            tool_calls_made += 1
            
            print(f"\n[LLM RESPONSE]:\n{response.content}\n")
            
            tool_calls = parse_tool_calls(response.content)
            print(f"[PARSED TOOL CALLS]: {tool_calls}")
            
            if not tool_calls:
                print("[NO TOOL CALLS DETECTED - Returning response as final answer]")
                return {
                    "success": True,
                    "answer": response.content,
                    "tool_calls_made": tool_calls_made
                }
            
            tool_results = []
            for tool_call in tool_calls:
                print(f"\n[EXECUTING]: {tool_call['function']}({tool_call['arguments']})")
                result = execute_tool_call(tool_call)
                print(f"[RAW RESULT]: {result}")
                
                formatted = format_tool_result(tool_call["function"], result)
                print(f"[FORMATTED]: {formatted}")
                tool_results.append(f"{tool_call['function']}: {formatted}")
            
            results_text = "Tool results:\n" + "\n".join(tool_results)
            messages.append(AIMessage(content=response.content))
            messages.append(HumanMessage(content=results_text + "\n\nBased on these results, provide a clear answer. Do NOT make more tool calls."))
        
        final_response = llm.invoke(messages)
        print(f"\n[FINAL RESPONSE]: {final_response.content}")
        
        return {
            "success": True,
            "answer": final_response.content,
            "tool_calls_made": tool_calls_made
        }
        
    except Exception as e:
        print(f"[ERROR]: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "answer": f"An error occurred: {str(e)}",
            "error": str(e)
        }


# Test it
if __name__ == "__main__":
    print("Testing path query...")
    result = query_knowledge_graph_debug("How does api-gateway connect to orders-db?")
    print(f"\n\nFINAL OUTPUT: {result['answer']}")