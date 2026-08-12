import unittest

import app.models  # noqa: F401
from app.database import Base


class DatabaseMetadataTests(unittest.TestCase):
    def test_all_tables_are_registered(self):
        expected_tables = {
            "biology_core_competencies",
            "biology_curriculum_modules",
            "biology_knowledge_points",
            "knowledge_documents",
            "paper_job_questions",
            "paper_jobs",
            "question_core_competencies",
            "question_analyses",
            "question_images",
            "question_knowledge_points",
            "question_options",
            "question_resources",
            "question_sources",
            "questions",
        }

        self.assertEqual(set(Base.metadata.tables), expected_tables)

    def test_question_and_image_provenance_foreign_keys_are_registered(self):
        questions = Base.metadata.tables["questions"]
        resources = Base.metadata.tables["question_resources"]
        images = Base.metadata.tables["question_images"]

        question_targets = {
            foreign_key.target_fullname
            for foreign_key in questions.c.source_id.foreign_keys
        }
        resource_targets = {
            foreign_key.target_fullname
            for foreign_key in resources.c.source_id.foreign_keys
        }
        image_targets = {
            foreign_key.target_fullname
            for foreign_key in images.c.resource_id.foreign_keys
        }

        self.assertEqual(question_targets, {"question_sources.source_id"})
        self.assertEqual(resource_targets, {"question_sources.source_id"})
        self.assertEqual(image_targets, {"question_resources.resource_id"})

    def test_question_taxonomy_foreign_keys_are_registered(self):
        knowledge_tags = Base.metadata.tables["question_knowledge_points"]
        competency_tags = Base.metadata.tables["question_core_competencies"]
        job_questions = Base.metadata.tables["paper_job_questions"]

        self.assertEqual(
            {
                foreign_key.target_fullname
                for foreign_key in knowledge_tags.c.knowledge_point_code.foreign_keys
            },
            {"biology_knowledge_points.code"},
        )
        self.assertEqual(
            {
                foreign_key.target_fullname
                for foreign_key in competency_tags.c.competency_code.foreign_keys
            },
            {"biology_core_competencies.code"},
        )
        self.assertEqual(
            {
                foreign_key.target_fullname
                for foreign_key in job_questions.c.job_id.foreign_keys
            },
            {"paper_jobs.job_id"},
        )

    def test_optional_json_fields_persist_none_as_sql_null(self):
        paper_jobs = Base.metadata.tables["paper_jobs"]
        questions = Base.metadata.tables["questions"]

        self.assertTrue(paper_jobs.c.review_result.type.none_as_null)
        self.assertTrue(questions.c.answer.type.none_as_null)

    def test_question_analysis_foreign_key_is_registered(self):
        analyses = Base.metadata.tables["question_analyses"]
        self.assertEqual(
            {
                foreign_key.target_fullname
                for foreign_key in analyses.c.question_id.foreign_keys
            },
            {"questions.id"},
        )


if __name__ == "__main__":
    unittest.main()
