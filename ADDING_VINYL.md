# إضافة قرص جديد

هذا الملف يشرح الطريقة الحالية لإضافة Vinyl جديد للبوت بعد توحيد القوالب والأزرار داخل `vinyl_catalog.py`.

## الفكرة

`vinyl_catalog.py` هو المصدر الرئيسي للأقراص. عند تسجيل قرص جديد هناك، البوت يتعرّف عليه تلقائيًا في:

- قائمة اختيار القرص العادية.
- خطوات الـWizard.
- لوحة المطور `/dev`.
- لوحة تحديد الأقراص المجانية والمدفوعة.
- المعالجة والرندر.

ما تحتاج تعدل `handlers.py` أو `routers/wizard.py` أو `keyboard.py` عند إضافة قرص جديد.

## 1. إضافة ملفات القالب

ضع صورة القرص داخل `assets/`، مثل:

```text
assets/vinyl_ocean.png
```

إذا عندك Shadow خاص:

```text
assets/shadow_ocean.png
```

وتكدر تستخدم Shadow موجود أصلًا بدل إضافة ملف جديد.

يفضل أن تكون ملفات القالب PNG مربعة وبنفس مقاسات القوالب الحالية، مع شفافية صحيحة حول القرص.

## 2. إضافة نص الزر

في `texts.py` أضف مفتاح عربي:

```python
BTN_VINYL_OCEAN = "OCEAN"
```

وفي `locales/en.py` أضف النسخة الإنكليزية:

```python
"BTN_VINYL_OCEAN": "OCEAN",
```

إذا أضيفت لغات أخرى لاحقًا، أضف نفس المفتاح إلى ملفاتها أيضًا.

## 3. تسجيل القرص في vinyl_catalog.py

أضف `VinylStyle` جديد داخل `VINYL_STYLES`:

```python
VinylStyle(
    "ocean",
    "BTN_VINYL_OCEAN",
    "vinyl_ocean.png",
    "shadow_ocean.png",
    button_row=7,
),
```

المعاني:

- `ocean`: المفتاح الداخلي للقرص. لازم يكون فريدًا ويفضل lowercase بدون مسافات.
- `BTN_VINYL_OCEAN`: مفتاح اسم الزر في ملفات النصوص.
- `vinyl_ocean.png`: ملف القالب داخل `assets/`.
- `shadow_ocean.png`: ملف الظل داخل `assets/`.
- `button_row=7`: رقم الصف الذي يظهر به الزر. الأقراص التي تحمل نفس الرقم تظهر بجانب بعضها بنفس الصف.

## 4. إذا كانت فتحة القرص تحتاج قياسًا خاصًا

القيمة الافتراضية تأتي من `HOLE_RATIO` في الإعدادات. إذا التصميم يحتاج نسبة مختلفة، مررها كالقيمة الخامسة:

```python
VinylStyle(
    "ocean",
    "BTN_VINYL_OCEAN",
    "vinyl_ocean.png",
    "shadow_ocean.png",
    0.39,
    button_row=7,
),
```

استعمل override فقط إذا القالب فعلًا يحتاجه.

## 5. إضافة Custom Emoji للزر - اختياري

إذا تريد زر القرص يحمل Premium/Custom Emoji، خزّن الـID داخل نفس تعريف القرص:

```python
VinylStyle(
    "ocean",
    "BTN_VINYL_OCEAN",
    "vinyl_ocean.png",
    "shadow_ocean.png",
    button_row=7,
    icon_custom_emoji_id="1234567890123456789",
),
```

ما تحتاج تضيف الـID إلى `keyboard.py`.

## 6. مجاني أو مدفوع

ما تحتاج تعدل `limits.py`.

بعد تشغيل البوت:

```text
/dev → الحدود
```

راح يظهر القرص الجديد تلقائيًا. من هناك تكدر تبدله بين:

- 🆓 مجاني
- 💎 مدفوع للمشتركين

## 7. فحص الملفات

الاختبار الموجود في `tests/test_vinyl_catalog.py` يتحقق من أن ملفات القرص والـShadow المسجلة موجودة فعلًا داخل `assets/`.

شغل:

```bash
python -m compileall .
ruff check .
pytest
```

إذا نسيت ملف asset أو كتبت اسمه بشكل غلط، اختبار الـcatalog المفروض يكشفه.

## مثال كامل

```python
VinylStyle(
    "ocean",
    "BTN_VINYL_OCEAN",
    "vinyl_ocean.png",
    "shadow_rose.png",
    button_row=7,
    icon_custom_emoji_id="1234567890123456789",
),
```

بهذا المثال يستخدم القرص `shadow_rose.png` الموجود أصلًا، ويظهر تلقائيًا بكل قوائم اختيار الأقراص بدون أي تعديل إضافي على الـhandlers أو الـkeyboard.

## الملفات التي تعدلها عادةً عند إضافة قرص

```text
assets/
vinyl_catalog.py
texts.py
locales/en.py
```

ولا تحتاج تعدل عادةً:

```text
keyboard.py
handlers.py
routers/wizard.py
services/job_processor.py
services/vinyl_settings.py
limits.py
```
