"""Rebuild the version-controlled BIO-031 Word template."""

from pathlib import Path
import sys


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.modules.paper_agent.services.student_paper import (
    TEMPLATE_FILENAME,
    create_student_paper_template,
)
from app.modules.paper_agent.services.paper_companions import (
    ANSWER_SHEET_TEMPLATE_FILENAME,
    TEACHER_TEMPLATE_FILENAME,
    create_answer_sheet_template,
    create_teacher_answer_template,
)


def main() -> None:
    template_root = BACKEND_ROOT / "templates" / "paper_agent"
    template_root.mkdir(parents=True, exist_ok=True)
    templates = (
        (TEMPLATE_FILENAME, create_student_paper_template),
        (TEACHER_TEMPLATE_FILENAME, create_teacher_answer_template),
        (ANSWER_SHEET_TEMPLATE_FILENAME, create_answer_sheet_template),
    )
    for filename, factory in templates:
        destination = template_root / filename
        factory().save(destination)
        print(destination)


if __name__ == "__main__":
    main()
