import test from 'node:test';
import assert from 'node:assert/strict';
import {STYLES,SPEEDS,styleOf,rotationSeconds} from '../../tgcloud/lib/catalog.js';
import {CONFIG} from '../../tgcloud/lib/config.js';

test('catalog mirrors 13 Python VINYL_STYLES with no duplicates',()=>{
  assert.equal(STYLES.length,13);
  assert.equal(new Set(STYLES.map(s=>s.key)).size,STYLES.length);
  assert.deepEqual(STYLES.map(s=>s.key),['default','pink','blue','yellow','red','green','bloody','rose','emerald','koi','kiss','ali','ocean']);
  assert.equal(styleOf('nonexistent').key,'default');
  assert.equal(styleOf('kiss').holeRatio,0.39);
  assert.equal(STYLES.find(s=>s.key==='bloody').shadow,'shadow_pink.png');
});
test('rotation settings match Python full/8/19/33/45 RPM choices',()=>{
  assert.deepEqual(SPEEDS,['full','8','19','33','45']);
  assert.equal(rotationSeconds('full'),0);
  assert.equal(rotationSeconds('8'),7.5);
  assert.ok(Math.abs(rotationSeconds('33')-(60/33))<1e-10);
  assert.equal(rotationSeconds('invalid'),4);
});
test('original defaults preserved and renderer explicitly disabled',()=>{
  assert.equal(CONFIG.FREE_DAILY_LIMIT,3);
  assert.equal(CONFIG.PREMIUM_DAILY_LIMIT,50);
  assert.equal(CONFIG.STARS_SUBSCRIPTION_PRICE,50);
  assert.equal(CONFIG.STARS_SUBSCRIPTION_DAYS,30);
  assert.equal(CONFIG.MAX_DURATION_SECONDS,60);
  assert.equal(CONFIG.DISC_SIZE,640);
  assert.equal(CONFIG.OUTPUT_FPS,30);
  assert.equal(CONFIG.RENDERER_ENABLED,false);
});
