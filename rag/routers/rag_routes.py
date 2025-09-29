from fastapi import APIRouter, HTTPException
import logging
from models import RAGRequest, RAGResult, DocumentResult
from routers.rag import YandexRAG

logger = logging.getLogger(__name__)
router = APIRouter()

rag_system = YandexRAG()


@router.post('/', response_model=RAGResult)
async def search_documents(req: RAGRequest):
    """Поиск релевантных документов по запросу"""
    try:
        query = req.query.strip()
        top_k = req.top_k

        if not query:
            raise HTTPException(status_code=400, detail="Query cannot be empty")

        if top_k < 1 or top_k > 20:
            raise HTTPException(status_code=400, detail="top_k must be between 1 and 20")

        context, retrieved_docs = rag_system.search(query, top_k)

        document_results = []
        for doc in retrieved_docs:
            document_results.append(DocumentResult(
                content=doc.content,
                source=doc.source,
                score=doc.score,
                rank=doc.rank
            ))

        return RAGResult(
            success=True,
            context=context,
            documents=document_results
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in document search: {e}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")