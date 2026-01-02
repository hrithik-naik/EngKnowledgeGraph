# ingest.py

import yaml
from pathlib import Path

from connectors.teams import TeamsConnector
from connectors.docker_compose import DockerComposeConnector
from connectors.kubernetes import KubernetesConnector


def load_yaml_documents(path):
    with open(path, "r") as file:
        return list(yaml.safe_load_all(file))


def run_ingestion(data_dir, connectors):
    nodes = []
    edges = []

    for file_path in data_dir.glob("*.y*ml"):
        documents = load_yaml_documents(file_path)
        handled = False

        for document in documents:
            if not isinstance(document, dict):
                continue

            for connector in connectors:
                if connector.can_handle(file_path.name, document):
                    parsed_nodes, parsed_edges = connector.parse(document)
                    nodes.extend(parsed_nodes)
                    edges.extend(parsed_edges)
                    print(f"[OK] {file_path.name} → {connector.__class__.__name__}")
                    handled = True
                    break

        if not handled:
            print(f"[SKIP] {file_path.name} (no matching connector)")

    return nodes, edges


def main():
    connectors = [
        TeamsConnector(),
        DockerComposeConnector(),
        KubernetesConnector(),
    ]

    nodes, edges = run_ingestion(Path("data"), connectors)

    print("\n=== NODES ===")
    for node in nodes:
        print(node)

    print("\n=== EDGES ===")
    for edge in edges:
        print(edge)


if __name__ == "__main__":
    main()
