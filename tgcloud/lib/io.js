import { api } from 'sdk';
import { tr } from './i18n.js';
export async function reply(message,text,reply_markup=null) {
  return api.sendMessage({chat_id:message.chat.id,text,parse_mode:'HTML',reply_to_message_id:message.message_id,...(reply_markup?{reply_markup}:{})});
}
export async function send(chatId,text,markup=null) {
  return api.sendMessage({chat_id:chatId,text,parse_mode:'HTML',...(markup?{reply_markup:markup}:{})});
}
export async function edit(message,text,markup=null) {
  const props={chat_id:message.chat.id,message_id:message.message_id,text,parse_mode:'HTML',...(markup?{reply_markup:markup}:{})};
  try {return await api.editMessageText(props);}
  catch(e){ if(String(e?.description||e).includes('message is not modified'))return; throw e; }
}
export async function answer(callback,text='',alert=false) {
  return api.answerCallbackQuery({callback_query_id:callback.id,...(text?{text,show_alert:alert}:{})});
}
export async function textFor(uid,lang,key,params={}){return tr(key,lang,params);}
