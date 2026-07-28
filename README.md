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

- `vinyl.png` — قرص أسود بتدرّج + أخاديد + انعكاسات ضوئية (640×640).
- `pin.png` — الحديدة المعدنية الوسطى (بشفافية) مع ظلها، توضع فوق الصورة تلقائياً.
- `shadow.png` — طبقة ظل/إضاءة عامة فوق كل شيء (ثابتة، لا تدور).

**هذي مجرد نماذج بسيطة تولّدت آلياً للاختبار السريع.**
استبدلها بتصميمك الحقيقي (بنفس الاسم والمقاس 640×640، PNG بشفافية) للحصول على
الشكل النهائي المطلوب.

## إعدادات قابلة للتعديل (متغيرات بيئة)

| المتغير | الافتراضي | الوصف |
|---|---|---|
| `MAX_CONCURRENT_JOBS` | 3 | عدد المعالجات المتزامنة |
| `ROTATION_SECONDS` | 4 | مدة دورة كاملة للقرص (ثانية) |
| `OUTPUT_FPS` | 30 | إطارات الفيديو الناتج |
| `DISC_SIZE` | 640 | مقاس الفيديو (مربّع، فيديو نوت بتليكرام) |
| `HOLE_RATIO` | 0.42 | نسبة قطر الثقب لمقاس القرص |
| `MAX_DURATION_SECONDS` | 60 | الحد الأقصى (حد تليكرام لفيديو نوت) |

## هيكل المشروع

```
vinylbot/
├── main.py         # نقطة التشغيل + polling
├── handlers.py      # استقبال الصوت + التحقق + إدارة الطابور
├── compose.py       # لصق صورة الغلاف داخل ثقب القرص (Pillow)
├── processor.py     # تدوير القرص + دمج الصوت (ffmpeg)
├── config.py         # الإعدادات
├── assets/           # vinyl.png + shadow.png (القالب)
├── temp/             # ملفات مؤقتة (تُحذف تلقائياً بعد كل طلب)
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

- `vinyl.png` — Black disc with gradient + grooves + light reflections (640x640).

- `pin.png` — The central metal piece (transparent) with its shadow, automatically placed on top of the image.

- `shadow.png` — A general shadow/light layer over everything (static, does not rotate).

**These are just simple, automatically generated samples for quick testing.** Replace them with your actual design (same name and size 640x640, PNG with transparency) to get the desired final look.

## Adjustable Settings (Environment Variables)

| Variable | Default | Description |

|---|---|---|

| `MAX_CONCURRENT_JOBS` | 3 | Number of concurrent processors |

| `ROTATION_SECONDS` | 4 | Duration of a full disk rotation (seconds) |

| `OUTPUT_FPS` | 30 | Output video frames |

| `DISC_SIZE` | 640 | Video size (square, Telegram Video Note) |

| `HOLE_RATIO` | 0.42 | Hole diameter to disk size ratio |

| `MAX_DURATION_SECONDS` | 60 | Maximum (Telegram Video Note limit) |

## Project Structure

```
vinylbot/
├── main.py # Startup point + polling
├── handlers.py # Audio reception + verification + queue management
├── compose.py # Paste cover image into disk hole (Pillow)
├── processor.py # Disk rotation + audio merging (ffmpeg)
├── config.py # Settings
├── assets/ # vinyl.png + shadow.png (Template)
├── temp/ # Temporary files (automatically deleted after each request)
└── requirements.txt
```
