"""测试 GET /health。需先启动服务: uvicorn app:app --host 0.0.0.0 --port 8002
在项目根目录运行: python scripts/test/api/test_health.py
"""
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(BASE))

import requests

URL = "http://127.0.0.1:8002/health"


def main():
    print("请求 GET /health ...")
    try:
        r = requests.get(URL, timeout=5)
    except requests.exceptions.ConnectionError as e:
        print(f"连接失败，请先启动服务: uvicorn app:app --host 0.0.0.0 --port 8002\n{e}")
        sys.exit(1)

    print(f"状态码: {r.status_code}")
    if r.status_code != 200:
        print(r.text)
        sys.exit(1)

    data = r.json()
    print(f"响应: {data}")
    assert data.get("status") == "ok", "期望 status == ok"
    print("通过")


if __name__ == "__main__":
    main()
