// Core text equivalence from texts.py + locales/en.py.
import { db } from 'sdk';
import { eq } from 'sdk/db';
import { overrides } from '../schema.js';
export const STR = {
 ar: {
  start: '<b>I\'m making a vinyl Disc 💽🎶</b>\n\n💽 أرسل لي ملف صوتي (audio) يحتوي صورة مصغرة، وراح أرجع لك فيديو قرص دوّار (vinyl) بصورتك وصوتك 💽⚡️\n\n<b>🎶 اختر سرعة دوران القرص:</b>\n<i>هذا لا يغيّر سرعة الصوت أو الملف</i>',
  choose:'📀 وصلني الملف! اختار شلون نسويلك القرص:',
  quick:'⚡ إنشاء سريع', customize:'🎛 تخصيص', lang:'🇬🇧 English',
  color:'🎨 اختار لون القرص:', speed:'🎚 اختار سرعة الدوران:',
  photo:'🖼 أرسل صورة الغلاف الجديدة (تستبدل الحالية لو موجودة)،\nأو اضغط تخطي للاحتفاظ بالصورة الأصلية.',
  skip:'⏭ تخطي (استخدم الصورة الأصلية)', segment:'⏱ الملف مدته أطول من دقيقة، اختار الدقيقة المراد تسجيلها:',
  review:'✅ جاهزين! تقدر تطلب معاينة سريعة أولاً، أو تنشئ الفيديو الكامل مباشرة.',
  preview:'🔍 معاينة سريعة (٣ ثواني)', full:'🚀 إنشاء الفيديو الكامل',
  expired:'⌛ انتهت صلاحية الجلسة، أرسل الملف من جديد.',
  noThumb:'⚠️ الملف ما فيه صورة أصلية، لازم ترسل صورة.',
  quickPhoto:'⚡ إنشاء سريع: هذا الملف ما فيه صورة مصغرة، أرسل الصورة الآن وسأكمل تلقائيًا.',
  buy:'⭐ اشتراك {price} نجمة / 30 يوم', back:'🔙 رجوع', cancel:'❌ إلغاء',
  wrong:'📌 أرسل ملف صوتي (Audio) وليس فيديو أو مستند، حتى تكون صورته المصغرة موجودة.',
  premium:'💎 هذا اللون متاح فقط للمشتركين بالاشتراك المدفوع.',
  denied:'🚫 هذا التحكم متاح فقط لصاحب الطلب أو مشرفي المحادثة.',
  limited:'🚫 وصلت للحد اليومي ({limit} أقراص كل 24 ساعة).\n⏳ راح يتجدد الحد خلال {hours} ساعة تقريبًا.',
  renderer:'⚠️ تحويل الصوت إلى فيديو نوت والمعاينة غير متاحين على فرع السيرفليس حالياً. لن تُحتسب محاولة أو يُخصم من رصيدك.',
  receipt:'✅ تم تفعيل الاشتراك بنجاح! حدك اليومي الآن {limit} قرص لكل 24 ساعة.',
  invalid:'❌ تعذر التحقق من بيانات الدفعة. لم يتم تفعيل الاشتراك.',
  size:'❌ الملف أكبر من 20 ميگابايت. أرسل ملفاً أصغر.',
  speedLabels: ['دورة كاملة','8 دورة في الدقيقة','19 دورة في الدقيقة','33 دورة في الدقيقة','45 دورة في الدقيقة'],
 },
 en: {
  start:'<b>I\'m making a vinyl Disc 💽🎶</b>\n\n💽 Send me an audio file with a thumbnail and I will turn it into a spinning vinyl video note with your picture and sound.\n\n<b>🎶 Choose the disc rotation speed:</b>\n<i>This does not change audio speed</i>',
  choose:'📀 Got the file! Choose how to make your disc:',
  quick:'⚡ Quick create', customize:'🎛 Customize', lang:'🇮🇶 العربية',
  color:'🎨 Choose the disc color:', speed:'🎚 Choose the rotation speed:',
  photo:'🖼 Send a new cover image, or skip to keep the original.',
  skip:'⏭ Skip (use original image)', segment:'⏱ The file is longer than a minute. Choose which minute to use:',
  review:'✅ All set! Preview the video or create the full version.',
  preview:'🔍 Quick preview (3 seconds)', full:'🚀 Create the full video',
  expired:'⌛ Session expired. Send the audio file again.', noThumb:'⚠️ The audio has no cover. Send an image.',
  quickPhoto:'⚡ Quick create needs a cover image. Send one now.',
  buy:'⭐ Subscribe {price} stars / 30 days', back:'🔙 Back', cancel:'❌ Cancel',
  wrong:'📌 Send an audio file (Audio), not a video or document.',
  premium:'💎 This disc is available only to subscribers.',
  denied:'🚫 Only the request owner or a chat administrator can control this.',
  limited:'🚫 You reached the daily limit ({limit} discs per 24 hours).\n⏳ It resets in roughly {hours} hours.',
  renderer:'⚠️ Audio-to-video rendering and previews are not available on this Serverless branch yet. No usage will be charged.',
  receipt:'✅ Subscription activated! Your daily limit is now {limit} discs every 24 hours.',
  invalid:'❌ Payment validation failed. Subscription was not activated.',
  size:'❌ File exceeds the 20 MB limit. Send a smaller file.',
  speedLabels: ['Full turn','8 RPM','19 RPM','33 RPM','45 RPM'],
 }
};
export function fmt(s, params={}) { return s.replace(/\{(\w+)\}/g, (_, k) => String(params[k] ?? '')); }
export async function tr(key, lang='ar', params={}) {
  const full = lang === 'en' ? 'EN::'+key : key;
  const row = await db.select().from(overrides).where(eq(overrides.key, full)).get();
  return fmt(row?.value ?? STR[lang]?.[key] ?? STR.ar[key] ?? key, params);
}
