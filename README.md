# 🕸️ EngKnowledgeGraph

An Engineering Knowledge Graph system that models infrastructure dependencies, service ownership, and enables natural language querying for incident response and impact analysis.

---

## Table of Contents

- [Setup \& Usage](#setup--usage)
- [Architecture Overview](#architecture-overview)
- [Design Questions](#design-questions)
- [Tradeoffs \& Limitations](#tradeoffs--limitations)
- [AI Usage](#ai-usage)

---

## Setup & Usage

### Prerequisites

- Docker & Docker Compose
- A **Groq API Key** (for LLM-powered natural language queries)

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `GROQ_API_KEY` | API key for Groq LLM service | ✅ Yes |
| `NEO4J_URI` | Neo4j connection URI | Auto-configured |
| `NEO4J_USER` | Neo4j username | Auto-configured |
| `NEO4J_PASSWORD` | Neo4j password | Auto-configured |

### Quick Start

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd EngKnowledgeGraph
   ```

2. **Set your Groq API key**
   ```bash
   export GROQ_API_KEY=your_groq_api_key_here
   ```

3. **Start all services**
   ```bash
   docker-compose up --build
   ```

4. **Access the interfaces**
   - **Chat UI (Streamlit):** http://localhost:8501
   - **Backend API:** http://localhost:8000
   - **Neo4j Browser:** http://localhost:7474 (credentials: `neo4j`/`password`)

### Interacting with the Chat Interface

The Streamlit chat interface supports natural language queries such as:

| Query Type | Example |
|------------|---------|
| **Dependencies** | "What does order-service depend on?" |
| **Dependents** | "What services use redis?" |
| **Ownership** | "Who owns payment-service?" |
| **Blast Radius** | "What breaks if orders-db goes down?" |
| **Paths** | "How does api-gateway connect to payments-db?" |
| **Listing** | "List all databases" |
| **Team Resources** | "What does the platform team own?" |

### Adding Your Own Data

Place YAML configuration files in the `data/` directory:
- **teams.yaml** — Team ownership definitions
- **docker-compose.yml** — Service dependencies
- **k8s*.yaml** — Kubernetes deployments/services

The watcher service automatically detects changes and re-ingests data.

---

## Architecture Overview

### Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           EngKnowledgeGraph                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐  │
│  │ Config Files │───▶│  Connectors │───▶│  Neo4j      │───▶│   Query     │  │
│  │              │    │             │    │  Graph DB   │    │   Engine    │  │
│  │ • teams.yaml │    │ • Teams     │    │             │    │             │  │
│  │ • docker-    │    │ • Docker    │    │  Nodes:     │    │ • get_node  │  │
│  │   compose.yml│    │   Compose   │    │  • Service  │    │ • upstream  │  │
│  │ • k8s*.yaml  │    │ • K8s       │    │  • Database │    │ • downstream│  │
│  └──────────────┘    └─────────────┘    │  • Team     │    │ • path      │  │
│         │                               │  • Cache    │    │ • blast_rad │  │
│         │                               │             │    └──────┬──────┘  │
│         ▼                               │  Edges:     │           │         │
│  ┌──────────────┐                       │  • DEPENDS  │           ▼         │
│  │   Watcher    │                       │  • OWNED_BY │    ┌─────────────┐  │
│  │  (watchdog)  │──────────────────────▶│             │    │   Chat      │  │
│  │              │     auto-sync         └─────────────┘    │   (LLM)     │  │
│  └──────────────┘                                          │             │  │
│                                                            │ Groq/Llama  │  │
│                                                            └──────┬──────┘  │
│                                                                   │         │
│  ┌────────────────────────────────────────────────────────────────┼───────┐ │
│  │                         FastAPI Backend                        │       │ │
│  │                      POST /query                               │       │ │
│  └────────────────────────────────────────────────────────────────┼───────┘ │
│                                                                   │         │
│  ┌────────────────────────────────────────────────────────────────▼───────┐ │
│  │                      Streamlit Chat UI                                 │ │
│  │                    http://localhost:8501                               │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Key Components

| Component | Location | Description |
|-----------|----------|-------------|
| **Connectors** | `connectors/` | Parse YAML configs into graph nodes/edges |
| **Graph Storage** | `graph/neo4j_storage.py` | Write nodes and relationships to Neo4j |
| **Query Engine** | `graph/query.py` | Execute Cypher queries (upstream, downstream, blast radius) |
| **Watcher** | `watch.py` | Monitor `data/` directory for changes, trigger re-ingestion |
| **Chat Agent** | `backend/chat.py` | Two-step LLM approach: extract intent → execute → format |
| **Backend API** | `backend/app.py` | FastAPI server exposing `/query` endpoint |
| **Chat UI** | `chat/ui.py` | Streamlit interface for end users |

### Services (Docker Compose)

| Service | Port | Purpose |
|---------|------|---------|
| `engknowledgegraph-neo4j` | 7474, 7687 | Graph database |
| `engknowledgegraph-watcher` | — | File watcher + data ingestion |
| `engknowledgegraph-backend` | 8000 | FastAPI query service |
| `engknowledgegraph-ui` | 8501 | Streamlit chat interface |

---

## Design Questions

### 1. Connector Pluggability

**How would someone add a new connector (e.g., Terraform)?**

To add a new connector (e.g., `TerraformConnector`):

1. **Create a new file** `connectors/terraform.py` with a class implementing two methods:
   - `can_handle(filename, data)` — Returns `True` if this connector should process the file
   - `parse(data)` — Returns `(nodes, edges)` tuples

2. **Register the connector** in `ingest.py` by importing it and adding to the `connectors` list:
   ```python
   from connectors.terraform import TerraformConnector
   connectors = [..., TerraformConnector()]
   ```

3. **Optionally update** `graph/neo4j_storage.py` to add new node labels in the `_label()` mapping if introducing new resource types.

The connector pattern is fully plug-and-play — no changes to the watcher, query engine, or chat layer are required.

---

### 2. Graph Updates

**If `docker-compose.yml` changes, how does your graph stay in sync?**

The system uses a **file watcher** (`watch.py`) built on the `watchdog` library with a `PollingObserver`. When any `.yml` or `.yaml` file in the `data/` directory is modified:

1. The `on_modified` event fires (with a 1.5s cooldown to debounce rapid saves)
2. The full `ingest.py` pipeline runs, re-parsing all config files
3. Neo4j uses `MERGE` statements, which **upsert** nodes by ID — existing nodes are updated, new ones are created
4. Relationships are also merged, preventing duplicates

**Limitation:** Currently, deleted services are not automatically removed from the graph. A full reconciliation would require comparing graph state vs. current configs.

---

### 3. Cycle Handling

**How do you prevent infinite loops in `upstream()` and `downstream()` queries?**

The Cypher queries use **variable-length path matching** with `DISTINCT`:

```cypher
MATCH (n {id: $id})-[:DEPENDS_ON*1..]->(d)
RETURN DISTINCT d
```

Neo4j's traversal engine inherently handles cycles by:
- Tracking visited nodes during path expansion
- `DISTINCT` ensures each node appears only once in results
- The `*1..` pattern specifies minimum 1 hop with no upper limit, but Neo4j won't revisit nodes in the same path

For the `shortestPath()` function used in `path()`, Neo4j automatically avoids cycles as it finds the minimal traversal.

---

### 4. Query Mapping

**How do you translate natural language to graph queries?**

The system uses a **two-step approach** in `backend/chat.py`:

1. **Intent Extraction (LLM call):** A Groq-hosted Llama model receives the user query with a detailed system prompt containing:
   - Node ID patterns (e.g., `service-order-service`, `database-orders-db`)
   - Available tools and their use cases
   - Example mappings from natural language to tool calls

   The LLM outputs a structured JSON like:
   ```json
   {"tool": "get_upstream_dependents", "params": {"node_id": "cache-redis-main"}}
   ```

2. **Deterministic Execution:** The extracted tool call is executed directly against the Query Engine — no LLM involved in actual graph traversal.

3. **Template-based Formatting:** Results are formatted into natural language using predefined templates, ensuring consistent output.

This approach minimizes LLM calls (exactly 1 per query) and prevents hallucination during data retrieval.

---

### 5. Failure Handling

**When the chat can't answer a question, what happens? How do you prevent hallucination?**

Several safeguards are in place:

1. **Structured output parsing:** If the LLM's JSON response fails to parse, the system returns an explicit error message rather than guessing.

2. **Tool execution validation:** Each tool returns `{"success": False, "message": "..."}` when queries fail (e.g., node not found).

3. **No LLM in data path:** The LLM only extracts intent — actual data comes directly from Neo4j. The LLM never sees or generates graph data.

4. **Deterministic formatting:** Results are formatted using fixed templates, not LLM generation, preventing fabricated information.

5. **Explicit error messages:** When a node doesn't exist or no path is found, the system returns clear messages like `"No owner found for service-xyz"` rather than inventing an answer.

---

### 6. Scale Considerations

**What would break first if this had 10K nodes? What would you change?**

**Bottlenecks at scale:**

1. **Full re-ingestion on every change:** Currently, any file modification triggers a complete re-parse of all files and MERGE operations for all nodes. At 10K nodes, this would be slow.

2. **Individual Cypher queries:** `write_nodes()` executes one query per node. Batch operations would be significantly faster.

3. **Blast radius computation:** Traversing large dependency graphs with `upstream()` + `downstream()` + owner lookups could timeout.

**Recommended changes:**

- **Incremental updates:** Track file hashes to only process changed files
- **Batch Cypher operations:** Use `UNWIND` for bulk inserts
- **Pagination:** Add limits to traversal queries
- **Caching:** Cache frequently-queried blast radius results
- **Indexing:** Ensure Neo4j indexes on `id` property (already implicit with MERGE)
- **Async ingestion:** Queue-based processing for large datasets

---

### 7. GraphDB Choice

**Why Neo4j?**

Neo4j was chosen for this implementation because:

1. **Native graph model:** Dependencies and ownership are inherently graph relationships — Neo4j's property graph model maps directly to `DEPENDS_ON` and `OWNED_BY` edges.

2. **Cypher expressiveness:** Queries like "find all upstream dependents" are one-liners: `MATCH (u)-[:DEPENDS_ON*]->(n) RETURN u`

3. **Path algorithms built-in:** `shortestPath()` and variable-length patterns handle dependency chain queries without custom code.

4. **Docker-ready:** Official Neo4j images with simple configuration.

5. **Visualization:** Neo4j Browser provides free graph visualization for debugging.

**Alternatives considered:**
- **NetworkX:** In-memory, no persistence, wouldn't survive restarts
- **PostgreSQL + recursive CTEs:** Possible but more complex queries
- **Amazon Neptune:** Better for massive scale but overkill for this use case

---

## Tradeoffs & Limitations

### Intentionally Skipped / Simplified

| Feature | Decision | Reason |
|---------|----------|--------|
| **Node deletion** | Not implemented | MERGE only creates/updates; would need reconciliation logic |
| **Multi-file transactions** | Skipped | Each file processed independently |
| **Authentication** | None | Focused on core functionality |
| **Rate limiting** | None | Demo scope |
| **Schema validation** | Basic | Relies on connector `can_handle()` checks |
| **Edge deletion** | Not implemented | Stale relationships may persist |

### Weakest Parts

1. **Re-ingestion strategy:** Full re-parse on every file change is inefficient. Should track what changed and apply deltas.

2. **Error recovery in watcher:** If Neo4j is temporarily unavailable, failed ingestions aren't queued for retry beyond the initial startup retry loop.

3. **Limited connector context:** Connectors parse files in isolation — cross-file references (e.g., K8s Service → Deployment matching) aren't fully implemented.

4. **Single LLM provider:** Hardcoded to Groq. Should abstract to support OpenAI, Anthropic, or local models.

### With 20 More Hours

- **Incremental sync:** Hash-based change detection with proper add/update/delete handling
- **Graph visualization:** Embed a D3.js or Cytoscape graph view in the UI
- **Multi-turn reasoning:** Allow follow-up questions with full context ("and what about its owner?")
- **More connectors:** Terraform, Pulumi, GitHub CODEOWNERS
- **Alerting integration:** Link to PagerDuty/Opsgenie for "who to page" queries
- **Testing:** Integration tests with a real Neo4j container
- **CI/CD pipeline:** Automated testing and deployment

---

## AI Usage

### Where AI Helped Most

1. **Boilerplate generation:** Initial FastAPI setup, Dockerfile templates, and Docker Compose configuration were accelerated significantly.

2. **Cypher query patterns:** AI suggested the variable-length path syntax (`*1..`) and `shortestPath()` usage.

3. **LLM prompt engineering:** Iterating on the intent extraction prompt with example mappings.

4. **Error handling patterns:** Suggestions for retry logic, timeout handling, and graceful degradation.

### Where I Corrected / Overrode AI

1. **Node ID conventions:** AI initially suggested simple names; I enforced the `type-name` pattern (e.g., `service-order-service`) for unambiguous lookups.

2. **Two-step vs. agent loop:** AI suggested a ReAct-style agent with multiple tool calls; I simplified to single-shot extraction for predictability and cost.

3. **Watcher debouncing:** AI's initial implementation fired on every filesystem event; added cooldown logic to prevent rapid re-ingestion.

4. **MERGE vs. CREATE:** AI used CREATE initially, which caused duplicate nodes. Switched to MERGE for idempotent operations.

### Lessons Learned About AI-Assisted Development

1. **AI excels at patterns, struggles with architecture:** Great for "how do I write a Cypher query for X?" but needs guidance on system-level decisions like data flow and component boundaries.

2. **Prompt specificity matters:** Vague prompts yield generic code. Providing concrete examples (node IDs, expected outputs) dramatically improved the intent extraction prompt.

3. **Always verify generated queries:** AI-generated Cypher looked correct but sometimes had subtle issues (wrong relationship direction, missing DISTINCT).

4. **Iteration is key:** The first AI suggestion is rarely production-ready. Treat it as a starting point for refinement.

5. **AI doesn't understand your constraints:** It may suggest solutions that don't fit your stack (e.g., suggesting LangGraph agents when simple function calls suffice).

---


