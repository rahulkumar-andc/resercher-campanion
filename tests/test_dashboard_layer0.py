"""
Unit & Integration Tests for Layer 0 Sandbox Profiler & Layer 7 Web Dashboard API.
"""

import unittest
from fastapi.testclient import TestClient
from src.web.dashboard import app
from src.core.models import PipelineContext
from src.agents.layer0_profiler import RuntimeProfilerAgent
from src.core.event_bus import SupervisorBus


class TestDashboardAndLayer0(unittest.TestCase):

    def setUp(self):
        self.client = TestClient(app)
        self.bus = SupervisorBus()
        self.profiler = RuntimeProfilerAgent(self.bus)

    def test_layer0_sandbox_profiler(self):
        ctx = PipelineContext(
            job_id="test_profiler_job",
            raw_topic="Sandbox Profiler Test",
            raw_code_paths=["./sample_data/sample_code.py"]
        )
        self.profiler.run(ctx)
        self.assertGreaterEqual(ctx.code_analysis.cpu_time_ms, 0.0)
        self.assertGreaterEqual(ctx.code_analysis.peak_memory_mb, 0.0)

    def test_web_dashboard_html(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Autonomous Research Companion", response.text)
        self.assertIn("27-Agent Neural Event Bus", response.text)

    def test_job_creation_and_api(self):
        response = self.client.post("/api/jobs", json={
            "raw_topic": "FastAPI Web Dashboard Test",
            "raw_code_paths": ["./sample_data/sample_code.py"],
            "raw_notes_paths": ["./sample_data/sample_notes.txt"]
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "SUCCESS")
        self.assertIn("job_id", data)

        job_id = data["job_id"]
        status_res = self.client.get(f"/api/jobs/{job_id}")
        self.assertEqual(status_res.status_code, 200)


if __name__ == "__main__":
    unittest.main()
