from pathlib import Path

from pydantic_settings import BaseSettings
from sqlalchemy import URL


class Settings(BaseSettings):
    # App
    app_name: str = "FlowGate"
    debug: bool = True

    # PostgreSQL
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "flowgate"
    postgres_user: str = "flowgate"
    postgres_password: str = "flowgate_dev"

    # Redis
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_password: str = "flowgate_redis_dev"

    # Qdrant
    qdrant_host: str = "localhost"
    qdrant_rest_port: int = 6333
    qdrant_grpc_port: int = 6334
    qdrant_api_key: str = "flowgate_qdrant_dev"
    qdrant_collection: str = "knowledge_chunks"

    # LLM
    openai_model: str = "gpt-4o-mini"
    openai_base_url: str = "https://api.openai.com/v1"
    openai_api_key: str = ""

    # Paper Agent
    paper_agent_model: str = "gpt-4o-mini"
    paper_agent_storage_path: Path = Path("/app/storage/paper_agent")
    paper_agent_template_path: Path = Path("/app/templates/paper_agent")

    # Embedding
    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_dim: int = 384
    embedding_base_url: str = ""
    embedding_api_key: str = ""

    @property
    def embedding_effective_url(self) -> str:
        return self.embedding_base_url or self.openai_base_url

    @property
    def embedding_effective_key(self) -> str:
        return self.embedding_api_key or self.openai_api_key

    @property
    def database_url(self) -> URL:
        return URL.create(
            drivername="postgresql+asyncpg",
            username=self.postgres_user,
            password=self.postgres_password,
            host=self.postgres_host,
            port=self.postgres_port,
            database=self.postgres_db,
        )

    @property
    def redis_url(self) -> str:
        return f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/0"

    model_config = {"env_file": "../.env", "extra": "ignore"}


settings = Settings()
