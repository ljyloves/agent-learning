import unittest

from pydantic import ValidationError

from app.modules.paper_agent.schemas import (
    QuestionResource,
    QuestionSource,
    ResourceType,
    SourceType,
)


class SourceSchemaTests(unittest.TestCase):
    def test_resource_keeps_nested_source_provenance(self):
        resource = QuestionResource(
            resource_id="resource-001",
            resource_type=ResourceType.IMAGE,
            uri="s3://question-assets/cell.png",
            source={
                "source_id": "source-001",
                "source_type": SourceType.WEBSITE,
                "name": "Biology Question Bank",
                "uri": "https://example.edu/questions/1",
            },
            mime_type="image/png",
            sha256="a" * 64,
        )

        payload = resource.model_dump(mode="json")
        self.assertEqual(payload["source"]["source_id"], "source-001")
        self.assertEqual(payload["source"]["source_type"], "website")
        self.assertEqual(payload["sha256"], "a" * 64)

    def test_source_requires_stable_locator(self):
        with self.assertRaises(ValidationError):
            QuestionSource(
                source_id="source-001",
                source_type=SourceType.MANUAL,
                name="Teacher contribution",
            )

    def test_resource_rejects_invalid_checksum(self):
        with self.assertRaises(ValidationError):
            QuestionResource(
                resource_id="resource-001",
                resource_type=ResourceType.IMAGE,
                uri="assets/cell.png",
                source={
                    "source_id": "source-001",
                    "source_type": SourceType.FILE,
                    "name": "Imported exercise",
                    "external_id": "upload-001",
                },
                sha256="not-a-sha256",
            )


if __name__ == "__main__":
    unittest.main()
