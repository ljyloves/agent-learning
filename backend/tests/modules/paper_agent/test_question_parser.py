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
    def test_numeric_table_rows_are_not_treated_as_question_starts(self):
        text = """
20. 某生态系统调查结果如下表，回答问题：
样地 物种数 指数
甲 67.67
乙 86.86
丙 10.40
(1) 比较三个样地的物种丰富度。
(2) 分析群落差异。
答案：(1) 乙最高 (2) 环境条件不同
21. 下列关于生态系统的叙述正确的是？
A. 能量循环利用
B. 物质可以循环
答案：B
"""

        questions = parse_question_text(text, source=SOURCE)

        self.assertEqual(len(questions), 2)
        self.assertEqual(questions[0].question_type.value, "composite")
        self.assertIn("67.67", questions[0].stem)
        self.assertEqual(len(questions[0].subquestions), 2)
        self.assertEqual(questions[1].answer, "B")

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

    def test_parses_exam_preamble_inline_options_and_separate_answers(self):
        text = """
        注意事项：1．答卷前填写姓名。
        2．作答选择题时使用 2B 铅笔。
        一、选择题：本题共 2 小题。
        1．下列细胞结构中含有 DNA 的是（ ）
        A．核糖体 B．中心体 C．线粒体 D．高尔基体
        2．下列有关生态系统的叙述，正确的是（ ）
        A．生产者都是植物
        B．消费者都是动物
        C．分解者只能利用无机物
        D．能量流动通常逐级递减
        二、非选择题：本题共 1 小题。
        （一）必考题：
        17．请回答下列问题
        （1）遗传信息主要储存在哪里？
        （2）控制物质进出细胞的结构是什么？
        2022 年广东省普通高中学业水平选择性考试
        生物学参考答案
        一、选择题：
        1. C 2. D
        二、非选择题：
        （一）必考题：
        17．【答案】（1）细胞核 （2）细胞膜
        """

        questions = parse_question_text(text, source=SOURCE)

        self.assertEqual(len(questions), 3)
        self.assertNotIn("作答选择题", questions[0].stem)
        self.assertEqual(
            [option.label for option in questions[0].options],
            list("ABCD"),
        )
        self.assertEqual(questions[0].answer, "C")
        self.assertEqual(questions[1].answer, "D")
        self.assertEqual(questions[2].question_type.value, "composite")
        self.assertEqual(questions[2].subquestions[0].answer, "细胞核")
        self.assertEqual(questions[2].subquestions[1].answer, "细胞膜")

        genetics = parse_question_text(
            "14．下列有关基因频率的叙述，正确的是（ ）\n"
            "A．选项一\nB．选项二\nC．选项三\n"
            "D．基因重组会影响种群中 H、D 的基因频率",
            source=SOURCE,
        )[0]
        self.assertEqual(len(genetics.options), 4)
        self.assertIn("H、D", genetics.options[-1].content)


if __name__ == "__main__":
    unittest.main()
