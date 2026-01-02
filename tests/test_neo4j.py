import pytest
from graph.neo4j_storage import Neo4jStorage


@pytest.mark.integration
def test_neo4j_write_and_cleanup():
    storage = Neo4jStorage(
        uri="bolt://localhost:7687",
        user="neo4j",
        password="password",
    )

    node = {
        "id": "service-test",
        "type": "service",
        "name": "test-service",
        "metadata": {"port": 8080},
        "source": "test",
    }

    edge = {
        "from": "service-test",
        "to": "service-test",
        "type": "DEPENDS_ON",
    }

    storage.write_nodes([node])
    storage.write_edges([edge])

    with storage.driver.session() as session:
        result = session.run(
            "MATCH (n {id: $id}) RETURN n",
            id="service-test",
        )
        records = list(result)
        assert len(records) == 1

        # 🔥 Cleanup (important)
        session.run(
            "MATCH (n {id: $id}) DETACH DELETE n",
            id="service-test",
        )

    storage.close()
