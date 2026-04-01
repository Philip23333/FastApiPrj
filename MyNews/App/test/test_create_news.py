import os
from datetime import datetime

import requests


BASE_URL = os.getenv("NEWS_API_BASE", "http://127.0.0.1:8080")
TOKEN = os.getenv("NEWS_BEARER_TOKEN")


def test_create_news_simple():
    if not TOKEN:
        print("请先设置环境变量 NEWS_BEARER_TOKEN，再运行测试。")
        print("PowerShell 示例: $env:NEWS_BEARER_TOKEN='你的token'")
        return

    headers = {
        "Authorization": f"Bearer {TOKEN}",
    }

    # 1) 先拿分类列表，获取 category_id + category_name
    resp = requests.get(f"{BASE_URL}/news/categories", headers=headers, timeout=10)
    print("[categories] status:", resp.status_code)
    data = resp.json()

    categories = data.get("data", [])
    if not categories:
        print("分类列表为空，无法继续发布测试。")
        return

    selected = categories[0]
    category_id = selected["id"]
    category_name = selected["name"]

    # 2) 构造发布新闻请求体（同时传 category_id 和 category_name）
    payload = {
        "title": f"测试发布新闻 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "description": "这是自动化测试发布的一条新闻",
        "content": "<p>这是一段测试内容，包含<b>富文本</b>结构。</p>",
        "image": "/static/uploads/demo.jpg",
        "category_id": category_id,
        "category_name": category_name,
    }

    create_resp = requests.post(
        f"{BASE_URL}/news/",
        json=payload,
        headers=headers,
        timeout=10,
    )

    print("[create] status:", create_resp.status_code)
    print("[create] body:", create_resp.json())


if __name__ == "__main__":
    test_create_news_simple()
