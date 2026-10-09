// Core text equivalence from texts.py + locales/en.py.
import { db } from 'sdk';
import { eq } from 'sdk/db';
import { overrides } from '../schema.js';
import { ORIGINAL_AR, ORIGINAL_EN } from './original-texts.js';
import { escapeHtml } from './dev-text-utils.js';
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
  renderer:'⚠️ إنشاء الفيديو والمعاينة غير متاحين حالياً. لن تُحتسب محاولة أو يُخصم من رصيدك.',
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
  renderer:'⚠️ Video creation and previews are currently unavailable. No usage will be charged.',
  receipt:'✅ Subscription activated! Your daily limit is now {limit} discs every 24 hours.',
  invalid:'❌ Payment validation failed. Subscription was not activated.',
  size:'❌ File exceeds the 20 MB limit. Send a smaller file.',
  speedLabels: ['Full turn','8 RPM','19 RPM','33 RPM','45 RPM'],
 }
};
export const LEGACY_KEYS=Object.freeze({
  start:'MSG_START_HELP',choose:'MSG_CHOOSE_MODE',
  quick:'BTN_QUICK_CREATE',customize:'BTN_CUSTOMIZE',lang:'BTN_LANG',
  color:'MSG_WIZ_CHOOSE_COLOR',speed:'MSG_WIZ_CHOOSE_SPEED',
  photo:'MSG_WIZ_CHOOSE_IMAGE',skip:'BTN_WIZ_SKIP_IMAGE',
  segment:'MSG_WIZ_CHOOSE_SEGMENT',review:'MSG_WIZ_REVIEW',
  preview:'BTN_WIZ_PREVIEW',full:'BTN_WIZ_CONFIRM_FULL',
  expired:'MSG_WIZ_EXPIRED',noThumb:'MSG_WIZ_NO_IMAGE_TO_SKIP',
  quickPhoto:'MSG_QUICK_NEED_IMAGE',buy:'BTN_BUY_STARS',
  back:'BTN_BACK',cancel:'BTN_CANCEL',wrong:'MSG_WRONG_TYPE',
  premium:'MSG_COLOR_PREMIUM_ONLY',receipt:'MSG_PAYMENT_SUCCESS_FMT',
  invalid:'MSG_PAYMENT_INVALID',
  size:'MSG_AUDIO_TOO_LARGE_FMT',limited:'MSG_LIMIT_REACHED_FMT',
});
export function fmt(s, params={}) {
  if (typeof s !== 'string') return s;
  return s.replace(/\{([a-zA-Z_][a-zA-Z0-9_]*)(?::([^}]+))?\}/g,
    (match,k,spec) => {
      if(params[k]==null)return match;
      if(/^\.\d{1,2}f$/.test(spec||'')&&Number.isFinite(Number(params[k])))
        return Number(params[k]).toFixed(Number(spec.slice(1,-1)));
      return String(params[k]);
    });
}
export async function textValue(key, lang='ar', params={}) {
  const full=LEGACY_KEYS[key]||key, en=lang==='en';
  let row=null;
  for(const target of new Set([en?'EN::'+key:key,en?'EN::'+full:full])){
    row=await db.select().from(overrides).where(eq(overrides.key,target)).get();
    if(row)break;
  }
  const source=en?ORIGINAL_EN:ORIGINAL_AR;
  const htmlParams=Object.fromEntries(Object.entries(params).map(([k,v])=>[k,typeof v==='string'?escapeHtml(v):v]));
  const text=fmt(row?.value ?? source[full] ?? STR[lang]?.[key] ?? ORIGINAL_AR[full] ?? STR.ar[key] ?? key,htmlParams);
  let rich=null;
  try {rich=row?.richJson?JSON.parse(row.richJson):null;}catch{}
  function format(value) {
    if(typeof value==='string')return fmt(value,params);
    if(Array.isArray(value))return value.map(format);
    if(value&&typeof value==='object')return Object.fromEntries(Object.entries(value).map(([k,v])=>[k,format(v)]));
    return value;
  }
  const formatted=rich&&typeof rich==='object'?format(rich):null;
  if(formatted&&typeof rich.html==='string')formatted.html=fmt(rich.html,htmlParams);
  return {text,rich:formatted};
}
export async function tr(key, lang='ar', params={}) {return (await textValue(key,lang,params)).text;}
