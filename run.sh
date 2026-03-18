# 须在项目根目录启动（app.py 在根目录）；可直接执行本脚本: ./run.sh
cd "$(dirname "$0")"
source venv/bin/activate
uvicorn app:app --host 0.0.0.0 --port 8002 --reload
