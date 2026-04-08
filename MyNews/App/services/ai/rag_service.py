import asyncio
import html
import logging
import os
import re
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from openai import AsyncOpenAI
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, FieldCondition, Filter, MatchValue, PointStruct, VectorParams

from crud import news as news_crud
from schemas.ai import AIRAGChunkItemOut, AIRAGChunkListOut, AIRAGIndexStatusOut, AIQACitationOut, AIQAOut
from services.ai.client import AIClient, AIClientError
from services.ai.prompts import build_qa_messages


logger = logging.getLogger(__name__)


class RAGService:
    def __init__(self):
        self._last_rebuild_at: datetime | None = None
        self._lock = asyncio.Lock()

        self.chunk_size = int(os.getenv("RAG_CHUNK_SIZE", "500"))
        self.chunk_overlap = int(os.getenv("RAG_CHUNK_OVERLAP", "80"))
        self.embedding_model = os.getenv("AI_EMBEDDING_MODEL", "text-embedding-3-small").strip()
        self.embedding_timeout = float(os.getenv("AI_EMBEDDING_TIMEOUT_SECONDS", "30"))
        self.embed_batch_size = int(os.getenv("RAG_EMBED_BATCH_SIZE", "10"))
        self.collection_name = os.getenv("RAG_QDRANT_COLLECTION", "mynews_rag")
        self.qdrant_url = os.getenv("QDRANT_URL", "http://127.0.0.1:6333").strip()
        self.qdrant_api_key = os.getenv("QDRANT_API_KEY", "").strip()

        self.api_base_url = os.getenv("AI_API_BASE_URL", "https://api.openai.com/v1").rstrip("/")
        self.api_key = os.getenv("AI_API_KEY", "").strip()

        self.qdrant = QdrantClient(
            url=self.qdrant_url,
            api_key=self.qdrant_api_key or None,
            timeout=self.embedding_timeout,
        )
        self._ali_client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.api_base_url or "https://dashscope.aliyuncs.com/compatible-mode/v1",
        )

    def _embedding_batch_limit(self) -> int:
        # DashScope 兼容 embedding 接口单次 input.contents 上限为 10。
        if "dashscope.aliyuncs.com" in self.api_base_url:
            return 10
        return max(1, int(os.getenv("RAG_EMBED_BATCH_HARD_LIMIT", "64")))

    async def _embed_documents(self, texts: list[str], batch_size: int) -> list[list[float]]:
        """兼容 embedding 调用：按服务端上限分批，失败时自动降批重试。"""
        if not texts:
            return []

        provider_limit = self._embedding_batch_limit()
        current_batch_size = max(1, min(batch_size, provider_limit))

        all_vecs: list[list[float]] = []
        for retry in range(3):
            try:
                all_vecs = []
                for i in range(0, len(texts), current_batch_size):
                    batch = texts[i:i + current_batch_size]
                    resp = await self._ali_client.embeddings.create(model=self.embedding_model, input=batch)
                    vecs = [item.embedding for item in sorted(resp.data, key=lambda x: x.index)]
                    all_vecs.extend(vecs)
                    logger.info("📥 Embedding 进度: %s/%s (batch=%s)", min(i + current_batch_size, len(texts)), len(texts), current_batch_size)
                return all_vecs
            except Exception as e:
                text = str(e)
                if "batch size is invalid" in text.lower() and current_batch_size > 1:
                    current_batch_size = max(1, min(provider_limit, current_batch_size // 2))
                    logger.warning("⚠️ 服务端拒绝当前批大小，自动降批为 %s 后重试", current_batch_size)

                if retry == 2:
                    raise
                logger.warning("⚠️ Embedding 重试 %s/3: %s", retry + 1, e)
                await asyncio.sleep(2 ** retry)

        return all_vecs

    async def _embed_query(self, query: str) -> list[float]:
        question = self._to_plain_text(query)
        if not question:
            raise AIClientError("问题内容为空，无法执行向量检索")
        try:
            resp = await self._ali_client.embeddings.create(model=self.embedding_model, input=[question])
            vecs = [item.embedding for item in sorted(resp.data, key=lambda x: x.index)]
        except Exception as exc:
            raise AIClientError(f"查询向量生成失败: {exc}") from exc

        if not vecs:
            raise AIClientError("查询向量生成为空")
        return vecs[0]

    def _collection_exists(self) -> bool:
        try:
            return self.qdrant.collection_exists(self.collection_name)
        except Exception as exc:
            raise AIClientError(f"Qdrant 连接失败: {exc}") from exc

    def _get_collection_vector_size(self) -> int | None:
        if not self._collection_exists():
            return None
        info = self.qdrant.get_collection(self.collection_name)
        vectors = info.config.params.vectors
        if hasattr(vectors, "size"):
            return int(vectors.size)
        if isinstance(vectors, dict):
            first = next(iter(vectors.values()), None)
            if first is not None and hasattr(first, "size"):
                return int(first.size)
        return None

    def _ensure_collection(self, vector_size: int):
        # 全量重建场景：为避免残留旧点位，始终重建 collection。
        if self._collection_exists():
            self.qdrant.delete_collection(self.collection_name)
        self.qdrant.create_collection(
            collection_name=self.collection_name,
            vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
        )

    def _delete_news_points(self, news_id: int):
        if not self._collection_exists():
            return
        self.qdrant.delete(
            collection_name=self.collection_name,
            points_selector=Filter(
                must=[
                    FieldCondition(
                        key="news_id",
                        match=MatchValue(value=news_id),
                    )
                ]
            ),
            wait=True,
        )

    @staticmethod
    def _iter_batches(items: list, batch_size: int):
        safe_batch = max(1, batch_size)
        for start in range(0, len(items), safe_batch):
            end = min(start + safe_batch, len(items))
            yield start, end, items[start:end]

    def _split_text(self, text: str) -> list[str]:
        """Paragraph Splitter: 先按段落切分，再按 chunk_size 合并，尾部保留 overlap。"""
        source = (text or "").strip()
        if not source:
            return []

        size = max(120, self.chunk_size)
        overlap = max(0, min(self.chunk_overlap, size - 1))

        paragraphs = [p.strip() for p in re.split(r"\n+", source) if p.strip()]
        # 若原文几乎无段落，则退化到按句子切分，仍走 Paragraph Splitter 逻辑。
        if len(paragraphs) <= 1:
            paragraphs = [p.strip() for p in re.split(r"(?<=[。！？.!?])\s+", source) if p.strip()]
            if not paragraphs:
                paragraphs = [source]

        chunks: list[str] = []
        buffer = ""
        for para in paragraphs:
            candidate = para if not buffer else f"{buffer}\n{para}"
            if len(candidate) <= size:
                buffer = candidate
                continue

            if buffer:
                chunks.append(buffer.strip())
                if overlap > 0:
                    tail = buffer[-overlap:]
                    buffer = f"{tail}\n{para}" if tail else para
                else:
                    buffer = para
            else:
                # 单段超长时兜底按字符切。
                step = max(1, size - overlap)
                for start in range(0, len(para), step):
                    piece = para[start:start + size].strip()
                    if piece:
                        chunks.append(piece)
                buffer = ""

        if buffer.strip():
            chunks.append(buffer.strip())

        return chunks

    @staticmethod
    def _to_plain_text(value: str | None) -> str:
        text = value or ""
        if not text:
            return ""

        # 去除 script/style，避免噪音进入向量库。
        text = re.sub(r"<script[\s\S]*?</script>", " ", text, flags=re.IGNORECASE)
        text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.IGNORECASE)
        # 去除所有 HTML 标签。
        text = re.sub(r"<[^>]+>", " ", text)
        # HTML 实体反转义，如 &nbsp; -> 空格。
        text = html.unescape(text)
        # 合并多余空白与换行。
        text = re.sub(r"[\t\r\n]+", " ", text)
        text = re.sub(r"\s{2,}", " ", text)
        return text.strip()

    def _count_distinct_news_ids(self) -> int:
        if not self._collection_exists():
            return 0

        ids: set[int] = set()
        offset = None
        while True:
            points, next_offset = self.qdrant.scroll(
                collection_name=self.collection_name,
                with_payload=["news_id"],
                with_vectors=False,
                limit=256,
                offset=offset,
            )
            for p in points:
                news_id = (p.payload or {}).get("news_id")
                if isinstance(news_id, int):
                    ids.add(news_id)

            if next_offset is None:
                break
            offset = next_offset

        return len(ids)

    async def rebuild_index(self, db: AsyncSession) -> AIRAGIndexStatusOut:
        if not self.api_key:
            raise AIClientError("AI_API_KEY 未配置，无法构建向量索引")

        async with self._lock:
            logger.info("[RAG] 开始重建索引，collection=%s", self.collection_name)
            rows = await news_crud.get_news_for_rag(db)
            logger.info("[RAG] 已加载可索引新闻数量: %s", len(rows))

            payloads: list[tuple[int, str, str, str, int, float]] = []
            docs: list[str] = []

            # 1️⃣ 生成切片 + 原始文本列表
            for row in rows:
                category_name = self._to_plain_text(row.category.name if row.category else "未知") or "未知"
                title = self._to_plain_text(row.title)
                description = self._to_plain_text(row.description) or "无"
                content = self._to_plain_text(row.content)

                base = f"标题：{title}\n分类：{category_name}\n摘要：{description}\n正文：{content}"
                pieces = self._split_text(base)
                for idx, chunk in enumerate(pieces):
                    # 🔥 chunk 本身就是字符串，直接追加
                    payloads.append((row.id, title, category_name, chunk, idx, row.publish_time.timestamp()))
                    docs.append(chunk)

            cleaned_docs: list[str] = []
            cleaned_payloads: list[tuple[int, str, str, str, int, float]] = []
            for i, text in enumerate(docs):
                if text is None or not isinstance(text, str):
                    logger.warning("⚠️ 跳过非法文本 (idx=%s)", i)
                    continue
                safe_text = text.strip()
                if not safe_text:
                    continue
                if len(safe_text) > 8000:
                    safe_text = safe_text[:8000] + "..."
                cleaned_docs.append(safe_text)
                news_id, title, category_name, _, chunk_index, publish_ts = payloads[i]
                cleaned_payloads.append((news_id, title, category_name, safe_text, chunk_index, publish_ts))

            docs = cleaned_docs
            payloads = cleaned_payloads

            if not docs:
                logger.warning("❌ 清洗后无有效文本，跳过 embedding")
                if self._collection_exists():
                    self.qdrant.delete_collection(self.collection_name)
                self._last_rebuild_at = datetime.now()
                return self.get_status()

            logger.info("[RAG] 清洗后有效 chunk 数: %s", len(docs))

        # 4️⃣ 生成首批向量（用于确定 vector_size）
        logger.info("[RAG] 开始生成 embedding...")
        first_batch_size = min(self.embed_batch_size, len(docs), self._embedding_batch_limit())
        first_vectors = await self._embed_documents(docs[:first_batch_size], batch_size=first_batch_size)

        if not first_vectors:
            raise AIClientError("Embedding 生成失败，无有效向量返回")

        # 5️⃣ 确保 Qdrant collection 存在（用实际返回的向量维度）
        actual_vector_size = len(first_vectors[0])
        self._ensure_collection(vector_size=actual_vector_size)
        logger.info("[RAG] Qdrant collection 已准备，vector_size=%s", actual_vector_size)

        # 6️⃣ 批量写入 Qdrant
        point_id = 1
        all_vectors = first_vectors  # 首批已生成

        # 生成剩余批次的向量
        if len(docs) > first_batch_size:
            remaining_vectors = await self._embed_documents(docs[first_batch_size:], batch_size=self.embed_batch_size)
            all_vectors.extend(remaining_vectors)

        # 按 batch 写入 Qdrant（避免单次点太多内存爆炸）
        for start, end, doc_batch in self._iter_batches(docs, self.embed_batch_size):
            payload_batch = payloads[start:end]
            vector_batch = all_vectors[start:end]

            points: list[PointStruct] = []
            for (news_id, title, category_name, snippet, chunk_index, publish_ts), vector in zip(payload_batch, vector_batch):
                points.append(
                    PointStruct(
                        id=point_id,
                        vector=vector,
                        payload={
                            "news_id": news_id,
                            "title": title,
                            "snippet": snippet,
                            "category_name": category_name,
                            "chunk_index": chunk_index,
                            "publish_ts": publish_ts,
                            "audit_status": "approved",  # 🔥 冗余存储，检索时双重过滤
                        },
                    )
                )
                point_id += 1

            self.qdrant.upsert(
                collection_name=self.collection_name,
                points=points,
                wait=True,  # 同步等待，保证写入成功再继续
            )
            logger.info("[RAG] 进度: %s/%s chunks 已写入", end, len(docs))

        # 7️⃣ 更新状态
        self._last_rebuild_at = datetime.now()
        logger.info("[RAG] 重建完成，总耗时结束时间: %s", self._last_rebuild_at.isoformat())
        return self.get_status()

    async def sync_news_index(self, db: AsyncSession, news_id: int):
        if not self.api_key:
            logger.warning("[RAG] 未配置 AI_API_KEY，跳过增量索引同步 news_id=%s", news_id)
            return

        async with self._lock:
            row = await news_crud.get_news_by_id_plain(db, news_id)

            # 非通过状态或已删除：从向量库移除，避免检索到下架内容。
            if not row or row.is_deleted or row.audit_status != "approved":
                self._delete_news_points(news_id)
                logger.info("[RAG] 已移除新闻索引 news_id=%s", news_id)
                return

            category_name = self._to_plain_text(row.category.name if row.category else "未知") or "未知"
            title = self._to_plain_text(row.title)
            description = self._to_plain_text(row.description) or "无"
            content = self._to_plain_text(row.content)

            base = f"标题：{title}\n分类：{category_name}\n摘要：{description}\n正文：{content}"
            chunks = self._split_text(base)

            if not chunks:
                self._delete_news_points(news_id)
                logger.info("[RAG] 新闻无有效文本，已移除索引 news_id=%s", news_id)
                return

            docs: list[str] = []
            for chunk in chunks:
                text = chunk.strip()
                if not text:
                    continue
                if len(text) > 8000:
                    text = text[:8000] + "..."
                docs.append(text)

            if not docs:
                self._delete_news_points(news_id)
                logger.info("[RAG] 新闻文本清洗后为空，已移除索引 news_id=%s", news_id)
                return

            vectors = await self._embed_documents(
                docs,
                batch_size=min(self.embed_batch_size, len(docs), self._embedding_batch_limit()),
            )
            if not vectors:
                raise AIClientError("增量索引构建失败，无有效向量返回")

            vector_size = len(vectors[0])
            current_vector_size = self._get_collection_vector_size()
            if current_vector_size is None:
                self.qdrant.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
                )
            elif current_vector_size != vector_size:
                raise AIClientError(
                    "向量维度与现有索引不一致，请先执行 /ai/rag/index/rebuild 全量重建"
                )

            self._delete_news_points(news_id)

            publish_ts = row.publish_time.timestamp() if row.publish_time else datetime.now().timestamp()
            points: list[PointStruct] = []
            for idx, (snippet, vector) in enumerate(zip(docs, vectors)):
                point_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"mynews-rag-{news_id}-{idx}"))
                points.append(
                    PointStruct(
                        id=point_uuid,
                        vector=vector,
                        payload={
                            "news_id": row.id,
                            "title": title,
                            "snippet": snippet,
                            "category_name": category_name,
                            "chunk_index": idx,
                            "publish_ts": publish_ts,
                            "audit_status": "approved",
                        },
                    )
                )

            self.qdrant.upsert(
                collection_name=self.collection_name,
                points=points,
                wait=True,
            )
            logger.info("[RAG] 增量索引同步完成 news_id=%s chunks=%s", news_id, len(points))

    def get_status(self) -> AIRAGIndexStatusOut:
        indexed_chunk_count = 0
        indexed_news_count = 0
        if self._collection_exists():
            indexed_chunk_count = self.qdrant.count(
                collection_name=self.collection_name,
                exact=True,
            ).count
            indexed_news_count = self._count_distinct_news_ids()

        return AIRAGIndexStatusOut(
            indexed_news_count=indexed_news_count,
            indexed_chunk_count=indexed_chunk_count,
            embedding_model=self.embedding_model,
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            last_rebuild_at=self._last_rebuild_at,
        )

    def clear_index(self) -> bool:
        if not self._collection_exists():
            return True
        self.qdrant.delete_collection(self.collection_name)
        return True

    def list_chunks(self, page: int = 1, size: int = 20, news_id: int | None = None) -> AIRAGChunkListOut:
        safe_page = max(1, page)
        safe_size = max(1, min(size, 100))

        if not self._collection_exists():
            return AIRAGChunkListOut(items=[], page=safe_page, size=safe_size, total=0)

        all_items: list[AIRAGChunkItemOut] = []
        offset: Any = None
        while True:
            points, next_offset = self.qdrant.scroll(
                collection_name=self.collection_name,
                with_payload=True,
                with_vectors=False,
                limit=256,
                offset=offset,
            )

            for point in points:
                payload = point.payload or {}
                p_news_id = payload.get("news_id")
                if news_id is not None and p_news_id != news_id:
                    continue

                all_items.append(
                    AIRAGChunkItemOut(
                        point_id=str(point.id),
                        news_id=int(payload.get("news_id", 0) or 0),
                        title=str(payload.get("title", "")),
                        snippet=str(payload.get("snippet", "")),
                        category_name=str(payload.get("category_name", "")),
                        chunk_index=int(payload.get("chunk_index", 0) or 0),
                        publish_ts=float(payload.get("publish_ts", 0.0) or 0.0),
                    )
                )

            if next_offset is None:
                break
            offset = next_offset

        all_items.sort(key=lambda item: (item.news_id, item.chunk_index))
        total = len(all_items)
        start = (safe_page - 1) * safe_size
        end = start + safe_size
        return AIRAGChunkListOut(items=all_items[start:end], page=safe_page, size=safe_size, total=total)

    async def answer_question(self, question: str, top_k: int, ai_client: AIClient) -> AIQAOut:
        if not self.api_key:
            raise AIClientError("AI_API_KEY 未配置，无法执行RAG问答")
        if not self._collection_exists():
            raise AIClientError("RAG 索引为空，请先执行索引构建")

        points_count = self.qdrant.count(collection_name=self.collection_name, exact=True).count
        if points_count <= 0:
            raise AIClientError("RAG 索引为空，请先执行索引构建")

        query_vector = await self._embed_query(question)

        ranked = self.qdrant.search(
            collection_name=self.collection_name,
            query_vector=query_vector,
            limit=top_k,
            with_payload=True,
            with_vectors=False,
        )

        citations = [
            AIQACitationOut(
                news_id=int((item.payload or {}).get("news_id", 0)),
                title=str((item.payload or {}).get("title", "")),
                snippet=str((item.payload or {}).get("snippet", "")),
                score=round(float(item.score or 0), 4),
            )
            for item in ranked
            if (item.payload or {}).get("news_id")
        ]

        if not citations:
            raise AIClientError("未检索到相关内容，请尝试更具体的问题")

        context_blocks = [
            f"[来源{i+1}] 新闻ID={c.news_id} 标题={c.title}\n片段：{c.snippet}"
            for i, c in enumerate(citations)
        ]

        messages = build_qa_messages(question=question, context_blocks=context_blocks)
        answer, model = await ai_client.chat_messages(messages=messages, temperature=0.2)

        return AIQAOut(answer=answer, model=model, citations=citations)


rag_service = RAGService()
