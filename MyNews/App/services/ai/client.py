import os
from typing import Optional

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI


class AIClientError(Exception):
    pass


class AIClient:
    def __init__(self):
        self.api_base_url = os.getenv("AI_API_BASE_URL", "https://api.openai.com/v1").rstrip("/")
        self.api_key = os.getenv("AI_API_KEY", "").strip()
        self.model = os.getenv("AI_MODEL", "gpt-4o-mini").strip()
        self.timeout = float(os.getenv("AI_TIMEOUT_SECONDS", "30"))

    def is_enabled(self) -> bool:
        return os.getenv("AI_ENABLED", "false").lower() == "true"

    def _build_llm(self, temperature: float, timeout: float | None = None) -> ChatOpenAI:
        return ChatOpenAI(
            model=self.model,
            api_key=self.api_key,
            base_url=self.api_base_url,
            temperature=temperature,
            timeout=timeout if timeout is not None else self.timeout,
        )

    @staticmethod
    def _extract_content(content: object) -> str:
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, dict):
                    text = item.get("text")
                    if isinstance(text, str) and text.strip():
                        parts.append(text.strip())
                elif isinstance(item, str) and item.strip():
                    parts.append(item.strip())
            return "\n".join(parts).strip()
        return str(content).strip()

    async def chat_messages(
        self,
        messages: list[BaseMessage],
        temperature: float = 0.3,
        timeout_seconds: float | None = None,
    ) -> tuple[str, str]:
        if not self.is_enabled():
            raise AIClientError("AI 功能未启用，请设置 AI_ENABLED=true")
        if not self.api_key:
            raise AIClientError("AI_API_KEY 未配置")

        llm = self._build_llm(temperature=temperature, timeout=timeout_seconds)
        try:
            response = await llm.ainvoke(messages)
        except Exception as exc:
            raise AIClientError(f"AI 请求异常: {exc}") from exc

        content = self._extract_content(response.content)
        if not content:
            raise AIClientError("AI 返回内容为空")

        model = (
            response.response_metadata.get("model_name")
            if isinstance(response.response_metadata, dict)
            else None
        ) or self.model

        return content, model

    async def chat(
        self,
        user_message: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.3,
    ) -> tuple[str, str]:
        messages: list[BaseMessage] = []
        if system_prompt:
            messages.append(SystemMessage(content=system_prompt))
        messages.append(HumanMessage(content=user_message))
        return await self.chat_messages(messages=messages, temperature=temperature)