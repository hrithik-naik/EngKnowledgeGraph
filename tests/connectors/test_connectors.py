from connectors.teams import TeamsConnector
from connectors.docker_compose import DockerComposeConnector
from connectors.kubernetes import KubernetesConnector


def test_teams_connector():
    data = {
        "teams": [
            {
                "name": "orders-team",
                "lead": "@alice",
                "owns": ["order-service", "orders-db", "redis-main"],
            }
        ]
    }

    connector = TeamsConnector()
    nodes, edges = connector.parse(data)

    node_ids = {n["id"] for n in nodes}

    assert "team-orders-team" in node_ids
    assert "service-order-service" in node_ids
    assert "database-orders-db" in node_ids
    assert "cache-redis-main" in node_ids
    assert any(e["type"] == "OWNED_BY" for e in edges)


def test_docker_compose_connector():
    data = {
        "services": {
            "api": {"depends_on": ["db"]},
            "db": {"image": "postgres:15"},
        }
    }

    connector = DockerComposeConnector()
    nodes, edges = connector.parse(data)

    node_ids = {n["id"] for n in nodes}

    assert "service-api" in node_ids
    assert "database-db" in node_ids
    assert {
        "from": "service-api",
        "to": "database-db",
        "type": "DEPENDS_ON",
    } in edges


def test_kubernetes_deployment_connector():
    data = {
        "kind": "Deployment",
        "metadata": {
            "name": "order-service",
            "namespace": "ecommerce",
        },
        "spec": {
            "replicas": 2,
            "template": {
                "spec": {
                    "containers": [
                        {
                            "name": "order",
                            "image": "order:v1",
                            "ports": [{"containerPort": 8080}],
                        }
                    ]
                }
            },
        },
    }

    connector = KubernetesConnector()
    nodes, edges = connector.parse(data)

    assert len(nodes) == 1
    assert nodes[0]["id"] == "k8s-deployment-order-service"
    assert nodes[0]["metadata"]["replicas"] == 2
    assert edges == []
