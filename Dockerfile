# syntax=docker/dockerfile:1
# 단일 서버 배포: 빌드된 화면 + FastAPI API를 같은 출처(포트 8000)로 제공한다.
# 데이터(DB·업로드·사용자 정의 기준)는 /data 볼륨에 영속 저장한다.
# SSL 검사 프록시 환경에서는 사내 루트 인증서를 빌드 비밀로 넘긴다(선택):
#   docker build --secret id=extra_ca,src=/path/ca.pem -t sw-design-helper .

FROM node:22-slim AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN --mount=type=secret,id=extra_ca,required=false \
    if [ -f /run/secrets/extra_ca ]; then export NODE_EXTRA_CA_CERTS=/run/secrets/extra_ca; fi; \
    npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
WORKDIR /app/backend
COPY backend/pyproject.toml backend/uv.lock ./
RUN --mount=type=secret,id=extra_ca,required=false \
    if [ -f /run/secrets/extra_ca ]; then cat /etc/ssl/certs/ca-certificates.crt /run/secrets/extra_ca > /tmp/ca.pem; export PIP_CERT=/tmp/ca.pem SSL_CERT_FILE=/tmp/ca.pem; fi; \
    pip install --no-cache-dir uv==0.11.32 && uv sync --frozen --no-dev --no-install-project && rm -f /tmp/ca.pem
COPY backend/app ./app
COPY examples /app/examples
COPY --from=web /web/dist /app/frontend/dist
ENV FRONTEND_DIST=/app/frontend/dist DATA_DIR=/data APP_ENV=production PATH="/app/backend/.venv/bin:$PATH"
RUN useradd --system --uid 10001 --user-group app && mkdir -p /data && chown app:app /data
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod 755 /usr/local/bin/docker-entrypoint.sh
# root로 시작해 /data 소유자만 맞추고 서버는 app(비루트)으로 실행한다(docker-entrypoint.sh).
VOLUME ["/data"]
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/api/health' % os.environ.get('PORT', '8000'), timeout=3)"
ENTRYPOINT ["docker-entrypoint.sh"]
# PORT: 배포 서비스가 지정하면 그 포트, 없으면 8000
CMD ["sh", "-c", "exec uvicorn app.main:create_app --factory --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers"]
