import { api } from 'sdk';

export function parseContext(raw) {
  if(typeof raw!=='string' || raw.length>64) return null;
  const match=raw.match(/^(.*):(-?\d+):(\d+)$/);
  if(!match) return {action:raw,key:null};
  const chatId=Number(match[2]),messageId=Number(match[3]);
  if(!Number.isSafeInteger(chatId)||!Number.isSafeInteger(messageId)||!chatId||messageId<=0) return null;
  return {action:match[1],chatId,messageId,key:'g'+chatId+':'+messageId};
}

export async function controlsSession(uid, s) {
  if(!uid||!s) return false;
  if(s.ownerId===uid) return true;
  if(s.key.startsWith('u')) return false;
  try {
    const member=await api.getChatMember({chat_id:s.chatId,user_id:uid});
    return ['administrator','creator'].includes(member.status);
  } catch(error) {
    if(error?.code===400||error?.code===403) return false;
    throw error;
  }
}

export function matchesPrompt(c, s, parsed) {
  if(!s||s.chatId!==c.message.chat.id||s.promptId!==c.message.message_id) return false;
  return parsed.key ? parsed.chatId===s.chatId&&parsed.messageId===s.messageId : s.key==='u'+c.from.id;
}
