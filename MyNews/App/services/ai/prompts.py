from schemas.ai import AINewsDraftSuggestIn
from langchain_core.prompts import ChatPromptTemplate


SUMMARY_SYSTEM_PROMPT = (
    "你是新闻编辑助手。请严格基于给定新闻内容进行总结，不要虚构信息。"
)

DRAFT_SUGGEST_SYSTEM_PROMPT = (
    "你是新闻写作助手。请基于稿件信息，给出标题优化、摘要优化和内容改进建议。"
)


SUMMARY_CHAT_PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", SUMMARY_SYSTEM_PROMPT),
        (
            "human",
            "请总结以下新闻，输出：1) 一段简要摘要；2) 3条要点。\n"
            "标题：{title}\n"
            "摘要：{description}\n"
            "正文：{content}",
        ),
    ]
)


DRAFT_SUGGEST_CHAT_PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", DRAFT_SUGGEST_SYSTEM_PROMPT),
        (
            "human",
            "请输出 JSON，字段为 title_suggestions(长度3数组), description_suggestion(字符串), "
            "content_suggestions(长度3数组)。\n"
            "分类：{category_name}\n"
            "标题：{title}\n"
            "摘要：{description}\n"
            "正文：{content}\n"
            "输出要求：{format_instructions}",
        ),
    ]
)


def build_summary_messages(title: str, description: str | None, content: str):
    return SUMMARY_CHAT_PROMPT.format_messages(
        title=title,
        description=description or "无",
        content=content,
    )


def build_draft_suggest_messages(draft: AINewsDraftSuggestIn, format_instructions: str):
    return DRAFT_SUGGEST_CHAT_PROMPT.format_messages(
        category_name=draft.category_name,
        title=draft.title,
        description=draft.description or "无",
        content=draft.content,
        format_instructions=format_instructions,
    )
