import { audioReceived } from '../lib/wizard.js';
export default async function(message) {
  if(message?.audio)await audioReceived(message,'channel');
}
