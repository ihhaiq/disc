import { audioReceived, handlePhoto } from '../lib/wizard.js';
export default async function(message) {
  if(!message?.chat || message.chat.type!=='channel')return;
  if(message.photo?.length && await handlePhoto(message))return;
  if(message.audio)await audioReceived(message,'channel');
}
