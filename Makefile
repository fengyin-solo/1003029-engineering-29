.PHONY: install backend frontend ready

install:
	cd backend && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
	cd frontend && npm install

backend:
	cd backend && ./run.sh

frontend:
	cd frontend && npm run dev

# 就绪探测：与 /api/ready 同一套检查，没过哪项会在输出里点出来，退出码非 0
ready:
	cd backend && .venv/bin/python -m app.readiness
