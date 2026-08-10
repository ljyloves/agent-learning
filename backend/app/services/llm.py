import httpx
from openai import AsyncOpenAI

from app.config import settings


def get_llm() -> AsyncOpenAI:
    transport = httpx.AsyncHTTPTransport(retries=2, local_address="0.0.0.0")
    http_client = httpx.AsyncClient(transport=transport, timeout=httpx.Timeout(30.0))
    return AsyncOpenAI(
        base_url=settings.openai_base_url,
        api_key=settings.openai_api_key,
        http_client=http_client,
    )


async def chat(messages: list[dict]) -> str:
    client = get_llm()
    response = await client.chat.completions.create(
        model=settings.openai_model,
        messages=messages,
    )
    return response.choices[0].message.content or ""
