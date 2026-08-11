import unittest

from app.modules.paper_agent.schemas.question import QuestionImage
from app.modules.paper_agent.services.question_parser import (
    QuestionParseError,
    parse_question_text,
)


SOURCE = {
    "source_id": "teacher-source",
    "source_type": "file",
    "name": "teacher.docx",
    "uri": "/tmp/teacher.docx",
}


class QuestionParserTests(unittest.TestCase):
    def test_recognizes_options_answer_explanation_and_subquestions(self):
        text = """
        1. 下列关于细胞膜的叙述，正确的是
        A. 主要由纤维素组成
        B. 具有选择透过性
        C. 不含蛋白质
        D. 结构完全固定
        答案：B
        解析：细胞膜具有选择透过性。
        2．观察材料并回答问题
        (1) 遗传信息主要储存在哪里？
        (2) 控制物质进出细胞的结构是什么？
        答案：
        (1) 细胞核
        (2) 细胞膜
        解析：
        (1) 细胞核含有遗传物质
        (2) 细胞膜具有选择透过性
        """

        questions = parse_question_text(text, source=SOURCE)

        self.assertEqual(len(questions), 2)
        self.assertEqual(questions[0].question_type.value, "single_choice")
        self.assertEqual([option.label for option in questions[0].options], list("ABCD"))
        self.assertEqual(questions[0].answer, "B")
        self.assertEqual(questions[0].explanation, "细胞膜具有选择透过性。")
        self.assertEqual(questions[1].question_type.value, "composite")
        self.assertEqual(len(questions[1].subquestions), 2)
        self.assertEqual(questions[1].subquestions[0].answer, "细胞核")
        self.assertEqual(questions[1].subquestions[1].answer, "细胞膜")

    def test_attaches_a_shared_image_marker_and_rejects_unknown_markers(self):
        image = QuestionImage(
            resource_id="diagram-image",
            uri="/tmp/diagram.png",
            source=SOURCE,
            mime_type="image/png",
            sha256="a" * 64,
        )
        questions = parse_question_text(
            "1. 观察图示 [[image:diagram-image]]\n答案：细胞\n"
            "2. 再次观察 [[resource:diagram-image]]\n答案：细胞膜",
            source=SOURCE,
            images={"diagram-image": image},
        )

        self.assertEqual(questions[0].images[0].resource_id, "diagram-image")
        self.assertEqual(questions[1].images[0].resource_id, "diagram-image")
        with self.assertRaises(QuestionParseError):
            parse_question_text(
                "1. 观察 [[image:missing-image]]",
                source=SOURCE,
            )


if __name__ == "__main__":
    unittest.main()
