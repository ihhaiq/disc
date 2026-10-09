import { api, db } from 'sdk';
import { eq } from 'sdk/db';
import { users, overrides } from '../schema.js';
import { CONFIG, developer } from '../lib/config.js';
import { getUser, getSession, updateUser, canUseColor } from '../lib/state.js';
import { tr } from '../lib/i18n.js';
import { startKeyboard, speedKeyboard, colorKeyboard, payKeyboard } from '../lib/keyboard.js';
import { edit, answer, reply } from '../lib/io.js';
import { rotationSeconds, SPEEDS, STYLES } from '../lib/catalog.js';
import { callbackWizard } from '../lib/wizard.js';
import { developerCallback } from '../lib/admin.js';
import { helpCallback } from '../lib/help.js';
import { sendInvoice } from '../lib/payments.js';

function parseContext(raw) {
  const m=String(raw||'').match(/^(.*):(-?\d+):(\d+)$/);
  return m?{action:m[1],key:'g'+m[2]+':'+m[3],chatId:Number(m[2]),messageId:Number(m[3])}:{action:String(raw||''),key:null};
}
async function controller(c,session) {
  if(session.ownerId===c.from.id) return true;
  if(session.key.startsWith('u'))return false;
  try {
    const x=await api.getChatMember({chat_id:session.chatId,user_id:c.from.id});
    return ['administrator','creator'].includes(x.status);
  }catch {return false;}
}
async function editColorMenu(message,uid,lang) {
  const text=await tr('color',lang),keyboard=await colorKeyboard(uid,lang);
  if(message.photo?.length) {
    return api.editMessageCaption({chat_id:message.chat.id,message_id:message.message_id,
      caption:text,parse_mode:'HTML',reply_markup:keyboard});
  }
  return edit(message,text,keyboard);
}
export default async function (c) {
  if(!c?.id||!c?.from||!c?.data||!c.message)return;
  const uid=c.from.id;
  const u=await getUser(uid),lang=u?.lang||'ar';
  const parsed=parseContext(c.data),data=parsed.action;
  if(data.startsWith('dev_')||data==='dev_back'||data==='vinyl_menu_image:set'){
    if(!developer(uid)){await answer(c,'هذا الخيار للمطور فقط',true);return;}
    if(await developerCallback(c,data))await answer(c);return;
  }
  if(data.startsWith('help_builder:')){
    if(!developer(uid)){await answer(c,'هذا الخيار للمطور فقط',true);return;}
    if(await helpCallback(c,data))await answer(c);return;
  }
  if(data==='lang:toggle'){
    const next=lang==='ar'?'en':'ar';
    await updateUser(uid,{lang:next});
    const keys=c.message.reply_markup?.inline_keyboard?.flat().map(x=>x.callback_data)||[];
    if(keys.some(x=>x?.startsWith('vinyl:')))
      await editColorMenu(c.message,uid,next);
    else if(keys.some(x=>x?.startsWith('speed:')))
      await edit(c.message,await tr('customize',next),await speedKeyboard(next,null,u.rotation));
    else await edit(c.message,await tr('start',next)+(CONFIG.RENDERER_ENABLED?'':'\n\n'+await tr('renderer',next)),await startKeyboard(uid,next));
    await answer(c,next.toUpperCase());return;
  }
  if(data==='customize:open'){
    await edit(c.message,await tr('customize',lang),await speedKeyboard(lang,null,u.rotation));await answer(c);return;
  }
  if(data==='customize:back'){
    await edit(c.message,await tr('start',lang)+(CONFIG.RENDERER_ENABLED?'':'\n\n'+await tr('renderer',lang)),await startKeyboard(uid,lang));await answer(c);return;
  }
  if(data==='vinyl_menu:open'){
    const photo=await db.select().from(overrides).where(eq(overrides.key,'__vinyl_menu_photo_id')).get();
    if(photo?.value) {
      try {
        await api.deleteMessage({chat_id:c.message.chat.id,message_id:c.message.message_id});
        await api.sendPhoto({chat_id:c.message.chat.id,photo:photo.value,
          caption:await tr('color',lang),reply_markup:await colorKeyboard(uid,lang)});
      } catch(error) {
        console.warn('Vinyl menu photo unavailable, showing text menu',String(error?.description||error));
        await api.sendMessage({chat_id:c.message.chat.id,text:await tr('color',lang),
          parse_mode:'HTML',reply_markup:await colorKeyboard(uid,lang)});
      }
    }else await edit(c.message,await tr('color',lang),await colorKeyboard(uid,lang));
    await answer(c);return;
  }
  if(data==='vinyl_menu:back'){
    if(c.message.photo?.length){
      try {await api.deleteMessage({chat_id:c.message.chat.id,message_id:c.message.message_id});}
      catch(error){console.warn('Could not remove color menu photo',String(error?.description||error));}
      await api.sendMessage({chat_id:c.message.chat.id,text:await tr('customize',lang),
        parse_mode:'HTML',reply_markup:await speedKeyboard(lang,null,u.rotation)});
    }else await edit(c.message,await tr('customize',lang),await speedKeyboard(lang,null,u.rotation));
    await answer(c);return;
  }
  if(data.startsWith('vinyl:')){
    const key=data.slice(6);
    if(!STYLES.some(x=>x.key===key)){await answer(c,'Invalid style',true);return;}
    if(!(await canUseColor(uid,key))){
      await answer(c,await tr(CONFIG.RENDERER_ENABLED?'premium':'renderer',lang),true);return;
    }
    await updateUser(uid,{style:key});
    await editColorMenu(c.message,uid,lang);
    await answer(c,lang==='en'?'Saved':'✅ تم حفظ الاختيار');return;
  }
  if(data.startsWith('speed:')){
    const speed=data.slice(6);
    if(!SPEEDS.includes(speed)){await answer(c,'Invalid speed',true);return;}
    await updateUser(uid,{rotation:String(rotationSeconds(speed))});
    await edit(c.message,await tr('customize',lang),await speedKeyboard(lang,null,String(rotationSeconds(speed))));
    await answer(c,lang==='en'?'Saved':'✅ تم حفظ السرعة');return;
  }
  if(data==='buy_stars'){
    const ok=await sendInvoice(c.message.chat.id,uid,lang);
    await answer(c,ok?'':await tr('renderer',lang),!ok);return;
  }
  const key=parsed.key?('g'+parsed.chatId+':'+parsed.messageId):'u'+uid;
  let s=await getSession(key);
  if(!s && parsed.key)s=await getSession('c'+parsed.chatId+':'+parsed.messageId);
  if(!s){await answer(c,await tr('expired',lang),true);return;}
  if(!(await controller(c,s))){await answer(c,await tr('denied',lang),true);return;}
  const handled=await callbackWizard(c,s,data);
  if(handled===true)await answer(c);
  else if(handled==='alert')return;
  else await answer(c,await tr('expired',lang),true);
}
