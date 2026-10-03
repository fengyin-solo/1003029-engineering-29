.PHONY: install backend frontend ready test

install:
	cd backend && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
	cd frontend && npm install

backend:
	cd backend && ./run.sh

frontend:
	cd frontend && npm run dev

# 就绪探测：和浏览器、curl 直接访问 /api/ready 看到的是同一份结论；
# 未就绪时退出码非 0，可直接接在脚本里做等待/断言。
ready:
	@curl -s --max-time 3 http://127.0.0.1:8000/api/ready | python3 -c "import sys, json; raw = sys.stdin.read().strip(); d = json.loads(raw) if raw else {'ready': False, 'detail': '后端不可达，先 make backend'}; print(json.dumps(d, ensure_ascii=False, indent=2)); sys.exit(0 if d.get('ready') else 1)"

test:
	cd backend && .venv/bin/python -m unittest discover -s tests -v
