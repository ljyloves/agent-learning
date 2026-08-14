from pathlib import Path

from pydantic import Field, model_validator
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
    paper_agent_checkpoint_pool_min_size: int = Field(default=1, ge=1, le=20)
    paper_agent_checkpoint_pool_max_size: int = Field(default=5, ge=1, le=50)
    paper_agent_upload_max_bytes: int = Field(
        default=20 * 1024 * 1024,
        ge=1024,
        le=100 * 1024 * 1024,
    )
    paper_agent_webpage_max_bytes: int = Field(
        default=5 * 1024 * 1024,
        ge=1024,
        le=20 * 1024 * 1024,
    )
    paper_agent_web_timeout_seconds: float = Field(default=15.0, ge=1.0, le=60.0)
    paper_agent_allowed_website_hosts: str = "openstax.org,www.openstax.org"
    paper_agent_question_collection: str = "paper_questions"
    paper_agent_retrieval_pool_size: int = Field(default=500, ge=10, le=5000)
    paper_agent_tool_timeout_seconds: float = Field(default=30.0, ge=1.0, le=120.0)
    paper_agent_tool_read_retry_count: int = Field(default=1, ge=0, le=3)
    paper_agent_taxonomy_write_enabled: bool = False

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
    def checkpointer_database_url(self) -> str:
        return URL.create(
            drivername="postgresql",
            username=self.postgres_user,
            password=self.postgres_password,
            host=self.postgres_host,
            port=self.postgres_port,
            database=self.postgres_db,
        ).render_as_string(hide_password=False)

    @property
    def redis_url(self) -> str:
        return f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/0"

    @property
    def paper_agent_allowed_hosts(self) -> frozenset[str]:
        return frozenset(
            host.strip().lower()
            for host in self.paper_agent_allowed_website_hosts.split(",")
            if host.strip()
        )

    @model_validator(mode="after")
    def validate_checkpoint_pool_size(self) -> "Settings":
        if (
            self.paper_agent_checkpoint_pool_max_size
            < self.paper_agent_checkpoint_pool_min_size
        ):
            raise ValueError(
                "paper_agent checkpoint pool max size must be at least min size"
            )
        if not self.paper_agent_allowed_hosts:
            raise ValueError("paper_agent website host whitelist cannot be empty")
        if any(
            "/" in host or ":" in host or "@" in host
            for host in self.paper_agent_allowed_hosts
        ):
            raise ValueError("paper_agent website whitelist must contain hostnames")
        return self

    model_config = {"env_file": "../.env", "extra": "ignore"}


settings = Settings()
