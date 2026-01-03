import os
import pytest

from graph.query import QueryEngine


NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")


@pytest.fixture(scope="module")
def query_engine():
    qe = QueryEngine(
        uri=NEO4J_URI,
        user=NEO4J_USER,
        password=NEO4J_PASSWORD,
    )
    yield qe
    qe.close()


# -------------------------
# Basic lookups
# -------------------------

def test_get_node(query_engine):
    node = query_engine.get_node("service-order-service")
    assert node is not None
    assert node["name"] == "order-service"


def test_get_nodes_by_type(query_engine):
    databases = query_engine.get_nodes(type="database")
    db_ids = {db["id"] for db in databases}

    assert "database-orders-db" in db_ids
    assert "database-users-db" in db_ids


def test_get_owner(query_engine):
    owner = query_engine.get_owner("service-payment-service")
    assert owner is not None
    assert owner["id"] == "team-payments-team"


# -------------------------
# Graph traversal
# -------------------------

def test_downstream(query_engine):
    deps = query_engine.downstream("service-order-service")
    dep_ids = {n["id"] for n in deps}

    assert "database-orders-db" in dep_ids
    assert "service-payment-service" in dep_ids


def test_upstream(query_engine):
    impacted = query_engine.upstream("database-orders-db")
    impacted_ids = {n["id"] for n in impacted}

    assert "service-order-service" in impacted_ids
    assert "service-api-gateway" in impacted_ids


def test_shortest_path(query_engine):
    path = query_engine.path(
        from_id="service-api-gateway",
        to_id="database-payments-db",
    )
    assert path is not None
    assert len(path["nodes"]) >= 2



# -------------------------
# Blast radius
# -------------------------

def test_blast_radius(query_engine):
    blast = query_engine.blast_radius("database-orders-db")

    assert blast["node"]["id"] == "database-orders-db"

    downstream_ids = {n["id"] for n in blast["downstream"]}
    upstream_ids = {n["id"] for n in blast["upstream"]}
    team_ids = {t["id"] for t in blast["teams"]}

    assert "service-order-service" in upstream_ids
    assert "service-api-gateway" in upstream_ids
    assert "team-orders-team" in team_ids
