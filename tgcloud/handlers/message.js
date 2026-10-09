import { api } from 'sdk';
import { CONFIG, developer } from '../lib/config.js';
import { getUser, getSession, cancelSession } from '../lib/state.js';
import { tr } from '../lib/i18n.js';
import { startKeyboard } from '../lib/keyboard.js';
import { reply, replyText } from '../lib/io.js';
import { audioReceived, handlePhoto } from '../lib/wizard.js';
import { devStart, adminMessage } from '../lib/admin.js';
import { sendHelp, helpMessage } from '../lib/help.js';
import { validatePayment } from '../lib/payments.js';
import { addReceipt } from '../lib/state.js';

export default async function (message) {
  if(!message?.chat)return;
  const uid=message.from?.id||0,privateChat=message.chat.type==='private';
  // Payments must be handled before any other message route.
  if(message.successful_payment && uid && privateChat) {
    const p=message.successful_payment,user=await getUser(uid),lang=user.lang;
    if(!validatePayment(p.invoice_payload,p.currency,p.total_amount,uid)) {
      await reply(message,await tr('invalid',lang));return;
    }
    const inserted=await addReceipt(p,uid);
    if(inserted) {
      await reply(message,await tr('receipt',lang,{limit:CONFIG.PREMIUM_DAILY_LIMIT}));
      if(CONFIG.DEVELOPER_ID && uid!==CONFIG.DEVELOPER_ID) {
        try { await api.sendMessage({chat_id:CONFIG.DEVELOPER_ID,text:'⭐ اشتراك جديد: '+uid+' — '+p.total_amount+' نجمة'}); }
        catch(e){console.error('Could not notify developer',e);}
      }
    }
    return;
  }
  const addressed=(message.text||'').match(/^\/\w+@(\w+)(?:\s|$)/);
  if(addressed&&(await api.getMe()).username?.toLowerCase()!==addressed[1].toLowerCase())return;
  if(/^\/help(?:@\w+)?(?:\s|$)/.test(message.text||'') ||
      /^\/start(?:@\w+)?\s+help(?:\s|$)/.test(message.text||'')) {
    await sendHelp(message);return;
  }
  if(privateChat && /^\/start(?:@\w+)?(?:\s|$)/.test(message.text||'')) {
    if(!uid)return;
    const user=await getUser(uid),lang=user.lang;
    await replyText(message,'start',lang,await startKeyboard(uid,lang));return;
  }
  if(privateChat && uid) {
    const user=await getUser(uid);
    if(/^\/dev(?:@\w+)?$/.test(message.text||'') && developer(uid)){await devStart(message);return;}
    if(/^\/cancel(?:@\w+)?$/.test(message.text||'')) {
      const session=await getSession('u'+uid);
      if(session)await cancelSession(session);
      await replyText(message,session?'MSG_QUEUE_CANCELED_EDIT':'expired',user.lang);return;
    }
    if(await adminMessage(message,user))return;
    if(await helpMessage(message,user))return;
  }
  if(message.photo?.length && await handlePhoto(message))return;
  if(message.audio){
    const kind=message.chat.type==='channel'?'channel':
      ['group','supergroup'].includes(message.chat.type)?'group':'private';
    await audioReceived(message,kind);return;
  }
  if(privateChat && (message.voice||message.document||message.video)){
    const lang=(await getUser(uid))?.lang||'ar';
    await replyText(message,'wrong',lang);
  }
}
