
"""
نظام الإيموجي البريميوم الذكي — استخراج وإدارة الأكواد تلقائياً

الفكرة:
- عند كتابة نص يحتوي على: <tg-emoji emoji-id='123'>🎶</tg-emoji>
- البوت يستخرج الكود (123) والإيموجي (🎶) تلقائياً
- ثم ينشئ entities صحيحة لـ Telegram
- بدون الحاجة لإدخال يدوي للأكواد
"""

import re
import logging
from typing import Dict, List, Tuple
from aiogram.types import MessageEntity

logger = logging.getLogger(name)

# regex لاستخراج أكواد الإيموجي البريميوم
PREMIUM_EMOJI_REGEX = r'<tg-emoji\s+emoji-id=["\'](\d+)["\']\s*>(.+?)</tg-emoji>'


def extract_premium_emojis(text: str) -> Dict[str, str]:
    """
    استخرج كل الإيموجي البريميوم من النص.
    
    المدخل:
        "مرحباً <tg-emoji emoji-id='123'>🎶</tg-emoji> وأهلاً"
    
    المخرج:
        {"🎶": "123"}
    """
    emojis = {}
    matches = re.finditer(PREMIUM_EMOJI_REGEX, text)
    for match in matches:
        emoji_id = match.group(1)
        emoji_char = match.group(2)
        emojis[emoji_char] = emoji_id
        logger.debug(f"✅ استخرج إيموجي بريميوم: {emoji_char} (ID: {emoji_id})")
    return emojis


def clean_premium_emoji_tags(text: str) -> str:
    """
    شيل tags الإيموجي البريميوم من النص (لكن احتفظ بالإيموجي نفسه).
    
    المدخل:
        "مرحباً <tg-emoji emoji-id='123'>🎶</tg-emoji>"
    
    المخرج:
        "مرحباً 🎶"
    """
    return re.sub(PREMIUM_EMOJI_REGEX, r'\2', text)


def _utf16_len(ch: str) -> int:
    """طول المحرف بوحدات UTF-16."""
    return len(ch.encode("utf-16-le")) // 2


def build_premium_entities(text: str) -> List[MessageEntity] | None:
    """
    ابني entities للإيموجي البريميوم من النص.
    
    الاستخدام:
        text = "مرحباً <tg-emoji emoji-id='123'>🎶</tg-emoji>"
        
        # 1. استخرج الأكواد
        emojis = extract_premium_emojis(text)
        
        # 2. نظّف النص (شيل tags)
        clean_text = clean_premium_emoji_tags(text)
        
        # 3. ابني entities
        entities = build_premium_entities(clean_text, emojis)
        
        # 4. أرسل الرسالة
        await message.reply(clean_text, entities=entities)
    """
    # استخرج الإيموجي والأكواد من النص الأصلي
    emojis_dict = extract_premium_emojis(text)
    
    if not emojis_dict:
        return None
    
    # نظّف النص أولاً
    clean_text = clean_premium_emoji_tags(text)
    
    # ابني entities
    entities: List[MessageEntity] = []
    offset = 0
    
    for ch in clean_text:
        length = _utf16_len(ch)
        
        if ch in emojis_dict:
            emoji_id = emojis_dict[ch]
            entities.append(MessageEntity(
                type="custom_emoji",
                offset=offset,
                length=length,
                custom_emoji_id=emoji_id,
            ))
            logger.debug(f"✅ أضفت entity: {ch} (offset={offset}, length={length}, id={emoji_id})")
        
        offset += length
    
    return entities if entities else None


async def send_with_premium_emojis(message_obj, text: str, **kwargs) -> any:
    """
    دالة helper — أرسل رسالة مع إيموجي بريميوم بشكل مباشر.
    
    الاستخدام:
        await send_with_premium_emojis(
            message,
            "مرحباً <tg-emoji emoji-id='123'>🎶</tg-emoji>"
        )
    """
    # استخرج الأكواد
    emojis_dict = extract_premium_emojis(text)
    
    if not emojis_dict:
        # لا توجد إيموجي بريميوم، أرسل عادي
        return await message_obj.reply(text, **kwargs)
    
    # نظّف النص
    clean_text = clean_premium_emoji_tags(text)
    
    # ابني entities
    entities = build_premium_entities(text)
    
    # أرسل مع entities
    try:
        return await message_obj.reply(clean_text, entities=entities, **kwargs)
    except Exception as e:
        logger.warning(f"فشل إرسال رسالة مع إيموجي بريميوم: {e}, سأحاول بدونها")
        return await message_obj.reply(clean_text, **kwargs)


def validate_premium_emoji_syntax(text: str) -> Tuple[bool, str]:
    """
    تحقق من صحة صيغة الإيموجي البريميوم.
    
    يرجع (True, "") إذا صحيحة
    يرجع (False, "رسالة الخطأ") إذا خاطئة
    """
    # ابحث عن tags مفتوحة بدون إغلاق
    open_tags = len(re.findall(r'<tg-emoji', text))
    close_tags = len(re.findall(r'</tg-emoji>', text))
    
    if open_tags != close_tags:
        return False, f"❌ عدد tags غير متطابق: {open_tags} فتح و {close_tags} إغلاق"
    
    # تحقق من صيغة emoji-id
    invalid_ids = re.findall(r'<tg-emoji\s+emoji-id=["\']([^"\']+)["\']', text)
    for emoji_id in invalid_ids:
        if not emoji_id.isdigit():
            return False, f"❌ emoji-id يجب أن يكون أرقام فقط: '{emoji_id}'"
    
    # تحقق من وجود محتوى fallback
    empty_tags = re.findall(r'<tg-emoji[^>]*>\s*</tg-emoji>', text)
    if empty_tags:
        return False, "❌ tag الإيموجي فارغ، ضع إيموجي أو نص بالداخل"
    
    return True, ""


def demo_premium_emoji():
    """مثال توضيحي."""
    example = (
        "مرحباً <tg-emoji emoji-id='5413457095766851738'>💽</tg-emoji> "
        "وأهلاً <tg-emoji emoji-id='5316520147752598207'>🎶</tg-emoji>"
    )
    
    print("=" * 60)
    print("📝 النص الأصلي:")
    print(example)
    print()
    
    # استخرج الأكواد
    emojis = extract_premium_emojis(example)
    print("✅ الإيموجي المستخرجة:")
    for emoji, emoji_id in emojis.items():
        print(f"  • {emoji} → {emoji_id}")
    print()
    
    # نظّف
    clean = clean_premium_emoji_tags(example)
    print("🧹 النص المنظّف:")
    print(clean)
    print()
    
    # تحقق من الصيغة
    is_valid, error = validate_premium_emoji_syntax(example)
    print(f"✔️ الصيغة صحيحة: {is_valid}")
    if error:
        print(f"   {error}")
    print("=" * 60)


if name == "main":
    demo_premium_emoji()
