import os
from typing import Optional, Dict, Any
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()


class Config(BaseModel):
    """HelloAgents配置类"""

    # LLM配置
    default_model: str = os.getenv("LLM_MODEL_ID", "qwen3.6-plus")
    default_provider: str = "Alibaba"
    temperature: float = 0.7
    max_tokens: Optional[int] = None

    # 系统配置
    debug: bool = False
    log_level: str = "INFO"

    # 其他配置
    max_history_length: int = 100

    @classmethod
    def from_env(cls) -> "Config":
        return cls(
            debug=os.getenv("DEBUG", "false").lower() == "true",
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            temperature=float(os.getenv("TEMPERATURE", "0.7")),
            max_tokens=(
                int(os.getenv("MAX_TOKENS")) if os.getenv("MAX_TOKENS") else None
            ),
        )

    def to_dict(self) -> Dict[str, Any]:
        return self.dict()
