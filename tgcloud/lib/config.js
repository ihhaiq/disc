// Values matched to config.py on main. Edit DEVELOPER_ID before enabling admin features.
export const CONFIG = Object.freeze({
  DEVELOPER_ID: 0,
  FREE_DAILY_LIMIT: 3,
  PREMIUM_DAILY_LIMIT: 50,
  STARS_SUBSCRIPTION_PRICE: 50,
  STARS_SUBSCRIPTION_DAYS: 30,
  MAX_DURATION_SECONDS: 60,
  MAX_TELEGRAM_AUDIO_SIZE_BYTES: 20 * 1024 * 1024,
  SESSION_TTL_SECONDS: 600,
  ROTATION_SECONDS: 4,
  DISC_SIZE: 640,
  OUTPUT_FPS: 30,
  HOLE_RATIO: 0.42,
  RENDERER_ENABLED: false,
});
export const now = () => Math.floor(Date.now() / 1000);
export function developer(id) {
  return CONFIG.DEVELOPER_ID > 0 && Number(id) === CONFIG.DEVELOPER_ID;
}
