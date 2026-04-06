import json
from typing import List

from langchain_core.output_parsers import PydanticOutputParser

from services.ai.client import AIClient
from services.ai.prompts import (
    build_draft_suggest_messages,
    build_summary_messages,
)
from schemas.ai import AINewsDraftSuggestIn, AINewsDraftSuggestOut, AINewsSummaryOut


class AIService:
    def __init__(self):
        self.client = AIClient()
        self.draft_parser = PydanticOutputParser(pydantic_object=AINewsDraftSuggestOut)

    async def summarize_news(self, news_id: int, title: str, description: str | None, content: str) -> tuple[AINewsSummaryOut, str]:
        messages = build_summary_messages(title=title, description=description, content=content)
        answer, model = await self.client.chat_messages(
            messages=messages,
            temperature=0.2,
        )

        # 容错解析：按换行拆出最多3条要点。
        lines: List[str] = [line.strip("- *\t ") for line in answer.splitlines() if line.strip()]
        key_points = lines[1:4] if len(lines) > 1 else []
        summary = lines[0] if lines else answer

        return AINewsSummaryOut(news_id=news_id, summary=summary, key_points=key_points), model

    async def suggest_news_draft(self, draft: AINewsDraftSuggestIn) -> tuple[AINewsDraftSuggestOut, str]:
        messages = build_draft_suggest_messages(
            draft=draft,
            format_instructions=self.draft_parser.get_format_instructions(),
        )
        answer, model = await self.client.chat_messages(
            messages=messages,
            temperature=0.4,
        )

        # 优先按 JSON 解析，失败则回退到纯文本。
        title_suggestions: List[str] = []
        content_suggestions: List[str] = []
        description_suggestion = None

        try:
            parsed = self.draft_parser.parse(answer)
            title_suggestions = [str(x).strip() for x in parsed.title_suggestions if str(x).strip()]
            content_suggestions = [str(x).strip() for x in parsed.content_suggestions if str(x).strip()]
            description_suggestion = (
                str(parsed.description_suggestion).strip()
                if parsed.description_suggestion is not None
                else None
            )
        except Exception:
            try:
                payload = json.loads(answer)
                title_suggestions = [str(x).strip() for x in payload.get("title_suggestions", []) if str(x).strip()]
                content_suggestions = [str(x).strip() for x in payload.get("content_suggestions", []) if str(x).strip()]
                desc = payload.get("description_suggestion")
                description_suggestion = str(desc).strip() if desc is not None else None
            except Exception:
                chunks = [line.strip("- *\t ") for line in answer.splitlines() if line.strip()]
                title_suggestions = chunks[:3]
                content_suggestions = chunks[3:6]

        return (
            AINewsDraftSuggestOut(
                title_suggestions=title_suggestions,
                description_suggestion=description_suggestion,
                content_suggestions=content_suggestions,
            ),
            model,
        )
