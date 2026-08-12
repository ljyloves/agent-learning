from typing import Annotated, Any

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Path,
    Request,
    UploadFile,
    status,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi.responses import FileResponse

from app.database import get_db
from app.config import settings
from app.modules.paper_agent.adapters import (
    WebsiteContentError,
    WebsiteFetchError,
    WebsiteNotAllowedError,
    WebsiteTooLargeError,
)
from app.modules.paper_agent.graph import PaperGraphState, paper_agent_graph
from app.modules.paper_agent.schemas.assembly import (
    PaperAssemblyRequest,
    PaperAssemblyResult,
)
from app.modules.paper_agent.schemas.annotation import (
    TaxonomyAnnotationRequest,
    TaxonomyAnnotationResponse,
)
from app.modules.paper_agent.schemas.analysis import (
    DifficultyEstimationResponse,
    QualityReviewResponse,
)
from app.modules.paper_agent.schemas.optimization import (
    OptimizedPaperRequest,
    OptimizedPaperResult,
)
from app.modules.paper_agent.schemas.optimized_task import (
    OptimizedPaperLockUpdate,
    OptimizedPaperReassemble,
    OptimizedPaperReplace,
    OptimizedPaperTaskCreate,
    OptimizedPaperTaskResponse,
    OptimizedPaperTaskReview,
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
from app.modules.paper_agent.schemas.ingestion import (
    IngestedResourceResponse,
    WebPageCollectRequest,
)
from app.modules.paper_agent.schemas.parsing import (
    ParsedQuestionsResponse,
    QuestionParseRequest,
)
from app.modules.paper_agent.schemas.question import Question
from app.modules.paper_agent.schemas.retrieval import (
    HybridQuestionSearchRequest,
    HybridQuestionSearchResponse,
    QuestionIndexRequest,
    QuestionIndexResponse,
)
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
from app.modules.paper_agent.services.optimization import (
    NoFeasiblePaperError,
    OptimizationDataError,
    OptimizationEmbeddingError,
    OptimizationFilterError,
    RequiredQuestionUnavailableError,
    optimize_paper,
)
from app.modules.paper_agent.services.optimized_task import (
    LockedQuestionError,
    OptimizedTaskNotFoundError,
    OptimizedTaskNotReviewableError,
    OptimizedTaskSelectionError,
    create_optimized_task,
    get_optimized_task,
    reassemble_optimized_task,
    replace_optimized_question,
    review_optimized_task,
    update_optimized_task_locks,
)
from app.modules.paper_agent.services.taxonomy import get_biology_taxonomy
from app.modules.paper_agent.services.taxonomy_annotation import (
    TaxonomyAnnotationConfigurationError,
    TaxonomyAnnotationConflictError,
    TaxonomyAnnotationOutputError,
    TaxonomyAnnotationPolicyError,
    TaxonomyAnnotationProviderError,
    annotate_question_taxonomy,
)
from app.modules.paper_agent.services.question_analysis import (
    QuestionAnalysisConfigurationError,
    QuestionAnalysisConflictError,
    QuestionAnalysisOutputError,
    QuestionAnalysisPolicyError,
    QuestionAnalysisPrerequisiteError,
    QuestionAnalysisProviderError,
    estimate_question_difficulty,
    review_question_quality,
)
from app.modules.paper_agent.services.file_ingestion import (
    EmptyUploadError,
    UnsupportedUploadError,
    UploadTooLargeError,
    save_teacher_upload,
)
from app.modules.paper_agent.services.task import (
    PaperTaskNotFoundError,
    PaperTaskNotReviewableError,
    PaperTaskReplacementError,
    create_paper_task,
    get_paper_task,
    review_paper_task,
)
from app.modules.paper_agent.services.web_ingestion import collect_openstax_webpage
from app.modules.paper_agent.services.document_extraction import DocumentExtractionError
from app.modules.paper_agent.services.question_ingestion import parse_uploaded_questions
from app.modules.paper_agent.services.question_parser import QuestionParseError
from app.modules.paper_agent.services.resource_storage import (
    QuestionNotFoundError,
    StoredResourceIntegrityError,
    StoredResourceNotFoundError,
    UnsafeStoredResourceError,
    get_stored_resource_file,
    recover_question,
)
from app.modules.paper_agent.services.retrieval import (
    QuestionIndexSelectionError,
    QuestionVectorStoreError,
    RetrievalFilterError,
    hybrid_search_questions,
    index_questions,
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
ResourceId = Annotated[
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


def optimized_task_http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, OptimizedTaskNotFoundError):
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="optimized paper task was not found",
        )
    if isinstance(
        exc,
        (
            LockedQuestionError,
            OptimizedTaskNotReviewableError,
            OptimizationDataError,
            TeacherReviewNotFoundError,
            TeacherReviewNotPendingError,
        ),
    ):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )
    if isinstance(exc, OptimizationEmbeddingError):
        return HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        )
    if isinstance(exc, NoFeasiblePaperError):
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                "code": "NO_FEASIBLE_PAPER",
                "candidate_count": exc.candidate_count,
                "quota_availability": exc.quota_availability,
            },
        )
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail=str(exc),
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


@router.post(
    "/papers/optimize",
    response_model=OptimizedPaperResult,
)
async def optimize_constrained_paper(
    payload: OptimizedPaperRequest,
    db: AsyncSession = Depends(get_db),
) -> OptimizedPaperResult:
    try:
        return await optimize_paper(db, payload)
    except OptimizationFilterError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    except NoFeasiblePaperError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                "code": "NO_FEASIBLE_PAPER",
                "candidate_count": exc.candidate_count,
                "quota_availability": exc.quota_availability,
            },
        ) from exc
    except OptimizationDataError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except OptimizationEmbeddingError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc


@router.post(
    "/sources/files",
    response_model=IngestedResourceResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_teacher_file(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
) -> IngestedResourceResponse:
    try:
        return await save_teacher_upload(
            db,
            file,
            storage_root=settings.paper_agent_storage_path,
            max_bytes=settings.paper_agent_upload_max_bytes,
        )
    except EmptyUploadError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except UploadTooLargeError as exc:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=str(exc),
        ) from exc
    except UnsupportedUploadError as exc:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=str(exc),
        ) from exc
    finally:
        await file.close()


@router.post(
    "/sources/webpages",
    response_model=IngestedResourceResponse,
    status_code=status.HTTP_201_CREATED,
)
async def collect_whitelisted_webpage(
    payload: WebPageCollectRequest,
    db: AsyncSession = Depends(get_db),
) -> IngestedResourceResponse:
    try:
        return await collect_openstax_webpage(
            db,
            payload,
            storage_root=settings.paper_agent_storage_path,
            allowed_hosts=settings.paper_agent_allowed_hosts,
            max_bytes=settings.paper_agent_webpage_max_bytes,
            timeout_seconds=settings.paper_agent_web_timeout_seconds,
        )
    except WebsiteNotAllowedError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    except WebsiteTooLargeError as exc:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=str(exc),
        ) from exc
    except WebsiteContentError as exc:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=str(exc),
        ) from exc
    except WebsiteFetchError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


@router.post(
    "/sources/resources/{resource_id}/questions",
    response_model=ParsedQuestionsResponse,
    status_code=status.HTTP_201_CREATED,
)
async def parse_teacher_questions(
    resource_id: ResourceId,
    payload: QuestionParseRequest,
    db: AsyncSession = Depends(get_db),
) -> ParsedQuestionsResponse:
    try:
        return await parse_uploaded_questions(
            db,
            resource_id,
            payload,
            storage_root=settings.paper_agent_storage_path,
            max_asset_bytes=settings.paper_agent_upload_max_bytes,
        )
    except StoredResourceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except (
        DocumentExtractionError,
        QuestionParseError,
        UnknownTaxonomyCodeError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    except (StoredResourceIntegrityError, UnsafeStoredResourceError) as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except (PersistenceConflictError, IntegrityError) as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="parsed question or resource conflicts with stored data",
        ) from exc


@router.get(
    "/questions/{question_id}",
    response_model=Question,
)
async def read_parsed_question(
    question_id: ResourceId,
    db: AsyncSession = Depends(get_db),
) -> Question:
    try:
        return await recover_question(db, question_id)
    except QuestionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except StoredResourceIntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc


@router.post(
    "/questions/{question_id}/taxonomy-annotation",
    response_model=TaxonomyAnnotationResponse,
)
async def annotate_question_with_taxonomy(
    question_id: ResourceId,
    payload: TaxonomyAnnotationRequest,
    db: AsyncSession = Depends(get_db),
) -> TaxonomyAnnotationResponse:
    try:
        return await annotate_question_taxonomy(db, question_id, payload)
    except QuestionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except TaxonomyAnnotationConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except TaxonomyAnnotationPolicyError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc
    except TaxonomyAnnotationConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except (
        TaxonomyAnnotationOutputError,
        TaxonomyAnnotationProviderError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="taxonomy annotation conflicts with stored data",
        ) from exc


@router.post(
    "/questions/{question_id}/difficulty-estimation",
    response_model=DifficultyEstimationResponse,
)
async def estimate_difficulty(
    question_id: ResourceId,
    db: AsyncSession = Depends(get_db),
) -> DifficultyEstimationResponse:
    try:
        return await estimate_question_difficulty(db, question_id)
    except QuestionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except QuestionAnalysisPolicyError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc
    except (
        QuestionAnalysisPrerequisiteError,
        QuestionAnalysisConflictError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except QuestionAnalysisConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except (
        QuestionAnalysisOutputError,
        QuestionAnalysisProviderError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="difficulty analysis conflicts with stored data",
        ) from exc


@router.post(
    "/questions/{question_id}/quality-review",
    response_model=QualityReviewResponse,
)
async def review_quality(
    question_id: ResourceId,
    db: AsyncSession = Depends(get_db),
) -> QualityReviewResponse:
    try:
        return await review_question_quality(db, question_id)
    except QuestionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except QuestionAnalysisPolicyError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc
    except (
        QuestionAnalysisPrerequisiteError,
        QuestionAnalysisConflictError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except QuestionAnalysisConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except (
        QuestionAnalysisOutputError,
        QuestionAnalysisProviderError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="quality review conflicts with stored data",
        ) from exc


@router.get("/resources/{resource_id}/content", response_class=FileResponse)
async def read_stored_resource_content(
    resource_id: ResourceId,
    db: AsyncSession = Depends(get_db),
) -> FileResponse:
    try:
        stored = await get_stored_resource_file(
            db,
            resource_id,
            storage_root=settings.paper_agent_storage_path,
        )
    except StoredResourceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except (StoredResourceIntegrityError, UnsafeStoredResourceError) as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    return FileResponse(
        path=stored.path,
        media_type=stored.resource.mime_type,
        filename=(
            stored.path.name
            if stored.resource.resource_type == "image"
            else stored.source.external_id or stored.path.name
        ),
    )


@router.post(
    "/retrieval/questions/index",
    response_model=QuestionIndexResponse,
)
async def index_retrievable_questions(
    payload: QuestionIndexRequest,
    db: AsyncSession = Depends(get_db),
) -> QuestionIndexResponse:
    try:
        return await index_questions(db, payload)
    except QuestionIndexSelectionError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    except QuestionVectorStoreError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc


@router.post(
    "/retrieval/questions/search",
    response_model=HybridQuestionSearchResponse,
)
async def search_retrievable_questions(
    payload: HybridQuestionSearchRequest,
    db: AsyncSession = Depends(get_db),
) -> HybridQuestionSearchResponse:
    try:
        return await hybrid_search_questions(db, payload)
    except RetrievalFilterError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    except QuestionVectorStoreError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
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


@router.post(
    "/optimized-tasks",
    response_model=OptimizedPaperTaskResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_persisted_optimized_task(
    payload: OptimizedPaperTaskCreate,
    db: AsyncSession = Depends(get_db),
    review_graph: Any = Depends(get_teacher_review_graph),
) -> OptimizedPaperTaskResponse:
    try:
        return await create_optimized_task(db, review_graph, payload)
    except (
        NoFeasiblePaperError,
        OptimizationDataError,
        OptimizationEmbeddingError,
        OptimizationFilterError,
        OptimizedTaskSelectionError,
        RequiredQuestionUnavailableError,
    ) as exc:
        await db.rollback()
        raise optimized_task_http_error(exc) from exc
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="optimized paper task conflicts with persisted data",
        ) from exc


@router.get(
    "/optimized-tasks/{job_id}",
    response_model=OptimizedPaperTaskResponse,
)
async def read_persisted_optimized_task(
    job_id: ThreadId,
    db: AsyncSession = Depends(get_db),
) -> OptimizedPaperTaskResponse:
    try:
        return await get_optimized_task(db, job_id)
    except OptimizedTaskNotFoundError as exc:
        raise optimized_task_http_error(exc) from exc


@router.put(
    "/optimized-tasks/{job_id}/locks",
    response_model=OptimizedPaperTaskResponse,
)
async def update_persisted_optimized_task_locks(
    job_id: ThreadId,
    payload: OptimizedPaperLockUpdate,
    db: AsyncSession = Depends(get_db),
) -> OptimizedPaperTaskResponse:
    try:
        return await update_optimized_task_locks(db, job_id, payload)
    except (
        OptimizedTaskNotFoundError,
        OptimizedTaskNotReviewableError,
        OptimizedTaskSelectionError,
    ) as exc:
        await db.rollback()
        raise optimized_task_http_error(exc) from exc


@router.post(
    "/optimized-tasks/{job_id}/replace",
    response_model=OptimizedPaperTaskResponse,
)
async def replace_persisted_optimized_question(
    job_id: ThreadId,
    payload: OptimizedPaperReplace,
    db: AsyncSession = Depends(get_db),
    review_graph: Any = Depends(get_teacher_review_graph),
) -> OptimizedPaperTaskResponse:
    try:
        return await replace_optimized_question(
            db,
            review_graph,
            job_id,
            payload,
        )
    except (
        LockedQuestionError,
        NoFeasiblePaperError,
        OptimizationDataError,
        OptimizationEmbeddingError,
        OptimizationFilterError,
        OptimizedTaskNotFoundError,
        OptimizedTaskNotReviewableError,
        OptimizedTaskSelectionError,
        RequiredQuestionUnavailableError,
        TeacherReviewNotFoundError,
        TeacherReviewNotPendingError,
    ) as exc:
        await db.rollback()
        raise optimized_task_http_error(exc) from exc


@router.post(
    "/optimized-tasks/{job_id}/reassemble",
    response_model=OptimizedPaperTaskResponse,
)
async def reassemble_persisted_optimized_task(
    job_id: ThreadId,
    payload: OptimizedPaperReassemble,
    db: AsyncSession = Depends(get_db),
    review_graph: Any = Depends(get_teacher_review_graph),
) -> OptimizedPaperTaskResponse:
    try:
        return await reassemble_optimized_task(
            db,
            review_graph,
            job_id,
            payload,
        )
    except (
        LockedQuestionError,
        NoFeasiblePaperError,
        OptimizationDataError,
        OptimizationEmbeddingError,
        OptimizationFilterError,
        OptimizedTaskNotFoundError,
        OptimizedTaskNotReviewableError,
        OptimizedTaskSelectionError,
        RequiredQuestionUnavailableError,
        TeacherReviewNotFoundError,
        TeacherReviewNotPendingError,
    ) as exc:
        await db.rollback()
        raise optimized_task_http_error(exc) from exc


@router.post(
    "/optimized-tasks/{job_id}/review",
    response_model=OptimizedPaperTaskResponse,
)
async def review_persisted_optimized_task(
    job_id: ThreadId,
    payload: OptimizedPaperTaskReview,
    db: AsyncSession = Depends(get_db),
    review_graph: Any = Depends(get_teacher_review_graph),
) -> OptimizedPaperTaskResponse:
    try:
        return await review_optimized_task(
            db,
            review_graph,
            job_id,
            payload,
        )
    except (
        OptimizedTaskNotFoundError,
        OptimizedTaskNotReviewableError,
        TeacherReviewNotFoundError,
        TeacherReviewNotPendingError,
    ) as exc:
        await db.rollback()
        raise optimized_task_http_error(exc) from exc
