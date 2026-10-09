import { api } from 'sdk';
import { STYLES, SPEEDS, rotationSeconds } from './catalog.js';
import { CONFIG } from './config.js';
import { tr } from './i18n.js';
import { getUser, colorPaid, premium } from './state.js';

export const kb = rows => ({inline_keyboard:rows});
const cb=(text,callback_data,extra={})=>({text,callback_data,...extra});
export const ctxData=(data,s)=>s.key.startsWith('u')?data:data+':'+s.chatId+':'+s.messageId;
export async function startKeyboard(uid,lang) {
  const me=await api.getMe();
  return kb([
    [{text:lang==='en'?'➕ Add to group':'➕ أضفني للمجموعة',url:'https://t.me/'+me.username+'?startgroup=start',style:'primary'}],
    [cb(await tr('lang',lang),'lang:toggle',{style:'success'}),cb(await tr('customize',lang),'customize:open',{style:'danger'})]
  ]);
}
export async function speedKeyboard(lang,s=null) {
  const labels=(await tr('speedLabels',lang));
  const names=Array.isArray(labels)?labels:['Full turn','8 RPM','19 RPM','33 RPM','45 RPM'];
  const buttons=SPEEDS.map((speed,i)=>cb(names[i]+(s && String(s.rotation)===String(rotationSeconds(speed))?' ✅':''),s?ctxData('wiz_speed:'+speed,s):'speed:'+speed,{style:'primary'}));
  if(s) return kb([buttons.slice(0,2),buttons.slice(2,4),buttons.slice(4)]);
  return kb([buttons.slice(0,2),buttons.slice(2,4),buttons.slice(4),[cb(await tr('color',lang),'vinyl_menu:open')],[cb(await tr('back',lang),'customize:back')]]);
}
export async function colorKeyboard(uid,lang,s=null) {
  const u=await getUser(uid), allowed=await premium(uid);
  const rows=[];
  for(const row of [...new Set(STYLES.map(x=>x.row))].sort((a,b)=>a-b)) {
    const arr=[];
    for(const style of STYLES.filter(x=>x.row===row)) {
      const paid=await colorPaid(style.key);
      const selected=(s?s.style:u?.style)===style.key;
      arr.push(cb((paid&&!allowed?'🔒 ':'')+(lang==='en'?style.label:style.ar)+(selected?' ✅':''),s?ctxData('wiz_color:'+style.key,s):'vinyl:'+style.key,{
        style:selected?'success':'default',...(style.emoji?{icon_custom_emoji_id:style.emoji}:{})
      }));
    }
    rows.push(arr);
  }
  rows.push([{text:lang==='en'?'Preview templates':'معاينة',url:'https://t.me/VinylTemplate'}]);
  if(!s) rows.push([cb(await tr('back',lang),'vinyl_menu:back')]);
  return kb(rows);
}
export async function modeKeyboard(uid,lang,s) {
  return kb([[cb(await tr('quick',lang),ctxData('mode:quick',s))],[cb(await tr('customize',lang),ctxData('mode:custom',s))],[cb(await tr('cancel',lang),ctxData('cancel_queue',s))]]);
}
export async function photoKeyboard(uid,lang,s) {
  return kb([[cb(await tr('skip',lang),ctxData('wiz_image:skip',s))],[cb(await tr('cancel',lang),ctxData('cancel_queue',s))]]);
}
export async function segmentKeyboard(uid,lang,s) {
  const n=Math.min(20,Math.ceil(s.duration/60)),rows=[];
  for(let i=0;i<n;i+=3) rows.push([i,i+1,i+2].filter(k=>k<n).map(k=>cb((lang==='en'?'⏱ Minute ':'⏱ الدقيقة ')+(k+1),ctxData('wiz_segment:'+(k*60),s),{style:'success'})));
  return kb(rows);
}
export async function confirmKeyboard(uid,lang,s) {
  return kb([[cb(await tr('preview',lang),ctxData('wiz_preview_confirm',s))],[cb(await tr('full',lang),ctxData('wiz_full_confirm',s))],[cb(await tr('cancel',lang),ctxData('cancel_queue',s))]]);
}
export async function payKeyboard(lang) {
 return kb([[cb(await tr('buy',lang,{price:CONFIG.STARS_SUBSCRIPTION_PRICE}),'buy_stars')]]);
}
export const DEV_MENU=kb([[cb('🔒 الأقراص المدفوعة','dev_limits:open')],[cb('🛡 القائمة البيضاء','dev_whitelist:open')],[cb('📝 /help','help_builder:menu')],[cb('✏️ تحرير النصوص','dev_text:menu')]]);
