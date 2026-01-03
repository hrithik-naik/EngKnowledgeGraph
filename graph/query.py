from neo4j import GraphDatabase


class QueryEngine:
    def __init__(self, uri: str, user: str, password: str):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        self.driver.close()

    # -------------------------
    # Internal helper
    # -------------------------
    def _run(self, query: str, params: dict | None = None):
        with self.driver.session() as session:
            result = session.run(query, params or {})
            return list(result)

    def _node_to_dict(self, node):
        if node is None:
            return None
        data = dict(node)
        data["id"] = node["id"]
        data["labels"] = list(node.labels)
        return data

    # -------------------------
    # Required queries
    # -------------------------
    def get_node(self, node_id: str):
        query = """
        MATCH (n {id: $id})
        RETURN n
        """
        rows = self._run(query, {"id": node_id})
        if not rows:
            return None
        return self._node_to_dict(rows[0]["n"])

    def get_nodes(self, type: str, filters: dict | None = None):
        filters = filters or {}
        params = {}

        where_clauses = []
        for key, value in filters.items():
            where_clauses.append(f"n.{key} = ${key}")
            params[key] = value

        where_stmt = ""
        if where_clauses:
            where_stmt = "WHERE " + " AND ".join(where_clauses)

        label = type.capitalize()

        query = f"""
        MATCH (n:`{label}`)
        {where_stmt}
        RETURN n
        """

        return [self._node_to_dict(row["n"]) for row in self._run(query, params)]

    def downstream(self, node_id: str):
        query = """
        MATCH (n {id: $id})-[:DEPENDS_ON*1..]->(d)
        RETURN DISTINCT d
        """
        return [
            self._node_to_dict(row["d"])
            for row in self._run(query, {"id": node_id})
        ]

    def upstream(self, node_id: str):
        query = """
        MATCH (u)-[:DEPENDS_ON*1..]->(n {id: $id})
        RETURN DISTINCT u
        """
        return [
            self._node_to_dict(row["u"])
            for row in self._run(query, {"id": node_id})
        ]

    def path(self, from_id: str, to_id: str):
        query = """
        MATCH p = shortestPath(
            (a {id: $from})-[:DEPENDS_ON*..]->(b {id: $to})
        )
        RETURN p
        """
        rows = self._run(query, {"from": from_id, "to": to_id})
        if not rows:
            return None

        path = rows[0]["p"]

        return {
            "nodes": [node["id"] for node in path.nodes],
            "relationships": [rel.type for rel in path.relationships],
        }

    def get_owner(self, node_id: str):
        query = """
        MATCH (n {id: $id})-[:OWNED_BY]->(t)
        RETURN t
        """
        rows = self._run(query, {"id": node_id})
        if not rows:
            return None
        return self._node_to_dict(rows[0]["t"])

    def blast_radius(self, node_id: str):
        root = self.get_node(node_id)
        if not root:
            return None

        downstream_nodes = self.downstream(node_id)
        upstream_nodes = self.upstream(node_id)

        impacted_nodes = {
            node["id"]: node
            for node in downstream_nodes + upstream_nodes
        }

        impacted_teams = {}
        for node in impacted_nodes.values():
            owner = self.get_owner(node["id"])
            if owner:
                impacted_teams[owner["id"]] = owner

        return {
            "node": root,
            "downstream": list(impacted_nodes.values()),
            "upstream": upstream_nodes,
            "teams": list(impacted_teams.values()),
        }
def main():
    engine = QueryEngine(
        uri="bolt://localhost:7687",
        user="neo4j",
        password="password",
    )

    try:
        print("\n=== GET NODE ===")
        node_id = "service-order-service"
        node = engine.get_node(node_id)
        if not node:
            print(f"[NOT FOUND] Node '{node_id}' does not exist")
        else:
            print(node)

        print("\n=== GET DATABASE NODES ===")
        databases = engine.get_nodes(type="database")
        if not databases:
            print("[EMPTY] No database nodes found")
        else:
            for db in databases:
                print(db["id"], db["name"])

        print("\n=== DOWNSTREAM (order-service depends on) ===")
        downstream = engine.downstream("service-order-service")
        if not downstream:
            print("[NONE] No downstream dependencies")
        else:
            for n in downstream:
                print(" -", n["id"])

        print("\n=== UPSTREAM (what depends on orders-db) ===")
        upstream = engine.upstream("database-orders-db")
        if not upstream:
            print("[NONE] No upstream dependents")
        else:
            for n in upstream:
                print(" -", n["id"])

        print("\n=== SHORTEST PATH api-gateway → payments-db ===")
        path = engine.path(
            from_id="service-api-gateway",
            to_id="database-payments-db",
        )
        if not path:
            print("[NO PATH] No dependency path exists")
        else:
            print("Nodes:", " -> ".join(path["nodes"]))
            print("Edges:", path["relationships"])

        print("\n=== SHORTEST PATH (non-existent example) ===")
        bad_path = engine.path(
            from_id="service-api-gateway",
            to_id="database-does-not-exist",
        )
        if not bad_path:
            print("[NO PATH] Target node does not exist or is unreachable")

        print("\n=== OWNER OF payment-service ===")
        owner = engine.get_owner("service-payment-service")
        if not owner:
            print("[UNKNOWN] No owning team found")
        else:
            print(owner)

        print("\n=== BLAST RADIUS: orders-db ===")
        blast = engine.blast_radius("database-orders-db")
        if not blast:
            print("[NOT FOUND] Root node does not exist")
        else:
            print("Root:", blast["node"]["id"])
            print("Impacted nodes:")
            for n in blast["downstream"]:
                print(" -", n["id"])
            print("Teams impacted:")
            for t in blast["teams"]:
                print(" -", t["name"])

        print("\n=== BLAST RADIUS (non-existent node) ===")
        blast = engine.blast_radius("database-ghost")
        if not blast:
            print("[NOT FOUND] Cannot compute blast radius for missing node")

    finally:
        engine.close()


if __name__ == "__main__":
    main()
