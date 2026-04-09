import os
from typing import AsyncIterator, Optional

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from openai import AsyncOpenAI


class AIClientError(Exception):
    """AI 客户端统一异常类型。"""

    pass


class AIClient:
    def __init__(self):
        """初始化模型调用配置，包括普通请求与流式请求超时。"""
        self.api_base_url = os.getenv("AI_API_BASE_URL", "https://api.openai.com/v1").rstrip("/")
        self.api_key = os.getenv("AI_API_KEY", "").strip()
        self.model = os.getenv("AI_MODEL", "gpt-4o-mini").strip()
        self.timeout = float(os.getenv("AI_TIMEOUT_SECONDS", "30"))
        self.stream_timeout = float(os.getenv("AI_STREAM_TIMEOUT_SECONDS", "180"))
        self._raw_client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.api_base_url,
            timeout=self.stream_timeout,
        )

    def is_enabled(self) -> bool:
        """检查 AI 功能开关是否开启。"""
        return os.getenv("AI_ENABLED", "false").lower() == "true"

    def _build_llm(self, temperature: float, timeout: float | None = None) -> ChatOpenAI:
        """构建 LangChain ChatOpenAI 客户端（用于非流式调用）。"""
        return ChatOpenAI(
            model=self.model,
            api_key=self.api_key,
            base_url=self.api_base_url,
            temperature=temperature,
            timeout=timeout if timeout is not None else self.timeout,
        )

    @staticmethod
    def _extract_content(content: object) -> str:
        """从模型返回内容中提取可读文本，并做基础清洗。"""
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

    @staticmethod
    def _extract_chunk_text(content: object) -> str:
        """从流式 delta 中提取增量文本。"""
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, dict):
                    text = item.get("text")
                    if isinstance(text, str) and text:
                        parts.append(text)
                elif isinstance(item, str) and item:
                    parts.append(item)
            return "".join(parts)
        return str(content) if content is not None else ""

    @staticmethod
    def _to_openai_messages(messages: list[BaseMessage]) -> list[dict]:
        """将 LangChain 消息转换为 OpenAI 兼容消息格式。"""
        payload: list[dict] = []
        for msg in messages:
            role = "user"
            if isinstance(msg, SystemMessage):
                role = "system"
            elif msg.__class__.__name__.lower().startswith("ai"):
                role = "assistant"
            content = AIClient._extract_content(getattr(msg, "content", ""))
            if not content:
                continue
            payload.append({"role": role, "content": content})
        return payload

    async def chat_messages(
        self,
        messages: list[BaseMessage],
        temperature: float = 0.3,
        timeout_seconds: float | None = None,
    ) -> tuple[str, str]:
        """发送非流式消息并返回完整文本与模型名。"""
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
        """简化版单轮对话接口。"""
        messages: list[BaseMessage] = []
        if system_prompt:
            messages.append(SystemMessage(content=system_prompt))
        messages.append(HumanMessage(content=user_message))
        return await self.chat_messages(messages=messages, temperature=temperature)

    async def chat_messages_stream(
        self,
        messages: list[BaseMessage],
        temperature: float = 0.3,
        timeout_seconds: float | None = None,
    ) -> AsyncIterator[str]:
        """发送流式消息并逐段产出文本增量。"""
        if not self.is_enabled():
            raise AIClientError("AI 功能未启用，请设置 AI_ENABLED=true")
        if not self.api_key:
            raise AIClientError("AI_API_KEY 未配置")

        req_timeout = timeout_seconds if timeout_seconds is not None else self.stream_timeout
        openai_messages = self._to_openai_messages(messages)
        if not openai_messages:
            raise AIClientError("流式请求消息为空")
        try:
            stream = await self._raw_client.chat.completions.create(
                model=self.model,
                messages=openai_messages,
                temperature=temperature,
                stream=True,
                timeout=req_timeout,
            )
            async for chunk in stream:
                choice = chunk.choices[0] if chunk.choices else None
                if not choice:
                    continue
                delta = getattr(choice, "delta", None)
                if delta is None:
                    continue
                text = self._extract_chunk_text(getattr(delta, "content", ""))
                if text:
                    yield text
        except Exception as exc:
            text = str(exc)
            if "timed out" in text.lower() or "timeout" in text.lower():
                raise AIClientError(
                    "AI 流式请求超时。请提高 AI_STREAM_TIMEOUT_SECONDS，或缩短问题与检索上下文。"
                ) from exc
            raise AIClientError(f"AI 流式请求异常: {exc}") from exc