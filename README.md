# Vinyl Bot

بوت تليكرام يستلم ملف صوتي (audio) ويحوّله إلى **فيديو نوت دائري** (Video Note،
نفس شكل الرسائل الصوتية الدائرية بتليكرام) — يضع صورة الغلاف داخل ثقب القرص،
يضيف الحديدة المعدنية بالمنتصف مع ظلها، يدوّر القرص، ويضع صوت الملف كصوت الفيديو.

⏱️ **الحد الأقصى 60 ثانية** (حد تليكرام الرسمي لفيديو نوت) — أي صوت أطول
يُقطع تلقائياً لأول 60 ثانية.

## التشغيل

```bash
pip install -r requirements.txt
# تأكد ffmpeg و ffprobe مثبتين على السيرفر (apt install ffmpeg)

export BOT_TOKEN="ضع_التوكن_هنا"
python main.py
```

## ملفات القالب (assets/)

- `vinyl*.png` — قوالب الأقراص المتاحة بألوانها وتصاميمها المختلفة.
- `shadow*.png` — طبقات الظل والإضاءة الثابتة التي توضع فوق القرص.

القوالب صور PNG مربعة، ويُفضّل إبقاؤها بالمقاس نفسه مع شفافية صحيحة حول القرص.

## إعدادات قابلة للتعديل (متغيرات بيئة)

| المتغير | الافتراضي | الوصف |
|---|---|---|
| `MAX_CONCURRENT_JOBS` | 2 | عدد المعالجات المتزامنة |
| `ROTATION_SECONDS` | 4 | مدة دورة كاملة للقرص (ثانية) |
| `OUTPUT_FPS` | 30 | إطارات الفيديو الناتج |
| `DISC_SIZE` | 640 | مقاس الفيديو (مربّع، فيديو نوت بتليكرام) |
| `HOLE_RATIO` | 0.42 | نسبة قطر الثقب لمقاس القرص |
| `MAX_DURATION_SECONDS` | 60 | الحد الأقصى (حد تليكرام لفيديو نوت) |

## تحديثات الأزرار (Button Styles)

- 🎨 **قائمة لون القرص** (من رسالة الترحيب وأيضاً من خطوة "🎛 تخصيص"): كل الأزرار تظهر بنمط `primary`، وعند اختيار لون معيّن يتحول زره إلى نمط `success` (فقط بقائمة الترحيب لأنها تُحدَّث بمكانها؛ خطوة التخصيص تنتقل مباشرة للخطوة التالية).
- ⏱ **اختيار الدقيقة** (بالضبط المخصص لملف أطول من دقيقة): كل الأزرار بنمط `success`.
- 🔙 زر الرجوع يبقى بالنمط الافتراضي بدون تغيير.

## هيكل المشروع

```
vinylbot/
├── main.py         # نقطة التشغيل + polling
├── handlers.py      # مسارات البوت وإدارة الطلبات والطابور
├── compose.py       # لصق صورة الغلاف داخل ثقب القرص (Pillow)
├── processor.py     # تدوير القرص + دمج الصوت (ffmpeg)
├── limits.py        # حدود الاستخدام والاشتراكات
├── texts.py         # النصوص العربية وتنظيف HTML
├── locales/         # الترجمات المنفصلة
├── services/        # سياسات السياق واللغة والتحقق من الدفع
├── routers/         # معالجات تليكرام مفصولة حسب الميزة
├── storage/         # تخزين JSON ذري ومشترك
├── rich_content.py  # استخراج وتطبيع الرسائل الغنية
├── vinyl_catalog.py # كتالوج القوالب ومساراتها
├── config.py        # الإعدادات
├── assets/          # قوالب الأقراص والظلال
├── temp/            # ملفات مؤقتة (تُحذف تلقائياً بعد كل طلب)
└── requirements.txt
```
# en
# Vinyl Bot

A Telegram bot that receives an audio file and converts it into a **circular video note** (similar to Telegram's circular voice messages). It places the cover image inside the disc hole, adds the metal object in the center with its shadow, rotates the disc, and plays the audio from the file as the video sound.

⏱️ **Maximum 60 seconds** (Telegram's official video note limit) — Any audio longer will be automatically cut to the first 60 seconds.

## Operation

```bash
pip install -r requirements.txt
# Ensure ffmpeg and ffprobe are installed on the server (apt install ffmpeg)

export BOT_TOKEN="Place the token here"
python main.py

```

## Template Files (assets/)

- `vinyl*.png` — Available vinyl templates in their different colors and designs.

- `shadow*.png` — Static shadow and lighting layers placed over the disc.

Templates should remain square PNG images with correct transparency around the disc.

## Adjustable Settings (Environment Variables)

| Variable | Default | Description |

|---|---|---|

| `MAX_CONCURRENT_JOBS` | 2 | Number of concurrent processors |

| `ROTATION_SECONDS` | 4 | Duration of a full disk rotation (seconds) |

| `OUTPUT_FPS` | 30 | Output video frames |

| `DISC_SIZE` | 640 | Video size (square, Telegram Video Note) |

| `HOLE_RATIO` | 0.42 | Hole diameter to disk size ratio |

| `MAX_DURATION_SECONDS` | 60 | Maximum (Telegram Video Note limit) |

## Project Structure

```
vinylbot/
├── main.py # Startup point + polling
├── handlers.py # Bot routes, requests, and queue management
├── compose.py # Paste cover image into disk hole (Pillow)
├── processor.py # Disk rotation + audio merging (ffmpeg)
├── limits.py # Usage limits and subscriptions
├── texts.py # Arabic source strings and HTML cleanup
├── locales/ # Separate translations
├── services/ # Context, localization, and payment policies
├── routers/ # Telegram handlers split by feature
├── storage/ # Shared atomic JSON persistence
├── rich_content.py # Rich-message normalization
├── vinyl_catalog.py # Vinyl template catalog
├── config.py # Settings
├── assets/ # Vinyl and shadow templates
├── temp/ # Temporary files (automatically deleted after each request)
└── requirements.txt
```


## فحوصات التطوير / Development checks

```bash
pip install -r requirements-dev.txt
ruff check .
pytest
```

`handlers.py` مستثنى مؤقتاً من Ruff إلى أن تكتمل مرحلة تفكيكه إلى routers.
