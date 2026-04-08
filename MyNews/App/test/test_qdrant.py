import asyncio
import logging
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv


APP_DIR = Path(__file__).resolve().parents[1]
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

load_dotenv(APP_DIR / ".env")

from config.db_config import AsyncSessionLocal
from services.ai.rag_service import rag_service
from services.ai.client import AIClient


def _model_dump_safe(model_obj):
    if hasattr(model_obj, "model_dump"):
        return model_obj.model_dump()
    if hasattr(model_obj, "dict"):
        return model_obj.dict()
    return str(model_obj)




async def run_rebuild_and_test(question: str | None = None):
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

    print("===== Qdrant RAG 构建测试开始 =====")
    print(f"QDRANT_URL={os.getenv('QDRANT_URL', 'http://127.0.0.1:6333')}")
    print(f"RAG_QDRANT_COLLECTION={os.getenv('RAG_QDRANT_COLLECTION', 'mynews_rag')}")

    async with AsyncSessionLocal() as session:
        try:
            before = rag_service.get_status()
            print("[Before]", _model_dump_safe(before))

            start = time.perf_counter()
            after = await rag_service.rebuild_index(session)
            duration = time.perf_counter() - start

            print("[After]", _model_dump_safe(after))
            print(f"构建耗时: {duration:.2f}s")

            if question:
                print("\n===== 开始问答测试 =====")
                result = await rag_service.answer_question(question=question, top_k=4, ai_client=AIClient())
                payload = _model_dump_safe(result)
                print("Answer:")
                print(payload.get("answer") if isinstance(payload, dict) else payload)
                print("\nCitations:")
                if isinstance(payload, dict):
                    for idx, item in enumerate(payload.get("citations", []), start=1):
                        print(f"{idx}. news_id={item.get('news_id')} score={item.get('score')} title={item.get('title')}")
        except Exception as exc:
            msg = str(exc)
            print("\n❌ 构建失败:", msg)
            if "batch size is invalid" in msg.lower():
                print("提示：当前 embedding 服务限制单批最多 10 条。请将 RAG_EMBED_BATCH_SIZE 设为 <=10。")
            raise

    print("===== Qdrant RAG 构建测试结束 =====")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Rebuild Qdrant RAG index and optionally run QA test")
    parser.add_argument("--question", type=str, default=None, help="optional QA question")
    args = parser.parse_args()

    asyncio.run(run_rebuild_and_test(question=args.question))
