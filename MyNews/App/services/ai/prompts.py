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


QA_SYSTEM_PROMPT = (
    "你是新闻知识库问答助手。仅允许基于给定上下文回答，"
    "如果上下文不足，请明确回复“根据现有新闻资料无法确定”。"
)


NEWS_CHAT_SYSTEM_PROMPT = (
    "你是新闻总结助手。请严格基于给定新闻内容回答，不要虚构事实，不要引入外部资料。"
)


QA_CHAT_PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", QA_SYSTEM_PROMPT),
        (
            "human",
            "问题：{question}\n\n"
            "上下文：\n{context}\n\n"
            "请先给出简洁答案，再给出关键依据点。",
        ),
    ]
)


NEWS_CHAT_PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", NEWS_CHAT_SYSTEM_PROMPT),
        (
            "human",
            "新闻标题：{title}\n"
            "新闻摘要：{description}\n"
            "新闻正文：{content}\n\n"
            "用户问题：{question}\n\n"
            "请使用中文回答，先给出简短总结，再给出3-5条要点。",
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


def build_qa_messages(question: str, context_blocks: list[str]):
    context = "\n\n".join(context_blocks) if context_blocks else "无"
    return QA_CHAT_PROMPT.format_messages(question=question, context=context)


def build_news_chat_messages(title: str, description: str | None, content: str, question: str):
    return NEWS_CHAT_PROMPT.format_messages(
        title=title or "无",
        description=description or "无",
        content=content or "无",
        question=question,
    )
