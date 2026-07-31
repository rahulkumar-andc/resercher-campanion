import os
import shutil
import unittest
from src.core.models import PipelineContext, PipelineStage
from src.core.event_bus import SupervisorBus
from src.core.style_engine import StyleEngine
from src.agents.layer6_supervisor import SupervisorAgent


class TestResearchCompanionPipeline(unittest.TestCase):
    def setUp(self):
        self.test_out_dir = "./test_output"
        os.makedirs(self.test_out_dir, exist_ok=True)
        self.test_code_path = "./sample_data/sample_code.py"
        self.test_notes_path = "./sample_data/sample_notes.txt"

    def tearDown(self):
        if os.path.exists(self.test_out_dir):
            shutil.rmtree(self.test_out_dir)

    def test_style_engine(self):
        sample_text = "The system uses an asynchronous event bus to decouple processing stages."
        fingerprint = StyleEngine.extract_fingerprint(sample_text)
        self.assertIn("academic_tone", fingerprint)
        self.assertIn("sentence_length", fingerprint)

    def test_full_pipeline_execution(self):
        ctx = PipelineContext(
            job_id="test_job_1",
            raw_topic="Unit Testing Multi-Agent Systems",
            raw_code_paths=[self.test_code_path],
            raw_notes_paths=[self.test_notes_path]
        )

        supervisor = SupervisorAgent()
        completed_ctx = supervisor.execute_pipeline(ctx, output_dir=self.test_out_dir)

        self.assertLessEqual(completed_ctx.quality_audit.plagiarism_percentage, 15.0)
        self.assertLessEqual(completed_ctx.quality_audit.ai_writing_percentage, 10.0)
        self.assertIn("1_why_needed", completed_ctx.quality_audit.reviewer_answers)
        self.assertEqual(len(completed_ctx.quality_audit.reviewer_answers), 7)

        # Check Hugging Face Upskill Evaluator Metrics
        self.assertGreaterEqual(completed_ctx.quality_audit.upskill_accuracy_score, 90.0)
        self.assertIn("academic_accuracy", completed_ctx.quality_audit.upskill_metrics)
        self.assertIn("citation_grounding", completed_ctx.quality_audit.upskill_metrics)


        # Check Generated Files
        pdf_path = os.path.join(self.test_out_dir, "ResearchPaper.pdf")
        pptx_path = os.path.join(self.test_out_dir, "Presentation.pptx")
        bib_path = os.path.join(self.test_out_dir, "references.bib")

        self.assertTrue(os.path.exists(pdf_path), "PDF research paper should be generated.")
        self.assertTrue(os.path.exists(pptx_path), "PPTX presentation should be generated.")
        self.assertTrue(os.path.exists(bib_path), "BibTeX references file should be generated.")
        self.assertGreater(os.path.getsize(pdf_path), 0)
        self.assertGreater(os.path.getsize(pptx_path), 0)


if __name__ == "__main__":
    unittest.main()
