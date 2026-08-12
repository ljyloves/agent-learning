"""Run the repeatable BIO-036 acceptance flow against a live FlowGate API."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

import httpx
from docx import Document
from docx.oxml.ns import qn
from pypdf import PdfReader

from app.database import async_session
from app.modules.paper_agent.services.mvp_acceptance import (
    BIO036_KNOWLEDGE_POINTS,
    BIO036_LEVEL_COUNTS,
    BIO036_REVIEWER,
    bio036_optimization_payload,
    optimized_paper_to_assembly,
    prepare_bio036_candidates,
)


ARTIFACT_REQUESTS = (
    (
        "student-word",
        "student-paper.docx",
        "student",
        {
            "title": "FlowGate 高中生物 MVP 验收样卷",
            "subtitle": "分子与细胞 · 学生卷",
            "grade_name": "高中",
            "duration_minutes": 45,
            "filename": "FlowGate_BIO036_MVP_Student_Paper",
        },
    ),
    (
        "student-pdf",
        "student-paper.pdf",
        "student",
        {
            "title": "FlowGate 高中生物 MVP 验收样卷",
            "subtitle": "分子与细胞 · 学生卷",
            "grade_name": "高中",
            "duration_minutes": 45,
            "filename": "FlowGate_BIO036_MVP_Student_Paper",
        },
    ),
    (
        "teacher-answer-word",
        "teacher-answer.docx",
        "teacher",
        {
            "title": "FlowGate 高中生物 MVP 验收样卷答案与解析",
            "subtitle": "分子与细胞 · 教师用卷",
            "filename": "FlowGate_BIO036_MVP_Teacher_Answer",
        },
    ),
    (
        "teacher-answer-pdf",
        "teacher-answer.pdf",
        "teacher",
        {
            "title": "FlowGate 高中生物 MVP 验收样卷答案与解析",
            "subtitle": "分子与细胞 · 教师用卷",
            "filename": "FlowGate_BIO036_MVP_Teacher_Answer",
        },
    ),
    (
        "answer-sheet-word",
        "answer-sheet.docx",
        "student",
        {
            "title": "FlowGate 高中生物 MVP 验收样卷答题卡",
            "subtitle": "分子与细胞 · 答题卡",
            "grade_name": "高中",
            "filename": "FlowGate_BIO036_MVP_Answer_Sheet",
        },
    ),
    (
        "answer-sheet-pdf",
        "answer-sheet.pdf",
        "student",
        {
            "title": "FlowGate 高中生物 MVP 验收样卷答题卡",
            "subtitle": "分子与细胞 · 答题卡",
            "grade_name": "高中",
            "filename": "FlowGate_BIO036_MVP_Answer_Sheet",
        },
    ),
)


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _docx_text(document: Document) -> str:
    return "\n".join(
        "".join(node.text or "" for node in paragraph.iter(qn("w:t")))
        for paragraph in document._element.iter(qn("w:p"))
    )


def _assert_document(
    content: bytes,
    *,
    filename: str,
    audience: str,
    headers: httpx.Headers,
) -> dict:
    if filename.endswith(".docx"):
        document = Document(BytesIO(content))
        text = _docx_text(document)
        page_count = None
        render_check = None
    else:
        if not content.startswith(b"%PDF-"):
            raise AssertionError(f"{filename} is not a PDF")
        reader = PdfReader(BytesIO(content))
        page_count = len(reader.pages)
        if page_count < 1:
            raise AssertionError(f"{filename} contains no pages")
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
        render_check = headers.get("x-render-check")
        if render_check != "passed":
            raise AssertionError(f"{filename} did not pass the render quality gate")
    if not text.strip():
        raise AssertionError(f"{filename} contains no printable text")
    if audience == "student" and ("答案：" in text or "解析：" in text):
        raise AssertionError(f"{filename} leaks teacher-only content")
    if audience == "teacher" and ("答案：" not in text or "解析：" not in text):
        raise AssertionError(f"{filename} lacks answer or explanation content")
    return {
        "filename": filename,
        "bytes": len(content),
        "sha256": _sha256(content),
        "page_count": page_count,
        "render_check": render_check,
        "expected_image_count": headers.get("x-expected-image-count"),
        "rendered_image_count": headers.get("x-rendered-image-count"),
    }


def _assert_paper(task: dict, candidate_ids: tuple[str, ...]) -> None:
    paper = task["paper"]
    audit = paper["audit"]
    selected = [
        question
        for section in paper["sections"]
        for question in section["questions"]
    ]
    counts = {
        level: sum(item["difficulty_level"] == level for item in selected)
        for level in BIO036_LEVEL_COUNTS
    }
    if paper["question_count"] != 10 or paper["total_score"] != 50:
        raise AssertionError("MVP paper count or score is incorrect")
    if counts != BIO036_LEVEL_COUNTS:
        raise AssertionError(f"MVP difficulty quotas are incorrect: {counts}")
    if {item["question_id"] for item in selected} != set(candidate_ids):
        raise AssertionError("MVP paper did not use the fixed candidate set")
    if not all(
        item.get("source_id")
        and item.get("difficulty_analysis_id")
        and item.get("quality_analysis_id")
        and item.get("knowledge_point_codes")
        and item.get("core_competency_codes")
        for item in selected
    ):
        raise AssertionError("MVP paper contains untraceable or unreviewed questions")
    if not (
        audit["satisfied"]
        and audit["coverage_rate"] == 1.0
        and audit["quality_approved_count"] == 10
        and audit["selected_duplicate_pair_count"] == 0
        and set(audit["covered_knowledge_point_codes"])
        == set(BIO036_KNOWLEDGE_POINTS)
    ):
        raise AssertionError("MVP paper constraint audit failed")


async def run(base_url: str, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    async with async_session() as session:
        candidates = await prepare_bio036_candidates(session)

    timeout = httpx.Timeout(180.0, connect=10.0)
    async with httpx.AsyncClient(base_url=base_url.rstrip("/"), timeout=timeout) as client:
        health = await client.get("/health")
        health.raise_for_status()
        if health.json().get("status") != "healthy":
            raise AssertionError("FlowGate backend is not healthy")

        created_response = await client.post(
            "/paper-agent/optimized-tasks",
            json=bio036_optimization_payload(candidates),
        )
        created_response.raise_for_status()
        created = created_response.json()
        if not (
            created["status"] == "awaiting_review"
            and created["review_status"] == "pending"
            and created["awaiting_teacher"]
        ):
            raise AssertionError("MVP paper did not pause for teacher review")
        _assert_paper(created, candidates.question_ids)

        approved_response = await client.post(
            f"/paper-agent/optimized-tasks/{created['job_id']}/review",
            json={
                "action": "approve",
                "reviewer": BIO036_REVIEWER,
                "comment": "BIO-036 MVP blueprint and paper quality approved.",
            },
        )
        approved_response.raise_for_status()
        approved = approved_response.json()
        if not (
            approved["status"] == "completed"
            and approved["review_status"] == "approved"
            and not approved["awaiting_teacher"]
            and approved["review_result"]["reviewer"] == BIO036_REVIEWER
        ):
            raise AssertionError("MVP paper did not complete teacher approval")

        assembly = optimized_paper_to_assembly(approved["paper"])
        artifacts: list[dict] = []
        for endpoint, filename, audience, request_fields in ARTIFACT_REQUESTS:
            response = await client.post(
                f"/paper-agent/papers/{endpoint}",
                json={"paper": assembly, **request_fields},
            )
            response.raise_for_status()
            artifact = _assert_document(
                response.content,
                filename=filename,
                audience=audience,
                headers=response.headers,
            )
            path = output_dir / filename
            path.write_bytes(response.content)
            artifact["path"] = filename
            artifacts.append(artifact)

    report = {
        "task_id": "BIO-036",
        "status": "passed",
        "executed_at": datetime.now(timezone.utc).isoformat(),
        "job_id": approved["job_id"],
        "mvp_blueprint": {
            "module_code": "BIO-M1",
            "module_name": "分子与细胞",
            "question_type": "single_choice",
            "question_count": 10,
            "score_per_question": 5,
            "total_score": 50,
            "difficulty_level_counts": BIO036_LEVEL_COUNTS,
            "knowledge_point_codes": BIO036_KNOWLEDGE_POINTS,
        },
        "teacher_review": approved["review_result"],
        "constraint_audit": approved["paper"]["audit"],
        "selected_question_ids": list(candidates.question_ids),
        "candidate_core_competency_count": candidates.core_competency_count,
        "artifacts": artifacts,
    }
    report_path = output_dir / "acceptance-report.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return report_path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--base-url",
        default="http://backend:8000/api",
        help="FlowGate API base URL, including the /api prefix",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("/acceptance/FlowGate_BIO036_MVP_Acceptance"),
    )
    args = parser.parse_args()
    report_path = asyncio.run(run(args.base_url, args.output_dir))
    print(report_path)


if __name__ == "__main__":
    main()
