FROM python:3.12-slim
WORKDIR /srv/app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
# 容器健康状态直接复用就绪地址：端口、依赖、代理全通才算 healthy。
# 部署时若前端不在本机，用 PROXY_HEALTH_URL 指向前端服务的 /api/health。
HEALTHCHECK --interval=10s --timeout=3s --start-period=20s --retries=6 \
  CMD ["python", "-c", "import json, urllib.request; raise SystemExit(0 if json.load(urllib.request.urlopen('http://127.0.0.1:8000/api/ready', timeout=2)).get('ready') else 1)"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
