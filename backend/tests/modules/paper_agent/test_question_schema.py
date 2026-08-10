import unittest

from pydantic import ValidationError

from app.modules.paper_agent.schemas import (
    Question,
    QuestionImage,
    QuestionOption,
    QuestionType,
)


def source_payload(source_id: str = "source-1") -> dict[str, str]:
    return {
        "source_id": source_id,
        "source_type": "website",
        "name": "Biology Question Bank",
        "uri": "https://example.edu/biology/questions/1",
    }


def image_payload(resource_id: str, uri: str) -> dict:
    return {
        "resource_id": resource_id,
        "uri": uri,
        "source": source_payload(f"{resource_id}-source"),
    }


class QuestionSchemaTests(unittest.TestCase):
    def test_complete_question_supports_required_content(self):
        question = Question(
            id="bio-001",
            question_type=QuestionType.COMPOSITE,
            stem="Analyze the cell diagram and answer the question.",
            source=source_payload(),
            images=[
                {
                    **image_payload(
                        "cell-image",
                        "s3://question-assets/cell.png",
                    ),
                    "alt_text": "A labeled cell diagram",
                }
            ],
            subquestions=[
                {
                    "id": "bio-001-1",
                    "question_type": QuestionType.MULTIPLE_CHOICE,
                    "stem": "Which structures contain genetic material?",
                    "source": source_payload("source-1-subquestion"),
                    "options": [
                        {"label": "a", "content": "Nucleus"},
                        {"label": "B", "content": "Cell wall"},
                        {
                            "label": "C",
                            "images": [
                                image_payload(
                                    "option-c-image",
                                    "assets/option-c.png",
                                )
                            ],
                        },
                    ],
                    "answer": ["A", "C"],
                    "explanation": "The nucleus and the pictured organelle contain DNA.",
                }
            ],
            explanation="Each subquestion is scored independently.",
        )

        payload = question.model_dump(mode="json")
        self.assertEqual(payload["question_type"], "composite")
        self.assertEqual(payload["source"]["source_id"], "source-1")
        self.assertEqual(payload["images"][0]["resource_type"], "image")
        self.assertEqual(payload["images"][0]["source"]["source_type"], "website")
        self.assertEqual(payload["subquestions"][0]["options"][0]["label"], "A")
        self.assertEqual(payload["subquestions"][0]["answer"], ["A", "C"])
        self.assertEqual(Question.model_validate(payload), question)

    def test_option_may_be_image_only(self):
        option = QuestionOption(
            label="A",
            images=[
                QuestionImage(
                    **image_payload(
                        "microscope-image",
                        "assets/microscope-view.png",
                    )
                )
            ],
        )

        self.assertIsNone(option.content)
        self.assertEqual(option.images[0].uri, "assets/microscope-view.png")

    def test_duplicate_option_labels_are_rejected(self):
        with self.assertRaises(ValidationError):
            Question(
                question_type=QuestionType.SINGLE_CHOICE,
                stem="Choose one.",
                source=source_payload(),
                options=[
                    {"label": "A", "content": "First"},
                    {"label": "a", "content": "Second"},
                ],
            )

    def test_empty_required_content_is_rejected(self):
        with self.assertRaises(ValidationError):
            Question(
                question_type=QuestionType.SHORT_ANSWER,
                stem="   ",
                source=source_payload(),
            )

        with self.assertRaises(ValidationError):
            QuestionOption(label="A")

    def test_question_requires_source(self):
        with self.assertRaises(ValidationError):
            Question(
                question_type=QuestionType.SHORT_ANSWER,
                stem="Name the organelle.",
            )

    def test_collection_defaults_are_not_shared(self):
        first = Question(
            question_type=QuestionType.SHORT_ANSWER,
            stem="First question",
            source=source_payload("first-source"),
        )
        second = Question(
            question_type=QuestionType.SHORT_ANSWER,
            stem="Second question",
            source=source_payload("second-source"),
        )

        first.images.append(
            QuestionImage(
                **image_payload(
                    "first-image",
                    "assets/first.png",
                )
            )
        )
        self.assertEqual(second.images, [])


if __name__ == "__main__":
    unittest.main()
