# connectors/teams.py


class TeamsConnector:
    def can_handle(self, filename, data):
        return isinstance(data, dict) and "teams" in data

    def infer_resource_type(self, name):
        if name.endswith("-db"):
            return "database"

        if name.startswith("redis"):
            return "cache"

        return "service"

    def build_team_node(self, team):
        return {
            "id": f"team-{team['name']}",
            "type": "team",
            "name": team["name"],
            "metadata": {
                "lead": team.get("lead"),
                "slack_channel": team.get("slack_channel"),
                "pagerduty_schedule": team.get("pagerduty_schedule"),
            },
            "source": "teams.yaml",
        }

    def build_resource_node(self, name, resource_type):
        return {
            "id": f"{resource_type}-{name}",
            "type": resource_type,
            "name": name,
            "metadata": {},
            "source": "teams.yaml",
        }

    def build_ownership_edge(self, resource_id, team_id):
        return {
            "from": resource_id,
            "to": team_id,
            "type": "OWNED_BY",
        }

    def parse(self, data):
        nodes = []
        edges = []

        for team in data.get("teams", []):
            team_name = team.get("name")
            if not team_name:
                continue

            team_id = f"team-{team_name}"
            nodes.append(self.build_team_node(team))

            for resource in team.get("owns", []):
                resource_type = self.infer_resource_type(resource)
                resource_id = f"{resource_type}-{resource}"

                nodes.append(
                    self.build_resource_node(resource, resource_type)
                )

                edges.append(
                    self.build_ownership_edge(resource_id, team_id)
                )

        return nodes, edges
