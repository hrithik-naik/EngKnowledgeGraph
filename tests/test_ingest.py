import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from ingest import run_ingestion
from connectors.teams import TeamsConnector
from connectors.docker_compose import DockerComposeConnector
from connectors.kubernetes import KubernetesConnector


def test_ingest_with_teams_yaml(tmp_path):
    (tmp_path / "teams.yaml").write_text(
        """
teams:
  - name: platform-team
    owns:
      - api-gateway
"""
    )

    nodes, edges = run_ingestion(tmp_path, [TeamsConnector()])

    node_ids = {n["id"] for n in nodes}

    assert "team-platform-team" in node_ids
    assert "service-api-gateway" in node_ids
    assert edges


def test_ingest_with_docker_compose_yaml(tmp_path):
    (tmp_path / "docker-compose.yml").write_text(
        """
services:
  api:
    depends_on:
      - db
  db:
    image: postgres:15
"""
    )

    nodes, edges = run_ingestion(tmp_path, [DockerComposeConnector()])

    node_ids = {n["id"] for n in nodes}

    assert "service-api" in node_ids
    assert "database-db" in node_ids
    assert {
        "from": "service-api",
        "to": "database-db",
        "type": "DEPENDS_ON",
    } in edges


def test_ingest_with_kubernetes_yaml(tmp_path):
    (tmp_path / "k8s.yaml").write_text(
        """
apiVersion: apps/v1
kind: Deployment
metadata:
  name: order-service
spec:
  replicas: 2
  template:
    spec:
      containers:
        - name: order
          image: order:v1
"""
    )

    nodes, edges = run_ingestion(tmp_path, [KubernetesConnector()])

    assert len(nodes) == 1
    assert nodes[0]["id"] == "k8s-deployment-order-service"
    assert edges == []
