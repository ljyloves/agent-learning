from fastapi import APIRouter, UploadFile, HTTPException
from pydantic import BaseModel

from app.services.rag import index_document

router = APIRouter(prefix="/documents", tags=["documents"])


class DocumentResponse(BaseModel):
    document_id: str
    source: str
    message: str


@router.post("/upload", response_model=DocumentResponse)
async def upload_document(file: UploadFile):
    if not file.filename:
        raise HTTPException(400, "文件名不能为空")

    raw = await file.read()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        # basic PDF hint — full parser comes later
        raise HTTPException(400, "暂不支持该文件编码，请上传 UTF-8 文本文件")

    if not text.strip():
        raise HTTPException(400, "文件内容为空")

    doc_id = await index_document(text=text, source=file.filename)
    return DocumentResponse(document_id=doc_id, source=file.filename, message="文档已上传并索引")
