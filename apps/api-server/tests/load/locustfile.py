from locust import HttpUser, between, task


class SentinelOpsUser(HttpUser):
    wait_time = between(1, 3)
    incident_id = "00000000-0000-0000-0000-000000000001"

    @task
    def health(self):
        self.client.get("/health")

    @task
    def evaluations(self):
        self.client.get("/evaluations/summary")

    @task
    def incidents(self):
        self.client.get("/incidents")

    @task
    def graph_state(self):
        self.client.get(f"/graph/incidents/{self.incident_id}/graph-state")
