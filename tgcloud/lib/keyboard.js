import { api } from 'sdk';
import { STYLES, SPEEDS, rotationSeconds } from './catalog.js';
import { ORIGINAL_AR } from './original-texts.js';
import { CONFIG } from './config.js';
import { tr } from './i18n.js';
import { getUser, colorPaid, premium } from './state.js';

export const kb = rows => ({inline_keyboard:rows});
const cb=(text,callback_data,extra={})=>({text,callback_data,...extra});
export const ctxData=(data,s)=>s.key.startsWith('u')?data:data+':'+s.chatId+':'+s.messageId;
export async function startKeyboard(uid,lang) {
  const me=await api.getMe();
  return kb([
    [{text:lang==='en'?'➕ Add me to a group':'➕ أضفني للمجموعة',url:'https://t.me/'+me.username+'?startgroup=start',style:'primary'}],
    [cb(await tr('lang',lang),'lang:toggle',{style:'success'}),cb(await tr('customize',lang),'customize:open',{style:'danger'})]
  ]);
}
export async function speedKeyboard(lang,s=null,selectedRotation=null) {
  const names=await Promise.all(['SPEED_LABEL_FULL','SPEED_LABEL_8RPM',
    'SPEED_LABEL_19RPM','SPEED_LABEL_33RPM','SPEED_LABEL_45RPM'].map(key=>tr(key,lang)));
  const buttons=SPEEDS.map((speed,i)=>cb(names[i]+(String(s?.rotation ?? selectedRotation)===String(rotationSeconds(speed))?' ✅':''),s?ctxData('wiz_speed:'+speed,s):'speed:'+speed,{style:'primary'}));
  if(s) return kb([buttons.slice(0,2),buttons.slice(2,4),buttons.slice(4),[cb(await tr('cancel',lang),ctxData('cancel_queue',s))]]);
  return kb([buttons.slice(0,2),buttons.slice(2,4),buttons.slice(4),[cb(await tr('BTN_VINYL_COLOR_MENU',lang),'vinyl_menu:open',{style:'danger'})],[cb(await tr('back',lang),'customize:back')]]);
}
export async function colorKeyboard(uid,lang,s=null) {
  const u=await getUser(uid), allowed=await premium(uid);
  const rows=[];
  for(const row of [...new Set(STYLES.map(x=>x.row))].sort((a,b)=>a-b)) {
    const arr=[];
    for(const style of STYLES.filter(x=>x.row===row)) {
      const paid=await colorPaid(style.key);
      const selected=(s?s.style:u?.style)===style.key;
      arr.push(cb((paid&&!allowed?'🔒 ':'')+(await tr(style.textKey,lang))+(selected&&!s?' ✅':''),s?ctxData('wiz_color:'+style.key,s):'vinyl:'+style.key,{
        style:s?'primary':selected?'success':'default',
        ...(style.emoji?{icon_custom_emoji_id:style.emoji}:{})
      }));
    }
    rows.push(arr);
  }
  rows.push([{text:await tr('BTN_VINYL_COLOR_PREVIEW',lang),url:'https://t.me/VinylTemplate',
    icon_custom_emoji_id:'5904219717073114606'}]);
  if(!s) rows.push([cb(await tr('back',lang),'vinyl_menu:back')]);
  else rows.push([cb(await tr('cancel',lang),ctxData('cancel_queue',s))]);
  return kb(rows);
}
export async function modeKeyboard(uid,lang,s) {
  return kb([[cb(await tr('quick',lang),ctxData('mode:quick',s))],[cb(await tr('customize',lang),ctxData('mode:custom',s))],[cb(await tr('cancel',lang),ctxData('cancel_queue',s))]]);
}
export async function photoKeyboard(uid,lang,s) {
  const rows=[];
  if(s.thumbId) rows.push([cb(await tr('skip',lang),ctxData('wiz_image:skip',s))]);
  rows.push([cb(await tr('cancel',lang),ctxData('cancel_queue',s))]);
  return kb(rows);
}
export async function segmentKeyboard(uid,lang,s,page=0) {
  const n=Math.max(1,Math.ceil(s.duration/60)),totalPages=Math.ceil(n/20);
  const p=Math.max(0,Math.min(totalPages-1,Math.floor(page)));
  const start=p*20,end=Math.min(n,start+20),rows=[];
  for(let i=start;i<end;i+=3)
    rows.push([i,i+1,i+2].filter(k=>k<end).map(k=>
      cb((lang==='en'?'⏱ Minute ':'⏱ الدقيقة ')+(k+1),
        ctxData('wiz_segment:'+(k*60),s),{style:'success'})));
  const nav=[];
  if(p>0)nav.push(cb(lang==='en'?'⬅️ Previous':'⬅️ السابق',ctxData('wiz_segment_page:'+(p-1),s)));
  if(p<totalPages-1)nav.push(cb(lang==='en'?'Next ➡️':'التالي ➡️',ctxData('wiz_segment_page:'+(p+1),s)));
  if(nav.length)rows.push(nav);
  rows.push([cb(await tr('cancel',lang),ctxData('cancel_queue',s))]);
  return kb(rows);
}
export async function confirmKeyboard(uid,lang,s) {
  return kb([[cb(await tr('preview',lang),ctxData('wiz_preview_confirm',s))],[cb(await tr('full',lang),ctxData('wiz_full_confirm',s))],[cb(await tr('cancel',lang),ctxData('cancel_queue',s))]]);
}
export async function payKeyboard(lang) {
 return kb([[cb(await tr('buy',lang,{price:CONFIG.STARS_SUBSCRIPTION_PRICE}),'buy_stars')]]);
}
// Static fallback matches the initial Python menu; developerKeyboard() additionally
// loads developer-edited text overrides to preserve the original mutable labels.
const devRows = label => [
  ...[...new Set(STYLES.map(s=>s.row))].sort((a,b)=>a-b).map(row=>
    STYLES.filter(s=>s.row===row).map(style=>cb(label(style.textKey),'vinyl:'+style.key,
      style.emoji?{icon_custom_emoji_id:style.emoji}:{}))),
  [cb(label('BTN_DEV_SET_MENU_IMAGE'),'vinyl_menu_image:set')],
  [cb('✏️ تحرير النصوص (عربي)','dev_text:page:ar:0')],
  [cb('✏️ Edit Texts (English)','dev_text:page:en:0')],
  [cb('🛡️ القائمة البيضاء','dev_whitelist:open')],
  [cb(label('BTN_DEV_LIMITS_MENU'),'dev_limits:open')],
];
export const DEV_MENU=kb(devRows(key=>ORIGINAL_AR[key]||key));
export async function developerKeyboard() {
  const keys=['BTN_DEV_SET_MENU_IMAGE','BTN_DEV_LIMITS_MENU',...STYLES.map(s=>s.textKey)];
  const labels=await Promise.all(keys.map(k=>tr(k,'ar')));
  const lookup=new Map(keys.map((k,i)=>[k,labels[i]]));
  return kb(devRows(key=>lookup.get(key)||key));
}
