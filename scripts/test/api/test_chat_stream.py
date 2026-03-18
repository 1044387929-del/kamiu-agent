"""测试 POST /api/chat/stream 流式对话（SSE）。
需先启动服务: uvicorn app:app --host 0.0.0.0 --port 8002
在项目根目录运行: python scripts/test/api/test_chat_stream.py
"""
import json
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(BASE))

import requests

BASE_URL = "http://127.0.0.1:8002"


def main():
    body = {
        "message": "现在的美国总统是谁？",
        "history": [],
        "enable_thinking": True,
    }
    print("请求 POST /api/chat/stream (SSE) ...")
    try:
        r = requests.post(
            f"{BASE_URL}/api/chat/stream",
            json=body,
            stream=True,
            timeout=60,
        )
    except requests.exceptions.ConnectionError as e:
        print(f"连接失败，请先启动服务: uvicorn app:app --host 0.0.0.0 --port 8002\n{e}")
        sys.exit(1)

    print(f"状态码: {r.status_code}")
    if r.status_code != 200:
        print(r.text)
        sys.exit(1)

    full_content = []
    for line in r.iter_lines(decode_unicode=True):
        if not line or not line.startswith("data:"):
            continue
        data = line[5:].strip()
        if data == "[DONE]" or not data:
            continue
        try:
            obj = json.loads(data)
        except json.JSONDecodeError:
            continue
        t = obj.get("type")
        if t == "content":
            full_content.append(obj.get("content", ""))
        elif t == "reasoning":
            print(f"[reasoning] {obj.get('content', '')[:50]}...")
        elif t == "usage":
            print(f"[usage] {obj.get('usage', {})}")
        elif t == "done":
            print("[done]")
    reply = "".join(full_content)
    print(f"回复长度: {len(reply)} 字符")
    print(f"回复: {reply}")
    print("POST /api/chat/stream 通过")


if __name__ == "__main__":
    main()
