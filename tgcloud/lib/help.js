import { db } from 'sdk';
import { eq } from 'sdk/db';
import { helpDocs } from '../schema.js';
import { developer } from './config.js';
import { updateUser, getUser } from './state.js';
import { kb } from './keyboard.js';
import { reply, answer, deliverRich, replyText } from './io.js';
import { tr } from './i18n.js';
import { extractMessageContent, safeHttpUrl } from './dev-text-utils.js';
const button=(text,callback_data)=>({text,callback_data});
const editorMenu=kb([[button('📝 نص الرسالة (Rich Msg)','help_builder:settext')],[button('➕ أضف زر','help_builder:addbtn'),button('🗑 حذف زر','help_builder:buttons')],[button('👁 معاينة','help_builder:preview')],[button('💾 حفظ ونشر','help_builder:save'),button('🔙 رجوع','help_builder:back')]]);
const editorRoot=kb([[button('🎛 تخصيص','help_builder:menu')]]);
function buttons(row){
  let b=[];
  try {b=JSON.parse(row?.buttonsJson || '[]');}catch{}
  return Array.isArray(b)?b.filter(x=>x&&x.text&&safeHttpUrl(x.url)).slice(0,40):[];
}
function markup(row,extra=null){
  const b=buttons(row).map(x=>[{text:String(x.text).slice(0,64),url:x.url}]);
  return b.length?kb(extra?[...b,...extra.inline_keyboard]:b):extra;
}
async function read(key) {return db.select().from(helpDocs).where(eq(helpDocs.key,key)).get();}
async function put(key,html,buttonsJson='[]',blocksJson=null,isRtl=null){
  const val={key,html,buttonsJson,blocksJson,isRtl,updatedAt:Math.floor(Date.now()/1000)};
  await db.insert(helpDocs).values(val).onConflictDoUpdate({target:helpDocs.key,set:val}).run();
}
export async function sendHelpDoc(message,row,extra=null) {
  const replyMarkup=markup(row,extra);
  // Telegram Bot API 10.1+ sendRichMessage preserves structured blocks/HTML.
  // Keep a compatibility fallback for API errors while the SDK is not live-tested.
  const blocks=(()=>{try {const parsed=JSON.parse(row?.blocksJson||'null');return Array.isArray(parsed)&&parsed.length?parsed:null;}catch{return null;}})();
  return deliverRich(message,{...(blocks?{blocks}:{html:row?.html||'النص'}),
    ...(row?.isRtl==null?{}:{is_rtl:!!row.isRtl})},row?.html||'',replyMarkup);
}
async function draft(uid){
  const key='draft:'+uid,r=await read(key);
  if(r)return r;
  await put(key,'النص');
  return read(key);
}
export async function sendHelp(message) {
  const uid=message.from?.id||0;
  const editing=developer(uid)&&message.chat.type==='private';
  if(editing)await updateUser(uid,{pendingAction:''});
  const r=editing?await draft(uid):await read('published');
  if(!r) {
    const lang=(await getUser(uid))?.lang||'ar';
    await replyText(message,'start',lang);return;
  }
  await sendHelpDoc(message,r,editing?editorRoot:null);
}
export async function helpCallback(c,data){
  const uid=c.from.id;
  if(c.message.chat.type!=='private'||!developer(uid)){await answer(c,await tr('MSG_DEV_ONLY_OPTION','ar'),true);return 'answered';}
  if(data==='help_builder:menu'){await reply(c.message,'⚙️ اختر من أدناه:',editorMenu);return true;}
  if(data==='help_builder:settext'||data==='help_builder:addbtn'){
    await updateUser(uid,{pendingAction:data==='help_builder:settext'?'help:text':'help:button'});
    await reply(c.message,data==='help_builder:settext'?
      '📝 أرسل نص /help الجديد (HTML أو نص عادي)، أو /cancel_edit.':
      '➕ أرسل الزر: <code>نص الزر | https://example.com</code> أو /cancel_edit.');
    return true;
  }
  if(data==='help_builder:buttons'){
    const r=await draft(uid),b=buttons(r);
    if(!b.length){await reply(c.message,'لا توجد أزرار في المسودة حالياً.',editorMenu);return true;}
    await reply(c.message,'🗑 اضغط على الزر الذي تريد حذفه:',kb([...b.map((item,i)=>[button('❌ '+item.text.slice(0,40),'help_builder:remove:'+i)]),[button('🔙 رجوع','help_builder:menu')]]));return true;
  }
  if(data.startsWith('help_builder:remove:')){
    const raw=data.slice('help_builder:remove:'.length),index=Number(raw),r=await draft(uid),b=buttons(r);
    if(!/^\d+$/.test(raw)||!Number.isSafeInteger(index)||index<0||index>=b.length){await answer(c,'زر غير موجود',true);return 'answered';}
    b.splice(index,1);
    await put(r.key,r.html,JSON.stringify(b),r.blocksJson,r.isRtl);
    await reply(c.message,'✅ تم حذف الزر.',editorMenu);return true;
  }
  if(data==='help_builder:preview'||data==='help_builder:back'){
    if(data==='help_builder:back')await updateUser(uid,{pendingAction:''});
    const r=await draft(uid);
    await sendHelpDoc(c.message,r,data==='help_builder:back'?editorRoot:null);return true;
  }
  if(data==='help_builder:save'){
    const r=await draft(uid);
    await put('published',r.html,r.buttonsJson,r.blocksJson,r.isRtl);
    await updateUser(uid,{pendingAction:''});
    await reply(c.message,'✅ تم حفظ ونشر رسالة /help الجديدة.');return true;
  }
  return false;
}
export async function helpMessage(message,user) {
  const uid=message.from?.id;
  if(message.chat.type!=='private'||!developer(uid)||!user?.pendingAction?.startsWith('help:'))return false;
  const action=user.pendingAction;
  const r=await draft(uid);
  if(action==='help:text'){
    const extracted=extractMessageContent(message);
    if(!extracted||(!extracted.html?.trim()&&!extracted.blocks)){
      await reply(message,'❌ أرسل نصاً أو رسالة غنية من تليكرام، أو /cancel_edit');return true;
    }
    // Keep the original structured Rich Message blocks, not just a text fallback.
    const value=extracted.html||'النص';
    if(value.length>25000||JSON.stringify(extracted.blocks||[]).length>100000){await reply(message,'❌ محتوى المسودة طويل جداً.');return true;}
    await put(r.key,value,r.buttonsJson,extracted.blocks?JSON.stringify(extracted.blocks):null,
      typeof extracted.isRtl==='boolean'?Number(extracted.isRtl):null);
    await updateUser(uid,{pendingAction:''});
    await reply(message,'✅ تم تحديث نص المسودة.',editorMenu);return true;
  }
  if(action==='help:button'){
    const raw=String(message.text||''),i=raw.indexOf('|');
    const label=i>=0?raw.slice(0,i).trim():'',url=i>=0?raw.slice(i+1).trim():'';
    if(!label||label.length>64||!safeHttpUrl(url)){await reply(message,'❌ الصيغة غلط، أرسل <code>الاسم | https://example.com</code>');return true;}
    const b=buttons(r);if(b.length>=40){await reply(message,'وصلت للحد الأقصى للأزرار.');return true;}
    b.push({text:label,url});
    await put(r.key,r.html,JSON.stringify(b),r.blocksJson,r.isRtl);
    await updateUser(uid,{pendingAction:''});
    await reply(message,'✅ تمت إضافة الزر.',editorMenu);return true;
  }
  return false;
}
