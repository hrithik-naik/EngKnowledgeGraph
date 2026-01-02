import json
from neo4j import GraphDatabase


class Neo4jStorage:
    def __init__(self, uri, user, password):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        self.driver.close()

    def write_nodes(self, nodes):
        with self.driver.session() as session:
            for node in nodes:
                properties = self._flatten_metadata(node.get("metadata", {}))

                session.run(
                    f"""
                    MERGE (n:{self._label(node['type'])} {{id: $id}})
                    SET n.name = $name,
                        n.source = $source,
                        n += $properties
                    """,
                    id=node["id"],
                    name=node["name"],
                    source=node["source"],
                    properties=properties,
                )

    def write_edges(self, edges):
        with self.driver.session() as session:
            for edge in edges:
                session.run(
                    f"""
                    MATCH (a {{id: $from_id}})
                    MATCH (b {{id: $to_id}})
                    MERGE (a)-[:{edge['type']}]->(b)
                    """,
                    from_id=edge["from"],
                    to_id=edge["to"],
                )

    def _flatten_metadata(self, metadata):
        flat = {}

        for key, value in metadata.items():
            if value is None:
                continue

            if isinstance(value, (str, int, float, bool)):
                flat[key] = value

            elif isinstance(value, list):
                if all(isinstance(v, (str, int, float, bool)) for v in value):
                    flat[key] = value
                else:
                    flat[key] = json.dumps(value)

            else:
                flat[key] = json.dumps(value)

        return flat

    def _label(self, node_type):
        return {
            "service": "Service",
            "database": "Database",
            "cache": "Cache",
            "team": "Team",
            "k8s_deployment": "K8sDeployment",
            "k8s_service": "K8sService",
        }.get(node_type, "Resource")
