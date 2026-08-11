"""Deterministic extraction of review questions from OpenStax HTML."""

from __future__ import annotations

import re
from html.parser import HTMLParser

from app.modules.paper_agent.schemas.question import Question, QuestionDifficulty
from app.modules.paper_agent.schemas.source import QuestionSource
from app.modules.paper_agent.services.question_parser import (
    QuestionParseError,
    parse_question_text,
)


def _clean(parts: list[str]) -> str:
    return re.sub(r"\s+", " ", " ".join(parts)).strip()


def _clean_stem(parts: list[str]) -> str:
    return _clean(parts).lstrip(".．、:： ")


class _OpenStaxExerciseParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: list[tuple[str, dict[str, str]]] = []
        self.exercise_depth: int | None = None
        self.skip_depth: int | None = None
        self.stem_parts: list[str] = []
        self.option_parts: list[str] | None = None
        self.options: list[str] = []
        self.exercises: list[tuple[str, list[str]]] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        attributes = {key: value or "" for key, value in attrs}
        self.stack.append((tag, attributes))
        depth = len(self.stack)
        data_type = attributes.get("data-type", "")
        classes = set(attributes.get("class", "").split())

        if data_type == "exercise" and self.exercise_depth is None:
            self.exercise_depth = depth
            self.stem_parts = []
            self.options = []
            return
        if self.exercise_depth is None:
            return
        if tag in {"script", "style"} or data_type in {
            "solution",
            "question-solution",
        } or "os-solution" in classes or "os-number" in classes:
            self.skip_depth = depth
            return
        if tag == "li" and self._is_answer_option(attributes):
            self.option_parts = []

    def handle_startendtag(self, tag: str, attrs) -> None:
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_data(self, data: str) -> None:
        if self.exercise_depth is None or self.skip_depth is not None:
            return
        text = data.strip()
        if not text:
            return
        if self.option_parts is not None:
            self.option_parts.append(text)
        else:
            self.stem_parts.append(text)

    def handle_endtag(self, tag: str) -> None:
        if not self.stack:
            return
        depth = len(self.stack)
        if self.skip_depth == depth:
            self.skip_depth = None
        if self.option_parts is not None and tag == "li":
            option = _clean(self.option_parts)
            if option:
                self.options.append(option)
            self.option_parts = None
        if self.exercise_depth == depth:
            stem = _clean_stem(self.stem_parts)
            if stem:
                self.exercises.append((stem, list(self.options)))
            self.exercise_depth = None
            self.stem_parts = []
            self.options = []
        self.stack.pop()

    def _is_answer_option(self, attributes: dict[str, str]) -> bool:
        if attributes.get("data-type") == "question-answer":
            return True
        for tag, ancestor in reversed(self.stack[:-1]):
            if tag != "ol":
                continue
            return (
                ancestor.get("type", "").casefold() == "a"
                or ancestor.get("data-type") == "question-answers"
            )
        return False


def parse_openstax_questions(
    html: str,
    *,
    source: QuestionSource,
    difficulty: QuestionDifficulty,
) -> list[Question]:
    parser = _OpenStaxExerciseParser()
    parser.feed(html)
    parser.close()
    if not parser.exercises:
        raise QuestionParseError("OpenStax page does not contain supported exercises")

    lines: list[str] = []
    for number, (stem, options) in enumerate(parser.exercises, start=1):
        lines.append(f"{number}. {stem}")
        lines.extend(
            f"{chr(65 + index)}. {option}"
            for index, option in enumerate(options[:8])
        )
    return parse_question_text(
        "\n".join(lines),
        source=source,
        difficulty=difficulty,
    )
