FROM python:3.12-slim-bookworm

ARG OBSCURA_VERSION=v0.2.0
ARG TARGETARCH
ENV DEBIAN_FRONTEND=noninteractive \
    OBSCURA_VERSION=${OBSCURA_VERSION}

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl fonts-liberation fonts-noto-color-emoji \
    && rm -rf /var/lib/apt/lists/*

RUN set -eux; \
    case "${TARGETARCH:-amd64}" in \
      amd64) obscura_arch="x86_64" ;; \
      arm64) obscura_arch="aarch64" ;; \
      *) echo "Unsupported architecture: ${TARGETARCH}" >&2; exit 1 ;; \
    esac; \
    curl -fL "https://github.com/h4ckf0r0day/obscura/releases/download/${OBSCURA_VERSION}/obscura-${obscura_arch}-linux-stealth.tar.gz" -o /tmp/obscura.tar.gz; \
    tar -xzf /tmp/obscura.tar.gz -C /usr/local/bin; \
    chmod +x /usr/local/bin/obscura /usr/local/bin/obscura-worker; \
    rm /tmp/obscura.tar.gz; \
    obscura --version

RUN pip install --no-cache-dir "playwright==1.62.0"

WORKDIR /app
COPY runner.py /app/runner.py
ENTRYPOINT ["python", "/app/runner.py"]