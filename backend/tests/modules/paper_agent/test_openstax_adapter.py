import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import httpx
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import settings
from app.models import QuestionModel, QuestionResourceModel, QuestionSourceModel
from app.modules.paper_agent.adapters.openstax import (
    OpenStaxWebsiteAdapter,
    WebsiteNotAllowedError,
)
from app.modules.paper_agent.schemas.ingestion import WebPageCollectRequest
from app.modules.paper_agent.schemas.parsing import QuestionParseRequest
from app.modules.paper_agent.services.question_ingestion import parse_uploaded_questions
from app.modules.paper_agent.services.web_ingestion import collect_openstax_webpage


class OpenStaxWebsiteAdapterTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = create_async_engine(settings.database_url, poolclass=NullPool)
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)
        self.temporary = TemporaryDirectory()
        self.responses = []
        self.allowed_hosts = frozenset({"openstax.org", "www.openstax.org"})

    async def asyncTearDown(self):
        async with self.sessions() as session:
            for response in self.responses:
                await session.execute(
                    delete(QuestionModel).where(
                        QuestionModel.source_id == response.source_id
                    )
                )
                resource = await session.get(
                    QuestionResourceModel,
                    response.resource_id,
                )
                if resource is not None:
                    await session.delete(resource)
                source = await session.get(QuestionSourceModel, response.source_id)
                if source is not None:
                    await session.delete(source)
                Path(response.storage_uri).unlink(missing_ok=True)
            await session.commit()
        self.temporary.cleanup()
        await self.engine.dispose()

    async def test_collects_whitelisted_page_and_persists_source(self):
        calls = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(str(request.url))
            if request.url.path == "/biology":
                return httpx.Response(
                    302,
                    headers={"location": "/biology/index.html"},
                )
            return httpx.Response(
                200,
                headers={"content-type": "text/html; charset=utf-8"},
                content=(
                    "<html><head><title>High School Biology</title></head>"
                    '<body><div data-type="exercise">'
                    '<div data-type="problem"><span class="os-number">1</span>'
                    '<div class="os-problem-container">'
                    '<p>Which structure controls transport across the cell boundary?</p>'
                    '<ol type="a"><li>cell membrane</li><li>cell wall</li>'
                    '<li>ribosome</li><li>chromosome</li></ol>'
                    '</div></div></div></body></html>'
                ).encode(),
            )

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler)
        ) as client:
            async with self.sessions() as session:
                result = await collect_openstax_webpage(
                    session,
                    WebPageCollectRequest(
                        url="https://openstax.org/biology"
                    ),
                    storage_root=Path(self.temporary.name),
                    allowed_hosts=self.allowed_hosts,
                    max_bytes=1024 * 1024,
                    timeout_seconds=5,
                    client=client,
                )
                self.responses.append(result)
                source = await session.get(QuestionSourceModel, result.source_id)
                resource = await session.get(
                    QuestionResourceModel,
                    result.resource_id,
                )
                parsed = await parse_uploaded_questions(
                    session,
                    result.resource_id,
                    QuestionParseRequest(
                        knowledge_point_codes=["BIO-M1-K02"],
                    ),
                    storage_root=Path(self.temporary.name),
                    max_asset_bytes=1024 * 1024,
                )

        self.assertEqual(len(calls), 2)
        self.assertEqual(result.adapter, "openstax")
        self.assertEqual(result.title, "High School Biology")
        self.assertEqual(str(result.source_url), calls[-1])
        self.assertEqual(source.uri, calls[-1])
        self.assertEqual(source.source_type, "website")
        self.assertEqual(source.license, "CC BY-NC-SA")
        self.assertEqual(resource.resource_type, "webpage")
        self.assertTrue(Path(result.storage_uri).is_file())
        self.assertEqual(len(parsed.questions), 1)
        self.assertEqual(parsed.questions[0].question_type.value, "single_choice")
        self.assertEqual(len(parsed.questions[0].options), 4)

    async def test_rejects_non_whitelisted_host_and_external_redirect(self):
        adapter = OpenStaxWebsiteAdapter()
        with self.assertRaises(WebsiteNotAllowedError):
            adapter.canonical_url(
                "https://example.com/biology",
                self.allowed_hosts,
            )

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                302,
                headers={"location": "https://example.com/redirected"},
            )

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler)
        ) as client:
            with self.assertRaises(WebsiteNotAllowedError):
                await adapter.collect(
                    "https://openstax.org/biology",
                    client=client,
                    allowed_hosts=self.allowed_hosts,
                    max_bytes=1024,
                )


if __name__ == "__main__":
    unittest.main()
