"""测试 GET /api/chat（说明）与 POST /api/chat（非流式对话）。
需先启动服务: uvicorn app:app --host 0.0.0.0 --port 8002
在项目根目录运行: python scripts/test/api/test_chat_api.py
"""
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(BASE))

import requests

BASE_URL = "http://127.0.0.1:8002"


def test_get_chat():
    """GET /api/chat 返回使用说明。"""
    print("请求 GET /api/chat ...")
    r = requests.get(f"{BASE_URL}/api/chat", timeout=5)
    print(f"状态码: {r.status_code}")
    if r.status_code != 200:
        print(r.text)
        sys.exit(1)
    data = r.json()
    assert "usage" in data and "body" in data
    print(f"响应: {data}")
    print("GET /api/chat 通过")


def test_post_chat():
    """POST /api/chat 单轮非流式对话。"""
    body = {
        "message": "你好，请用一句话介绍你自己。",
        "history": [],
        "enable_thinking": False,
    }
    print("请求 POST /api/chat ...")
    r = requests.post(f"{BASE_URL}/api/chat", json=body, timeout=60)
    print(f"状态码: {r.status_code}")
    if r.status_code != 200:
        print(r.text)
        sys.exit(1)
    data = r.json()
    assert "reply" in data
    print(f"reply 长度: {len(data['reply'])} 字符")
    print(f"reply 预览: {data['reply'][:80]}...")
    print("POST /api/chat 通过")


def main():
    try:
        test_get_chat()
        test_post_chat()
    except requests.exceptions.ConnectionError as e:
        print(f"连接失败，请先启动服务: uvicorn app:app --host 0.0.0.0 --port 8002\n{e}")
        sys.exit(1)
    print("全部通过")


if __name__ == "__main__":
    main()
