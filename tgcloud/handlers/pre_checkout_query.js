import { api } from 'sdk';
import { CONFIG } from '../lib/config.js';
import { validatePayment } from '../lib/payments.js';
import { getUser } from '../lib/state.js';
export default async function(q) {
  if(!q?.id||!q.from)return;
  const valid=CONFIG.RENDERER_ENABLED && validatePayment(q.invoice_payload,q.currency,q.total_amount,q.from.id);
  const lang=(await getUser(q.from.id))?.lang||'ar';
  await api.answerPreCheckoutQuery({
    pre_checkout_query_id:q.id,ok:Boolean(valid),
    ...(!valid?{error_message:lang==='en'?'Subscriptions are currently unavailable. No payment will be taken.':'الاشتراك غير متاح للبيع حالياً. لن تُخصم أي دفعة.'}:{})
  });
}
