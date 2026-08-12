"""Rule-based parser for common Chinese teacher question-bank layouts."""

from __future__ import annotations

import re
import uuid
from collections.abc import Mapping, Sequence

from app.modules.paper_agent.schemas.question import (
    Question,
    QuestionDifficulty,
    QuestionImage,
    QuestionOption,
    QuestionType,
)
from app.modules.paper_agent.schemas.source import QuestionSource


class QuestionParseError(ValueError):
    pass


QUESTION_RE = re.compile(r"^\s*(\d{1,4})\s*[.．、]\s*(.*)$")
OPTION_RE = re.compile(r"^\s*([A-HＡ-Ｈ])\s*[.．、:：)）]\s*(.*)$", re.I)
INLINE_OPTION_RE = re.compile(
    r"(?<!\S)([A-HＡ-Ｈ])\s*[.．、:：)）]\s*",
    re.I,
)
SUBQUESTION_RE = re.compile(r"^\s*[(（](\d{1,2})[)）]\s*(.*)$")
ANSWER_RE = re.compile(r"^\s*(?:参考)?答案\s*[:：]?\s*(.*)$")
EXPLANATION_RE = re.compile(r"^\s*(?:答案)?解析\s*[:：]?\s*(.*)$")
IMAGE_RE = re.compile(r"\[\[(?:image|resource):([A-Za-z0-9._:-]+)\]\]", re.I)
LABELED_VALUE_RE = re.compile(r"[(（](\d{1,2})[)）]")
CHOICE_ANSWER_RE = re.compile(
    r"(?<!\d)(\d{1,3})\s*[.．、]\s*([A-HＡ-Ｈ]{1,8})(?=\s|$)",
    re.I,
)
EXAM_ANSWER_HEADING_RE = re.compile(r"参考答案\s*$")
CHOICE_SECTION_RE = re.compile(r"^一\s*[、.]\s*选择题")
SECTION_HEADING_RE = re.compile(
    r"^(?:[一二三四五六七八九十]+\s*[、.]\s*(?:选择题|非选择题)|"
    r"[（(][一二三四五六七八九十]+[）)]\s*(?:必考题|选考题))"
)
BOILERPLATE_LINES = {
    "学科网（北京）股份有限公司",
    "学科网(北京)股份有限公司",
}
FULLWIDTH_LABELS = str.maketrans("ＡＢＣＤＥＦＧＨ", "ABCDEFGH")


def _new_id() -> str:
    return str(uuid.uuid4())


def _expand_inline_options(line: str) -> list[str]:
    matches = list(INLINE_OPTION_RE.finditer(line))
    if not matches or matches[0].start() != 0:
        return [line]
    first_label = matches[0].group(1).upper().translate(FULLWIDTH_LABELS)
    first_index = "ABCDEFGH".index(first_label)
    sequential_matches: list[re.Match[str]] = []
    for match in matches:
        label = match.group(1).upper().translate(FULLWIDTH_LABELS)
        expected_index = first_index + len(sequential_matches)
        if expected_index == 8:
            break
        expected = "ABCDEFGH"[expected_index]
        if label == expected:
            sequential_matches.append(match)
    if len(sequential_matches) < 2:
        return [line]
    expanded: list[str] = []
    for index, match in enumerate(sequential_matches):
        end = (
            sequential_matches[index + 1].start()
            if index + 1 < len(sequential_matches)
            else len(line)
        )
        label = match.group(1).upper().translate(FULLWIDTH_LABELS)
        expanded.append(f"{label}．{line[match.end():end].strip()}")
    return expanded


def _normalize_lines(text: str) -> list[str]:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    lines: list[str] = []
    for raw_line in normalized.split("\n"):
        line = raw_line.strip()
        if not line or line in BOILERPLATE_LINES:
            continue
        lines.extend(_expand_inline_options(line))
    return lines


def _split_exam_document(
    lines: Sequence[str],
) -> tuple[list[str], list[str]]:
    answer_index = next(
        (
            index
            for index, line in enumerate(lines)
            if EXAM_ANSWER_HEADING_RE.search(line)
        ),
        None,
    )
    body_end = len(lines) if answer_index is None else answer_index
    while body_end > 0 and (
        "学业水平选择性考试" in lines[body_end - 1]
        or lines[body_end - 1].replace(" ", "") in {"生物", "生物学"}
    ):
        body_end -= 1
    body = list(lines[:body_end])
    answer_lines = [] if answer_index is None else list(lines[answer_index + 1:])

    choice_section = next(
        (
            index
            for index, line in enumerate(body)
            if CHOICE_SECTION_RE.match(line)
        ),
        None,
    )
    if choice_section is not None:
        body = body[choice_section + 1:]
    body = [line for line in body if not SECTION_HEADING_RE.match(line)]
    answer_lines = [
        line for line in answer_lines if not SECTION_HEADING_RE.match(line)
    ]
    return body, answer_lines


def _split_question_blocks(
    lines: Sequence[str],
) -> list[tuple[int | None, list[str]]]:
    blocks: list[tuple[int | None, list[str]]] = []
    current: list[str] = []
    current_number: int | None = None
    pending_images: list[str] = []
    for line in lines:
        match = QUESTION_RE.match(line)
        if match and re.fullmatch(r"[\d\s.,．%％+-]+", match.group(2)):
            match = None
        if match:
            if current:
                blocks.append((current_number, current))
            current_number = int(match.group(1))
            current = [*pending_images, match.group(2).strip()]
            pending_images = []
        elif current:
            current.append(line)
        elif IMAGE_RE.search(line):
            pending_images.append(line)
    if current:
        blocks.append((current_number, current))
    if not blocks and lines:
        blocks.append((None, list(lines)))
    return blocks


def _extract_content(
    lines: Sequence[str],
    images: Mapping[str, QuestionImage],
) -> tuple[str | None, list[QuestionImage]]:
    content_lines: list[str] = []
    referenced: list[QuestionImage] = []
    seen: set[str] = set()
    for line in lines:
        keys = IMAGE_RE.findall(line)
        for key in keys:
            image = images.get(key)
            if image is None:
                raise QuestionParseError(f"unknown image resource marker: {key}")
            if image.resource_id not in seen:
                referenced.append(image)
                seen.add(image.resource_id)
        cleaned = IMAGE_RE.sub("", line).strip()
        if cleaned:
            content_lines.append(cleaned)
    content = "\n".join(content_lines).strip() or None
    return content, referenced


def _infer_type(
    stem: str,
    options: Sequence[QuestionOption],
    answer: str | list[str] | None,
) -> QuestionType:
    if options:
        answer_text = "" if answer is None else "".join(answer) if isinstance(answer, list) else answer
        labels = set(re.findall(r"[A-H]", answer_text.upper().translate(FULLWIDTH_LABELS)))
        return (
            QuestionType.MULTIPLE_CHOICE
            if len(labels) > 1
            else QuestionType.SINGLE_CHOICE
        )
    if isinstance(answer, str) and answer.strip() in {
        "正确",
        "错误",
        "对",
        "错",
        "√",
        "×",
    }:
        return QuestionType.TRUE_FALSE
    if re.search(r"_{2,}|（\s*）|\(\s*\)", stem):
        return QuestionType.FILL_BLANK
    return QuestionType.SHORT_ANSWER


def _parse_simple_question(
    lines: Sequence[str],
    *,
    source: QuestionSource,
    difficulty: QuestionDifficulty,
    images: Mapping[str, QuestionImage],
) -> Question:
    stem_lines: list[str] = []
    answer_lines: list[str] = []
    explanation_lines: list[str] = []
    option_parts: list[tuple[str, list[str]]] = []
    section = "stem"

    for line in lines:
        answer_match = ANSWER_RE.match(line)
        if answer_match:
            section = "answer"
            if answer_match.group(1).strip():
                answer_lines.append(answer_match.group(1).strip())
            continue
        explanation_match = EXPLANATION_RE.match(line)
        if explanation_match:
            section = "explanation"
            if explanation_match.group(1).strip():
                explanation_lines.append(explanation_match.group(1).strip())
            continue
        option_match = OPTION_RE.match(line) if section not in {"answer", "explanation"} else None
        if option_match:
            section = "option"
            label = option_match.group(1).upper().translate(FULLWIDTH_LABELS)
            option_parts.append((label, [option_match.group(2).strip()]))
            continue

        if section == "stem":
            stem_lines.append(line)
        elif section == "option" and option_parts:
            option_parts[-1][1].append(line)
        elif section == "answer":
            answer_lines.append(line)
        else:
            explanation_lines.append(line)

    stem, stem_images = _extract_content(stem_lines, images)
    if stem is None:
        raise QuestionParseError("question stem is empty after parsing")

    options: list[QuestionOption] = []
    for label, content_lines in option_parts:
        content, option_images = _extract_content(content_lines, images)
        options.append(
            QuestionOption(label=label, content=content, images=option_images)
        )

    answer, answer_images = _extract_content(answer_lines, images)
    explanation, explanation_images = _extract_content(explanation_lines, images)
    if answer_images or explanation_images:
        stem_images.extend(answer_images + explanation_images)

    return Question(
        id=_new_id(),
        question_type=_infer_type(stem, options, answer),
        difficulty=difficulty,
        stem=stem,
        source=source,
        options=options,
        answer=answer,
        explanation=explanation,
        images=stem_images,
    )


def _split_labeled_values(lines: Sequence[str]) -> dict[int, str]:
    text = "\n".join(lines).strip()
    matches = list(LABELED_VALUE_RE.finditer(text))
    if not matches:
        return {}
    values: dict[int, str] = {}
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        value = text[match.end():end].strip(" \n:：;；")
        if value:
            values[int(match.group(1))] = value
    return values


def _parse_composite_question(
    lines: Sequence[str],
    *,
    source: QuestionSource,
    difficulty: QuestionDifficulty,
    images: Mapping[str, QuestionImage],
) -> Question:
    all_sub_indexes = [
        index for index, line in enumerate(lines) if SUBQUESTION_RE.match(line)
    ]
    tail_start = None
    if len(all_sub_indexes) >= 2:
        for index, line in enumerate(lines):
            if index > all_sub_indexes[1] and (
                ANSWER_RE.match(line) or EXPLANATION_RE.match(line)
            ):
                tail_start = index
                break
    sub_indexes = [
        index
        for index in all_sub_indexes
        if tail_start is None or index < tail_start
    ]
    first_sub = sub_indexes[0]
    parent_stem, parent_images = _extract_content(lines[:first_sub], images)
    if parent_stem is None:
        parent_stem = "请回答下列小题。"

    global_lines: Sequence[str] = []
    question_lines = list(lines)
    if tail_start is not None:
        global_lines = lines[tail_start:]
        question_lines = list(lines[:tail_start])

    child_starts = [
        index for index, line in enumerate(question_lines) if SUBQUESTION_RE.match(line)
    ]
    children: list[Question] = []
    child_numbers: list[int] = []
    for offset, start in enumerate(child_starts):
        match = SUBQUESTION_RE.match(question_lines[start])
        assert match is not None
        end = child_starts[offset + 1] if offset + 1 < len(child_starts) else len(question_lines)
        child_numbers.append(int(match.group(1)))
        children.append(
            _parse_simple_question(
                [match.group(2), *question_lines[start + 1:end]],
                source=source,
                difficulty=difficulty,
                images=images,
            )
        )

    answer_lines: list[str] = []
    explanation_lines: list[str] = []
    section = "answer"
    for line in global_lines:
        answer_match = ANSWER_RE.match(line)
        explanation_match = EXPLANATION_RE.match(line)
        if answer_match:
            section = "answer"
            if answer_match.group(1):
                answer_lines.append(answer_match.group(1))
        elif explanation_match:
            section = "explanation"
            if explanation_match.group(1):
                explanation_lines.append(explanation_match.group(1))
        elif section == "answer":
            answer_lines.append(line)
        else:
            explanation_lines.append(line)

    answers = _split_labeled_values(answer_lines)
    explanations = _split_labeled_values(explanation_lines)
    for index, number in enumerate(child_numbers):
        updates = {}
        if number in answers:
            updates["answer"] = answers[number]
        if number in explanations:
            updates["explanation"] = explanations[number]
        if updates:
            children[index] = children[index].model_copy(update=updates)

    return Question(
        id=_new_id(),
        question_type=QuestionType.COMPOSITE,
        difficulty=difficulty,
        stem=parent_stem,
        source=source,
        subquestions=children,
        images=parent_images,
    )


def _numbered_answer_blocks(lines: Sequence[str]) -> dict[int, list[str]]:
    blocks: dict[int, list[str]] = {}
    current_number: int | None = None
    for line in lines:
        match = QUESTION_RE.match(line)
        if match and re.fullmatch(r"[\d\s.,．%％+-]+", match.group(2)):
            match = None
        if match:
            current_number = int(match.group(1))
            blocks[current_number] = [match.group(2).strip()]
        elif current_number is not None:
            blocks[current_number].append(line)
    return blocks


def _with_answer(question: Question, answer: str) -> Question:
    payload = question.model_dump(mode="python")
    payload["answer"] = answer
    payload["question_type"] = _infer_type(
        question.stem,
        question.options,
        answer,
    )
    return Question.model_validate(payload)


def _with_subquestion_answers(
    question: Question,
    answer_lines: Sequence[str],
) -> Question:
    cleaned_lines = [
        re.sub(r"^\s*【答案】\s*", "", line).strip()
        for line in answer_lines
    ]
    answers = _split_labeled_values(cleaned_lines)
    if not answers:
        return question
    children: list[Question] = []
    for number, child in enumerate(question.subquestions, start=1):
        answer = answers.get(number)
        children.append(child if answer is None else _with_answer(child, answer))
    payload = question.model_dump(mode="python")
    payload["subquestions"] = children
    return Question.model_validate(payload)


def _apply_exam_answers(
    questions: Sequence[Question],
    question_numbers: Sequence[int | None],
    answer_lines: Sequence[str],
) -> list[Question]:
    if not answer_lines:
        return list(questions)
    answer_text = "\n".join(answer_lines)
    choice_answers = {
        int(match.group(1)): match.group(2).upper().translate(FULLWIDTH_LABELS)
        for match in CHOICE_ANSWER_RE.finditer(answer_text)
    }
    answer_blocks = _numbered_answer_blocks(answer_lines)
    updated: list[Question] = []
    for ordinal, question in enumerate(questions, start=1):
        number = question_numbers[ordinal - 1] or ordinal
        if question.question_type == QuestionType.COMPOSITE:
            updated.append(
                _with_subquestion_answers(
                    question,
                    answer_blocks.get(number, []),
                )
            )
        elif question.options and number in choice_answers:
            updated.append(_with_answer(question, choice_answers[number]))
        else:
            updated.append(question)
    return updated


def parse_question_text(
    text: str,
    *,
    source: QuestionSource,
    difficulty: QuestionDifficulty = QuestionDifficulty.MEDIUM,
    images: Mapping[str, QuestionImage] | None = None,
) -> list[Question]:
    lines = _normalize_lines(text)
    if not lines:
        raise QuestionParseError("document does not contain extractable text")
    question_lines, answer_lines = _split_exam_document(lines)
    image_map = images or {}
    questions: list[Question] = []
    question_numbers: list[int | None] = []
    for number, block in _split_question_blocks(question_lines):
        if any(SUBQUESTION_RE.match(line) for line in block):
            question = _parse_composite_question(
                block,
                source=source,
                difficulty=difficulty,
                images=image_map,
            )
        else:
            question = _parse_simple_question(
                block,
                source=source,
                difficulty=difficulty,
                images=image_map,
            )
        questions.append(question)
        question_numbers.append(number)
    if not questions:
        raise QuestionParseError("no questions were recognized")
    return _apply_exam_answers(questions, question_numbers, answer_lines)
