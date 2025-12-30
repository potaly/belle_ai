# syntax=docker/dockerfile:1.7

ARG BASE_IMAGE=python:3.10-slim-bullseye

FROM ${BASE_IMAGE} AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive

# 可选：pip 内网/镜像源
ARG PIP_INDEX_URL
ARG PIP_TRUSTED_HOST

# 可选：apt 镜像站点
# 推荐传站点根：  https://mirrors.tuna.tsinghua.edu.cn
# 也兼容传：      https://mirrors.tuna.tsinghua.edu.cn/debian
ARG APT_MIRROR

WORKDIR /app

RUN set -eux; \
    rm -f /etc/apt/sources.list.d/*.list || true; \
    \
    # APT 网络稳健化（企业内网常用）
    printf 'Acquire::ForceIPv4 "true";\nAcquire::Retries "5";\nAcquire::http::Timeout "20";\nAcquire::https::Timeout "20";\n' > /etc/apt/apt.conf.d/99network; \
    \
    codename="$(awk -F= '/^VERSION_CODENAME/{print $2}' /etc/os-release)"; \
    \
    # 计算镜像根：保证 APT_MIRROR 传 /debian 或不传都能用
    if [ -n "${APT_MIRROR:-}" ]; then \
      mirror="${APT_MIRROR%/}"; \
      mirror="${mirror%/debian}"; \
    else \
      mirror="https://mirrors.tuna.tsinghua.edu.cn"; \
    fi; \
    \
    # bullseye（Debian 11）正确源（不包含 non-free-firmware；security 走 debian-security 路径）
    printf "deb %s/debian %s main contrib non-free\n" "$mirror" "$codename" > /etc/apt/sources.list; \
    printf "deb %s/debian %s-updates main contrib non-free\n" "$mirror" "$codename" >> /etc/apt/sources.list; \
    printf "deb %s/debian-security %s-security main contrib non-free\n" "$mirror" "$codename" >> /etc/apt/sources.list; \
    \
    apt-get update; \
    apt-get install -y --no-install-recommends gcc g++ make ca-certificates; \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --upgrade pip --default-timeout=600 \
    && if [ -n "${PIP_INDEX_URL:-}" ]; then /opt/venv/bin/pip config set global.index-url "${PIP_INDEX_URL}"; fi \
    && if [ -n "${PIP_TRUSTED_HOST:-}" ]; then /opt/venv/bin/pip config set global.trusted-host "${PIP_TRUSTED_HOST}"; fi \
    && /opt/venv/bin/pip install -r requirements.txt --default-timeout=600


FROM ${BASE_IMAGE} AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:${PATH}" \
    LOG_DIR=/app/logs

RUN useradd --create-home --shell /bin/bash appuser

WORKDIR /app

COPY --from=builder /opt/venv /opt/venv
COPY app/ /app/app/
COPY requirements.txt /app/

RUN mkdir -p /app/logs && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health').read()" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
