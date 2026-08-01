# ============================================================
# المرحلة 1: بناء سيرفر telegram-bot-api المحلي من المصدر
# ============================================================
FROM debian:bookworm-slim AS botapi-build

RUN apt-get update && apt-get install -y --no-install-recommends \
        git make cmake g++ gperf libssl-dev zlib1g-dev ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /src
RUN git clone --recursive https://github.com/tdlib/telegram-bot-api.git .

RUN mkdir build && cd build \
    && cmake -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX:PATH=.. .. \
    && cmake --build . --target install -j"$(nproc)" \
    && strip ../bin/telegram-bot-api


# ============================================================
# المرحلة 2: صورة البوت النهائية (بايثون + ffmpeg + سيرفر تليكرام المحلي)
# ============================================================
FROM python:3.11-slim

# ffmpeg لمعالجة الفيديو، curl لفحص جاهزية السيرفر المحلي،
# libssl3/zlib1g مكتبات التشغيل اللي يحتاجها telegram-bot-api
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg curl libssl3 zlib1g \
    && rm -rf /var/lib/apt/lists/*

# الملف التنفيذي لسيرفر تليكرام المحلي من مرحلة البناء
COPY --from=botapi-build /src/bin/telegram-bot-api /usr/local/bin/telegram-bot-api

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN chmod +x docker-entrypoint-combined.sh

RUN mkdir -p /var/lib/telegram-bot-api

EXPOSE 8081

ENTRYPOINT ["./docker-entrypoint-combined.sh"]
