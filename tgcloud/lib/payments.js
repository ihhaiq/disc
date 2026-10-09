import { api } from 'sdk';
import { CONFIG } from './config.js';
import { tr } from './i18n.js';
export function validatePayment(payload,currency,amount,uid){
  const parts=String(payload||'').split('_');
  return parts.length===3&&parts[0]==='sub'&&Number(parts[1])===uid&&Number(parts[2])>0&&
    currency==='XTR'&&amount===CONFIG.STARS_SUBSCRIPTION_PRICE;
}
export async function sendInvoice(chatId,uid,lang) {
  if(!CONFIG.RENDERER_ENABLED) return false; // no selling a currently unusable service
  await api.sendInvoice({
    chat_id:chatId, title:lang==='en'?'30-day subscription':'اشتراك 30 يوم - رفع الحد اليومي',
    description:lang==='en'?'Up to 50 discs per 24 hours for 30 days':'يرفع الحد اليومي إلى 50 قرص لمدة 30 يوم',
    payload:'sub_'+uid+'_'+Math.floor(Date.now()/1000),provider_token:'',currency:'XTR',
    prices:[{label:lang==='en'?'30-day subscription':'اشتراك 30 يوم',amount:CONFIG.STARS_SUBSCRIPTION_PRICE}],
  });return true;
}
