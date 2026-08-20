FROM python:3.12-slim
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl gnupg unzip xvfb xauth \
    chromium chromium-driver \
    fonts-liberation fonts-noto-color-emoji \
    libnss3 libxss1 libasound2 libatk-bridge2.0-0 libgtk-3-0 \
    && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir "setuptools<81" selenium selenium-wire blinker==1.7.0 pyOpenSSL==23.3.0 cryptography==41.0.7
RUN python -c "import pkg_resources, seleniumwire, selenium, OpenSSL; print('selenium deps ok')"
WORKDIR /app
COPY runner.py /app/runner.py
ENTRYPOINT ["python", "/app/runner.py"]