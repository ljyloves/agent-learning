from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.modules.paper_agent.graph import paper_agent_graph
from app.modules.paper_agent.schemas.taxonomy import (
    BiologyTaxonomyResponse,
    PaperJobQuestionCreate,
    PaperJobQuestionCreated,
)
from app.modules.paper_agent.services.persistence import (
    PersistenceConflictError,
    UnknownTaxonomyCodeError,
    create_job_with_question,
)
from app.modules.paper_agent.services.taxonomy import get_biology_taxonomy


router = APIRouter(prefix="/paper-agent", tags=["paper-agent"])


@router.get("/health")
async def paper_agent_health():
    return {"module": "paper_agent", "status": "ready"}


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


@router.post("/graph/smoke")
async def paper_agent_graph_smoke():
    result = await paper_agent_graph.ainvoke(
        {
            "job_id": "smoke-test",
            "status": "pending",
            "steps": [],
        }
    )
    return {"graph": "paper_agent", "result": result}
