import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.modules.paper_agent.services.document_extraction import _extract_pdf


class FakeImage:
    def __init__(self, name, data):
        self.name = name
        self.data = data


class FakeContents:
    def get_data(self):
        return b"short-content-stream"


class FakePage:
    def __init__(self, images, events):
        self.images = images
        self.events = events
        self.mediabox = SimpleNamespace(top=1000)

    def get_contents(self):
        return FakeContents()

    def extract_text(self, *, visitor_operand_before, visitor_text):
        for event in self.events:
            if event[0] == "text":
                visitor_text(event[1], None, None, None, 10)
            else:
                visitor_operand_before(
                    b"Do",
                    [f"/{event[1]}"],
                    [1, 0, 0, 1, 10, event[2]],
                    None,
                )
        return "ignored"


class DocumentExtractionTests(unittest.TestCase):
    def test_pdf_images_follow_stream_order_and_repeated_edge_art_is_removed(self):
        watermark = b"same-watermark"
        pages = [
            FakePage(
                [
                    FakeImage("WM1.png", watermark),
                    FakeImage("FIG1.png", b"figure-one"),
                ],
                [
                    ("image", "WM1", 960),
                    ("text", "1. 观察图示，选择正确答案。\n"),
                    ("image", "FIG1", 500),
                    ("text", "A. 甲\nB. 乙\n2. 跨页图题。\n"),
                ],
            ),
            FakePage(
                [
                    FakeImage("WM2.png", watermark),
                    FakeImage("FIG2.png", b"figure-two"),
                ],
                [
                    ("image", "WM2", 960),
                    ("image", "FIG2", 800),
                    ("text", "A. 丙\nB. 丁\n3. 无图题。\n"),
                ],
            ),
            FakePage(
                [FakeImage("WM3.png", watermark)],
                [
                    ("image", "WM3", 960),
                    ("text", "A. 戊\nB. 己\n"),
                ],
            ),
        ]

        with patch(
            "app.modules.paper_agent.services.document_extraction.PdfReader",
            return_value=SimpleNamespace(pages=pages),
        ):
            result = _extract_pdf(b"%PDF-fake")

        self.assertEqual(
            [asset.marker for asset in result.assets],
            ["pdf-1-1", "pdf-2-1"],
        )
        self.assertNotIn("WM", result.text)
        self.assertLess(
            result.text.index("1. 观察图示"),
            result.text.index("[[image:pdf-1-1]]"),
        )
        self.assertLess(
            result.text.index("2. 跨页图题"),
            result.text.index("[[image:pdf-2-1]]"),
        )
        self.assertLess(
            result.text.index("[[image:pdf-2-1]]"),
            result.text.index("A. 丙"),
        )
        self.assertIn("page boilerplate", " ".join(result.warnings))


if __name__ == "__main__":
    unittest.main()
