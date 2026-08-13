"""Persist whitelisted website snapshots and their provenance."""

from __future__ import annotations

import asyncio
import hashlib
import os
import uuid
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import QuestionResourceModel, QuestionSourceModel
from app.modules.paper_agent.adapters.openstax import OpenStaxWebsiteAdapter
from app.modules.paper_agent.schemas.ingestion import (
    IngestedResourceResponse,
    WebPageCollectRequest,
)
from app.modules.paper_agent.schemas.source import ResourceType, SourceType


def _write_atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    try:
        temporary.write_bytes(data)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


async def collect_openstax_webpage(
    session: AsyncSession,
    request: WebPageCollectRequest,
    *,
    storage_root: Path,
    allowed_hosts: frozenset[str],
    max_bytes: int,
    timeout_seconds: float,
    client: httpx.AsyncClient | None = None,
) -> IngestedResourceResponse:
    adapter = OpenStaxWebsiteAdapter()
    owns_client = client is None
    active_client = client or httpx.AsyncClient(timeout=timeout_seconds)
    try:
        page = await adapter.collect(
            str(request.url),
            client=active_client,
            allowed_hosts=allowed_hosts,
            max_bytes=max_bytes,
        )
    finally:
        if owns_client:
            await active_client.aclose()

    source_id = str(uuid.uuid4())
    resource_id = str(uuid.uuid4())
    destination = storage_root / "webpages" / f"{resource_id}.html"
    await asyncio.to_thread(_write_atomic, destination, page.content)
    digest = hashlib.sha256(page.content).hexdigest()
    host = urlsplit(page.final_url).hostname or "openstax.org"
    source_name = (page.title or f"OpenStax page: {host}")[:255]

    try:
        session.add(
            QuestionSourceModel(
                source_id=source_id,
                source_type=SourceType.WEBSITE.value,
                name=source_name,
                uri=page.final_url,
                external_id=(
                    "openstax:"
                    f"{hashlib.sha256(page.final_url.encode()).hexdigest()[:24]}"
                ),
                attribution="OpenStax",
                license="CC BY-NC-SA",
                processing_status="uploaded",
            )
        )
        await session.flush()
        session.add(
            QuestionResourceModel(
                resource_id=resource_id,
                resource_type=ResourceType.WEBPAGE.value,
                uri=str(destination),
                source_id=source_id,
                mime_type=page.content_type,
                sha256=digest,
            )
        )
        await session.commit()
    except Exception:
        await session.rollback()
        await asyncio.to_thread(destination.unlink, missing_ok=True)
        raise

    return IngestedResourceResponse(
        source_id=source_id,
        resource_id=resource_id,
        source_type=SourceType.WEBSITE,
        resource_type=ResourceType.WEBPAGE,
        source_url=page.final_url,
        storage_uri=str(destination),
        mime_type=page.content_type,
        sha256=digest,
        size_bytes=len(page.content),
        title=page.title,
        adapter=adapter.name,
    )
