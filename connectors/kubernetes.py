# connectors/kubernetes.py


class KubernetesConnector:
    def can_handle(self, filename, data):
        return isinstance(data, dict) and "kind" in data and "metadata" in data

    def build_deployment_node(self, name, namespace, metadata, spec):
        containers = []

        pod_spec = (
            spec.get("template", {})
                .get("spec", {})
        )

        for container in pod_spec.get("containers", []):
            containers.append({
                "name": container.get("name"),
                "image": container.get("image"),
                "ports": [
                    port.get("containerPort")
                    for port in container.get("ports", [])
                ],
            })

        return {
            "id": f"k8s-deployment-{name}",
            "type": "k8s_deployment",
            "name": name,
            "metadata": {
                "namespace": namespace,
                "replicas": spec.get("replicas"),
                "containers": containers,
                "labels": metadata.get("labels", {}),
            },
            "source": "k8s.yaml",
        }

    def build_service_node(self, name, namespace, spec):
        ports = []

        for port in spec.get("ports", []):
            ports.append({
                "port": port.get("port"),
                "targetPort": port.get("targetPort"),
                "protocol": port.get("protocol"),
            })

        return {
            "id": f"k8s-service-{name}",
            "type": "k8s_service",
            "name": name,
            "metadata": {
                "namespace": namespace,
                "service_type": spec.get("type", "ClusterIP"),
                "ports": ports,
                "selector": spec.get("selector", {}),
            },
            "source": "k8s.yaml",
        }

    def parse(self, data):
        nodes = []
        edges = []

        kind = data.get("kind")
        metadata = data.get("metadata", {})
        spec = data.get("spec", {})

        name = metadata.get("name")
        namespace = metadata.get("namespace", "default")

        if not kind or not name:
            return nodes, edges

        if kind == "Deployment":
            nodes.append(
                self.build_deployment_node(name, namespace, metadata, spec)
            )

        elif kind == "Service":
            nodes.append(
                self.build_service_node(name, namespace, spec)
            )

        return nodes, edges
