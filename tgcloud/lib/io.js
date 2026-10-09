import { api } from 'sdk';
import { tr } from './i18n.js';
import { escapeHtml } from './dev-text-utils.js';

// Keep the original text visible when a legacy developer override contains
// malformed/unsupported HTML. Do not conceal other Telegram/API errors.
function parseFailure(e) {
  const reason=String(e?.description||e||'').toLowerCase();
  return /can't parse entities|can't find end tag|unsupported start tag|entity parsing/.test(reason);
}
export async function reply(message,text,reply_markup=null) {
  const props={chat_id:message.chat.id,text,parse_mode:'HTML',
    reply_to_message_id:message.message_id,...(reply_markup?{reply_markup}:{})};
  try {return await api.sendMessage(props);}
  catch(e){if(!parseFailure(e))throw e;return api.sendMessage({...props,text:escapeHtml(text)});}
}
export async function send(chatId,text,markup=null) {
  const props={chat_id:chatId,text,parse_mode:'HTML',...(markup?{reply_markup:markup}:{})};
  try {return await api.sendMessage(props);}
  catch(e){if(!parseFailure(e))throw e;return api.sendMessage({...props,text:escapeHtml(text)});}
}
export async function edit(message,text,markup=null) {
  const props={chat_id:message.chat.id,message_id:message.message_id,text,parse_mode:'HTML',
    ...(markup?{reply_markup:markup}:{})};
  try {return await api.editMessageText(props);}
  catch(e) {
    if(String(e?.description||e).includes('message is not modified'))return;
    if(parseFailure(e))return api.editMessageText({...props,text:escapeHtml(text)});
    throw e;
  }
}
export async function answer(callback,text='',alert=false) {
  return api.answerCallbackQuery({callback_query_id:callback.id,...(text?{text,show_alert:alert}:{})});
}
export async function textFor(uid,lang,key,params={}){return tr(key,lang,params);}
