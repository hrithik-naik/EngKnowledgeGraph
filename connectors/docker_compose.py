# connectors/docker_compose.py


class DockerComposeConnector:
    def can_handle(self, filename, data):
        return isinstance(data, dict) and "services" in data

    def infer_resource_type(self, name, definition=None):
        if name.endswith("-db"):
            return "database"

        image = str(definition.get("image", "")).lower() if definition else ""

        if any(db in image for db in ("postgres", "mysql", "mongo")):
            return "database"

        if "redis" in image or name.startswith("redis"):
            return "cache"

        return "service"

    def build_node(self, name, definition, resource_type):
        return {
            "id": f"{resource_type}-{name}",
            "type": resource_type,
            "name": name,
            "metadata": {
                "image": definition.get("image"),
                "ports": definition.get("ports", []),
                "environment": definition.get("environment"),
                "labels": definition.get("labels", {}),
            },
            "source": "docker-compose.yml",
        }

    def build_dependency_edge(self, source_id, target_id):
        return {
            "from": source_id,
            "to": target_id,
            "type": "DEPENDS_ON",
        }

    def parse(self, data):
        nodes = []
        edges = []

        services = data.get("services", {})
        inferred_types = {}

        for service_name, service_def in services.items():
            resource_type = self.infer_resource_type(service_name, service_def)
            inferred_types[service_name] = resource_type
            nodes.append(self.build_node(service_name, service_def, resource_type))

        for service_name, service_def in services.items():
            source_type = inferred_types[service_name]
            source_id = f"{source_type}-{service_name}"

            for dependency in service_def.get("depends_on", []):
                dep_type = inferred_types.get(dependency) or self.infer_resource_type(dependency)
                dep_id = f"{dep_type}-{dependency}"
                edges.append(self.build_dependency_edge(source_id, dep_id))

        return nodes, edges
