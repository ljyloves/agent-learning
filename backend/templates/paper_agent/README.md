# Paper Agent Templates

Version-controlled source templates for generated Word and PDF papers live here.

- `student_paper.docx`: BIO-031 A4 student-paper base template.
- `teacher_answer.docx`: BIO-032 A4 teacher answer and explanation template.
- `answer_sheet.docx`: BIO-033 A4 answer-sheet template.

All templates contain page settings, Word styles, and automatic page-number
fields but no question data. Rebuild them after changing the document services:

```bash
PYTHONPATH=. python scripts/build_student_paper_template.py
```
