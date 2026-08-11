from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Path, Request, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.modules.paper_agent.graph import PaperGraphState, paper_agent_graph
from app.modules.paper_agent.schemas.assembly import (
    PaperAssemblyRequest,
    PaperAssemblyResult,
)
from app.modules.paper_agent.schemas.checkpoint import (
    PaperGraphTaskResponse,
    PaperGraphTaskResume,
    PaperGraphTaskStart,
    TeacherReviewCommand,
    TeacherReviewTaskResponse,
    TeacherReviewTaskStart,
)
from app.modules.paper_agent.schemas.paper_job import PaperJobStatus
from app.modules.paper_agent.schemas.taxonomy import (
    BiologyTaxonomyResponse,
    PaperJobQuestionCreate,
    PaperJobQuestionCreated,
)
from app.modules.paper_agent.schemas.task import (
    PaperTaskCreate,
    PaperTaskResponse,
    PaperTaskReview,
)
from app.modules.paper_agent.services.persistence import (
    PersistenceConflictError,
    UnknownTaxonomyCodeError,
    create_job_with_question,
)
from app.modules.paper_agent.services.checkpoint import (
    GraphTaskAlreadyExistsError,
    GraphTaskNotFoundError,
    GraphTaskNotResumableError,
    get_graph_task_state,
    resume_graph_task,
    start_graph_task,
    TeacherReviewAlreadyExistsError,
    TeacherReviewNotFoundError,
    TeacherReviewNotPendingError,
    get_teacher_review_state,
    start_teacher_review,
    submit_teacher_review,
)
from app.modules.paper_agent.services.assembly import (
    InsufficientQuestionBankError,
    assemble_paper,
)
from app.modules.paper_agent.services.taxonomy import get_biology_taxonomy
from app.modules.paper_agent.services.task import (
    PaperTaskNotFoundError,
    PaperTaskNotReviewableError,
    PaperTaskReplacementError,
    create_paper_task,
    get_paper_task,
    review_paper_task,
)


router = APIRouter(prefix="/paper-agent", tags=["paper-agent"])
ThreadId = Annotated[
    str,
    Path(
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$",
    ),
]


def get_checkpointed_paper_graph(request: Request) -> Any:
    graph = getattr(request.app.state, "paper_agent_graph", None)
    if graph is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="paper graph runtime is not ready",
        )
    return graph


def get_teacher_review_graph(request: Request) -> Any:
    graph = getattr(request.app.state, "paper_agent_teacher_review_graph", None)
    if graph is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="teacher review graph runtime is not ready",
        )
    return graph


def teacher_review_response(
    thread_id: str,
    state: PaperGraphState,
) -> TeacherReviewTaskResponse:
    return TeacherReviewTaskResponse(
        thread_id=thread_id,
        awaiting_teacher=(
            state.execution.status == PaperJobStatus.AWAITING_REVIEW
        ),
        state=state,
    )


@router.get("/health")
async def paper_agent_health(request: Request):
    checkpointer_ready = hasattr(request.app.state, "paper_agent_checkpointer")
    teacher_review_ready = hasattr(
        request.app.state,
        "paper_agent_teacher_review_graph",
    )
    ready = checkpointer_ready and teacher_review_ready
    return {
        "module": "paper_agent",
        "status": "ready" if ready else "starting",
        "checkpointer": "postgresql" if checkpointer_ready else None,
        "teacher_review": "interrupt" if teacher_review_ready else None,
    }


@router.get(
    "/taxonomy/biology",
    response_model=BiologyTaxonomyResponse,
)
async def biology_taxonomy(
    db: AsyncSession = Depends(get_db),
) -> BiologyTaxonomyResponse:
    return await get_biology_taxonomy(db)


@router.post(
    "/jobs/with-question",
    response_model=PaperJobQuestionCreated,
    status_code=status.HTTP_201_CREATED,
)
async def create_paper_job_with_question(
    payload: PaperJobQuestionCreate,
    db: AsyncSession = Depends(get_db),
) -> PaperJobQuestionCreated:
    try:
        result = await create_job_with_question(db, payload)
        await db.commit()
        return result
    except UnknownTaxonomyCodeError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    except (PersistenceConflictError, IntegrityError) as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="job, question, source, or resource already exists",
        ) from exc


@router.post(
    "/papers/assemble",
    response_model=PaperAssemblyResult,
)
async def assemble_basic_paper(
    payload: PaperAssemblyRequest,
    db: AsyncSession = Depends(get_db),
) -> PaperAssemblyResult:
    try:
        return await assemble_paper(db, payload)
    except InsufficientQuestionBankError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                "code": "INSUFFICIENT_QUESTION_BANK",
                "question_type": exc.section.question_type.value,
                "difficulty": exc.section.difficulty.value,
                "required": exc.required,
                "available": exc.available,
            },
        ) from exc


@router.post("/graph/smoke")
async def paper_agent_graph_smoke():
    initial_state = PaperGraphState(job_id="smoke-test")
    result = await paper_agent_graph.ainvoke(initial_state)
    validated_result = PaperGraphState.model_validate(result)
    return {
        "graph": "paper_agent",
        "result": validated_result.model_dump(mode="json"),
    }


@router.post(
    "/graph/tasks/{thread_id}",
    response_model=PaperGraphTaskResponse,
    status_code=status.HTTP_201_CREATED,
)
async def start_checkpointed_graph_task(
    thread_id: ThreadId,
    payload: PaperGraphTaskStart,
    graph: Any = Depends(get_checkpointed_paper_graph),
) -> PaperGraphTaskResponse:
    try:
        state = await start_graph_task(graph, thread_id, payload)
    except GraphTaskAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="graph task thread already exists",
        ) from exc
    return PaperGraphTaskResponse(thread_id=thread_id, state=state)


@router.get(
    "/graph/tasks/{thread_id}",
    response_model=PaperGraphTaskResponse,
)
async def read_checkpointed_graph_task(
    thread_id: ThreadId,
    graph: Any = Depends(get_checkpointed_paper_graph),
) -> PaperGraphTaskResponse:
    state = await get_graph_task_state(graph, thread_id)
    if state is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="graph task thread was not found",
        )
    return PaperGraphTaskResponse(thread_id=thread_id, state=state)


@router.post(
    "/graph/tasks/{thread_id}/resume",
    response_model=PaperGraphTaskResponse,
)
async def resume_checkpointed_graph_task(
    thread_id: ThreadId,
    payload: PaperGraphTaskResume,
    graph: Any = Depends(get_checkpointed_paper_graph),
) -> PaperGraphTaskResponse:
    try:
        state = await resume_graph_task(graph, thread_id, payload)
    except GraphTaskNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="graph task thread was not found",
        ) from exc
    except GraphTaskNotResumableError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="only queued graph tasks can be resumed",
        ) from exc
    return PaperGraphTaskResponse(thread_id=thread_id, state=state)


@router.post(
    "/reviews/{thread_id}",
    response_model=TeacherReviewTaskResponse,
    status_code=status.HTTP_201_CREATED,
)
async def start_teacher_review_task(
    thread_id: ThreadId,
    payload: TeacherReviewTaskStart,
    graph: Any = Depends(get_teacher_review_graph),
) -> TeacherReviewTaskResponse:
    try:
        state = await start_teacher_review(graph, thread_id, payload)
    except TeacherReviewAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="teacher review thread already exists",
        ) from exc
    return teacher_review_response(thread_id, state)


@router.get(
    "/reviews/{thread_id}",
    response_model=TeacherReviewTaskResponse,
)
async def read_teacher_review_task(
    thread_id: ThreadId,
    graph: Any = Depends(get_teacher_review_graph),
) -> TeacherReviewTaskResponse:
    state = await get_teacher_review_state(graph, thread_id)
    if state is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="teacher review thread was not found",
        )
    return teacher_review_response(thread_id, state)


@router.post(
    "/reviews/{thread_id}/actions",
    response_model=TeacherReviewTaskResponse,
)
async def submit_teacher_review_action(
    thread_id: ThreadId,
    payload: TeacherReviewCommand,
    graph: Any = Depends(get_teacher_review_graph),
) -> TeacherReviewTaskResponse:
    try:
        state = await submit_teacher_review(graph, thread_id, payload)
    except TeacherReviewNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="teacher review thread was not found",
        ) from exc
    except TeacherReviewNotPendingError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="teacher review is not awaiting an action",
        ) from exc
    return teacher_review_response(thread_id, state)


@router.post(
    "/tasks",
    response_model=PaperTaskResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_assembly_task(
    payload: PaperTaskCreate,
    db: AsyncSession = Depends(get_db),
    review_graph: Any = Depends(get_teacher_review_graph),
) -> PaperTaskResponse:
    try:
        return await create_paper_task(db, review_graph, payload)
    except InsufficientQuestionBankError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                "code": "INSUFFICIENT_QUESTION_BANK",
                "question_type": exc.section.question_type.value,
                "difficulty": exc.section.difficulty.value,
                "required": exc.required,
                "available": exc.available,
            },
        ) from exc


@router.get(
    "/tasks/{job_id}",
    response_model=PaperTaskResponse,
)
async def read_assembly_task(
    job_id: ThreadId,
    db: AsyncSession = Depends(get_db),
) -> PaperTaskResponse:
    try:
        return await get_paper_task(db, job_id)
    except PaperTaskNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="paper task was not found",
        ) from exc


@router.post(
    "/tasks/{job_id}/review",
    response_model=PaperTaskResponse,
)
async def review_assembly_task(
    job_id: ThreadId,
    payload: PaperTaskReview,
    db: AsyncSession = Depends(get_db),
    review_graph: Any = Depends(get_teacher_review_graph),
) -> PaperTaskResponse:
    try:
        return await review_paper_task(db, review_graph, job_id, payload)
    except PaperTaskNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="paper task was not found",
        ) from exc
    except PaperTaskNotReviewableError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="paper task is not awaiting teacher review",
        ) from exc
    except PaperTaskReplacementError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
