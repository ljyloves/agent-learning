import unittest

from pydantic import ValidationError

from app.modules.paper_agent.schemas import (
    PaperJob,
    PaperJobStatus,
    ReviewStatus,
)


class PaperJobSchemaTests(unittest.TestCase):
    def test_failed_job_records_failure_reason(self):
        job = PaperJob(
            job_id="job-failed",
            status=PaperJobStatus.FAILED,
            failure_reason="The source site timed out.",
        )

        self.assertEqual(job.status, PaperJobStatus.FAILED)
        self.assertEqual(job.failure_reason, "The source site timed out.")

    def test_failed_job_requires_failure_reason(self):
        with self.assertRaises(ValidationError):
            PaperJob(
                job_id="job-failed",
                status=PaperJobStatus.FAILED,
            )

    def test_final_review_records_result(self):
        job = PaperJob(
            job_id="job-approved",
            status=PaperJobStatus.COMPLETED,
            review_status=ReviewStatus.APPROVED,
            review_result={
                "status": ReviewStatus.APPROVED,
                "reviewer": "teacher-001",
                "comments": "Difficulty and coverage are appropriate.",
            },
        )

        payload = job.model_dump(mode="json")
        self.assertEqual(payload["review_status"], "approved")
        self.assertEqual(payload["review_result"]["reviewer"], "teacher-001")
        self.assertIsNotNone(payload["review_result"]["reviewed_at"])

    def test_final_review_requires_matching_result(self):
        with self.assertRaises(ValidationError):
            PaperJob(
                job_id="job-missing-review",
                review_status=ReviewStatus.REJECTED,
            )

        with self.assertRaises(ValidationError):
            PaperJob(
                job_id="job-mismatched-review",
                review_status=ReviewStatus.APPROVED,
                review_result={
                    "status": ReviewStatus.REJECTED,
                    "reviewer": "teacher-001",
                    "comments": "Replace duplicated questions.",
                },
            )

    def test_rejected_review_requires_details(self):
        with self.assertRaises(ValidationError):
            PaperJob(
                job_id="job-rejected",
                review_status=ReviewStatus.REJECTED,
                review_result={
                    "status": ReviewStatus.REJECTED,
                    "reviewer": "teacher-001",
                },
            )


if __name__ == "__main__":
    unittest.main()
