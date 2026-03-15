cd "$(dirname "$0")"
source venv/bin/activate
uvicorn app:app --host 0.0.0.0 --port 8002 --reload
