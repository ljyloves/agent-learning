import uuid
from datetime import datetime

from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class KnowledgeDocument(Base):
    __tablename__ = "knowledge_documents"

    id: Mapped[str] = mapped_column(primary_key=True, default=lambda: str(uuid.uuid4()))
    filename: Mapped[str]
    file_size: Mapped[int]
    chunk_count: Mapped[int]
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
