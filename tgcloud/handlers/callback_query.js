import { api } from 'sdk';
import { eq } from 'sdk/db';
import { users } from '../schema.js';
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
export default async function (c) {
  if(!c?.id||!c?.from||!c?.data||!c.message)return;
  const uid=c.from.id;
  const u=await getUser(uid),lang=u?.lang||'ar';
  const parsed=parseContext(c.data),data=parsed.action;
  if(data.startsWith('dev_')||data==='dev_back'){
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
      await edit(c.message,await tr('color',next),await colorKeyboard(uid,next));
    else if(keys.some(x=>x?.startsWith('speed:')))
      await edit(c.message,await tr('customize',next),await speedKeyboard(next));
    else await edit(c.message,await tr('start',next)+(CONFIG.RENDERER_ENABLED?'':'\n\n'+await tr('renderer',next)),await startKeyboard(uid,next));
    await answer(c,next.toUpperCase());return;
  }
  if(data==='customize:open'){
    await edit(c.message,await tr('customize',lang),await speedKeyboard(lang));await answer(c);return;
  }
  if(data==='customize:back'){
    await edit(c.message,await tr('start',lang)+(CONFIG.RENDERER_ENABLED?'':'\n\n'+await tr('renderer',lang)),await startKeyboard(uid,lang));await answer(c);return;
  }
  if(data==='vinyl_menu:open'){
    await edit(c.message,await tr('color',lang),await colorKeyboard(uid,lang));await answer(c);return;
  }
  if(data==='vinyl_menu:back'){
    await edit(c.message,await tr('customize',lang),await speedKeyboard(lang));await answer(c);return;
  }
  if(data.startsWith('vinyl:')){
    const key=data.slice(6);
    if(!STYLES.some(x=>x.key===key)){await answer(c,'Invalid style',true);return;}
    if(!(await canUseColor(uid,key))){
      await answer(c,await tr('premium',lang),true);return;
    }
    await updateUser(uid,{style:key});
    await edit(c.message,await tr('color',lang),await colorKeyboard(uid,lang));
    await answer(c,lang==='en'?'Saved':'✅ تم حفظ الاختيار');return;
  }
  if(data.startsWith('speed:')){
    const speed=data.slice(6);
    if(!SPEEDS.includes(speed)){await answer(c,'Invalid speed',true);return;}
    await updateUser(uid,{rotation:String(rotationSeconds(speed))});
    await edit(c.message,await tr('customize',lang),await speedKeyboard(lang));
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
