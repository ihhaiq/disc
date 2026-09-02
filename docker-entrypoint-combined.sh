#!/bin/sh
set -e

if [ -z "${TELEGRAM_API_ID}" ] || [ -z "${TELEGRAM_API_HASH}" ]; then
    echo "❌ خطأ: لازم تحدد TELEGRAM_API_ID و TELEGRAM_API_HASH بمتغيرات البيئة."
    echo "    احصل عليهم من https://my.telegram.org"
    exit 1
fi

WORK_DIR="/var/lib/telegram-bot-api"
mkdir -p "${WORK_DIR}"

echo "🚀 تشغيل سيرفر تليكرام المحلي (وضع --local)..."
telegram-bot-api \
    --api-id="${TELEGRAM_API_ID}" \
    --api-hash="${TELEGRAM_API_HASH}" \
    --local \
    --http-port=8081 \
    --dir="${WORK_DIR}" &

BOT_API_PID=$!

echo "⏳ بانتظار جاهزية سيرفر تليكرام المحلي..."
i=0
until curl -s -o /dev/null "http://127.0.0.1:8081"; do
    i=$((i + 1))
    if [ "$i" -ge 30 ]; then
        echo "❌ السيرفر المحلي ما صار جاهز بعد 30 ثانية، إيقاف."
        kill "${BOT_API_PID}" 2>/dev/null
        exit 1
    fi
    sleep 1
done
echo "✅ سيرفر تليكرام المحلي جاهز."

cleanup() {
    echo "🛑 إيقاف سيرفر تليكرام المحلي..."
    kill "${BOT_API_PID}" 2>/dev/null
}
trap cleanup EXIT INT TERM

export LOCAL_BOT_API_URL="${LOCAL_BOT_API_URL:-http://127.0.0.1:8081}"
echo "🤖 تشغيل البوت..."
python main.py
