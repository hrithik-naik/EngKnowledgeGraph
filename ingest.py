# ingest.py

import yaml
from pathlib import Path
import os
from connectors.teams import TeamsConnector
from connectors.docker_compose import DockerComposeConnector
from connectors.kubernetes import KubernetesConnector
from graph.neo4j_storage import Neo4jStorage

def load_yaml_documents(path: Path):
    try:
        with open(path, "r") as file:
            return list(yaml.safe_load_all(file))
    except yaml.YAMLError as e:
        print(f"[INGEST] Invalid YAML, skipping: {path.name}")
        return []



def run_ingestion(data_dir, connectors):
    nodes = []
    edges = []

    for file_path in data_dir.glob("*.y*ml"):
        try:
            documents = load_yaml_documents(file_path)
        except Exception as e:
            print(f"[INGEST] Failed to load {file_path.name}: {e}")
            continue

        if not documents:
            # Invalid or empty YAML → nothing to do
            print(f"[INGEST] Skipping {file_path.name} (no valid documents)")
            continue

        handled = False

        for document in documents:
            if not isinstance(document, dict):
                continue

            for connector in connectors:
                try:
                    if connector.can_handle(file_path.name, document):
                        parsed_nodes, parsed_edges = connector.parse(document)
                        nodes.extend(parsed_nodes)
                        edges.extend(parsed_edges)
                        print(f"[OK] {file_path.name} → {connector.__class__.__name__}")
                        handled = True
                        break
                except Exception as e:
                    print(
                        f"[INGEST] Error in {connector.__class__.__name__} "
                        f"for {file_path.name}: {e}"
                    )
                    handled = True
                    break

        if not handled:
            print(f"[SKIP] {file_path.name} (no matching connector)")

    return nodes, edges


import time

def write_with_retry(storage, nodes, edges, retries=20, delay=2):
    for attempt in range(1, retries + 1):
        try:
            time.sleep(1)
            storage.write_nodes(nodes)
            storage.write_edges(edges)
            return
        except Exception as e:
            print(f"[INGEST] Neo4j not ready (attempt {attempt})")
            if attempt == retries:
                raise
            time.sleep(delay)


def main():
    connectors = [
        TeamsConnector(),
        DockerComposeConnector(),
        KubernetesConnector(),
    ]

    nodes, edges = run_ingestion(Path("data"), connectors)
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "password")
    storage = Neo4jStorage(
        uri=uri,
        user=user,
        password=password,
    )

    write_with_retry(storage=storage,nodes=nodes,edges=edges)
    storage.close()


if __name__ == "__main__":
    main()
