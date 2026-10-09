// Matches vinyl_catalog.py on main; image templates remain binary assets outside V8.
export const STYLES = Object.freeze([
  { key:'default', textKey:'BTN_VINYL_BLACK', label:'⚫ Black', ar:'⚫ الأسود', row:0, disc:'vinyl.png', shadow:'shadow.png', emoji:'5399878127163811970' },
  { key:'pink', textKey:'BTN_VINYL_PINK', label:'💗 Pink', ar:'💗 وردي', row:1, disc:'vinyl_pink.png', shadow:'shadow_pink.png' },
  { key:'blue', textKey:'BTN_VINYL_BLUE', label:'💙 Blue', ar:'💙 أزرق', row:1, disc:'vinyl_blue.png', shadow:'shadow_blue.png' },
  { key:'yellow', textKey:'BTN_VINYL_YELLOW', label:'💛 Yellow', ar:'💛 أصفر', row:2, disc:'vinyl_yellow.png', shadow:'shadow_yellow.png' },
  { key:'red', textKey:'BTN_VINYL_RED', label:'❤️ Red', ar:'❤️ أحمر', row:2, disc:'vinyl_red.png', shadow:'shadow_red.png' },
  { key:'green', textKey:'BTN_VINYL_GREEN', label:'Green (beta)', ar:'اخضر تجريبي', row:3, disc:'vinyl_green.png', shadow:'shadow_green.png' },
  { key:'bloody', textKey:'BTN_VINYL_BLOODY', label:'🩸 Bloody', ar:'🩸', row:3, disc:'vinyl_bloody.png', shadow:'shadow_pink.png' },
  { key:'rose', textKey:'BTN_VINYL_ROSE', label:'ROSE💮', ar:'ROSE💮', row:4, disc:'vinyl_rose.png', shadow:'shadow_rose.png' },
  { key:'emerald', textKey:'BTN_VINYL_EMERALD', label:'EMERALD', ar:'EMERALD', row:5, disc:'vinyl_emerald.png', shadow:'shadow_rose.png', emoji:'5285265490350972397' },
  { key:'koi', textKey:'BTN_VINYL_KOI', label:'KOI', ar:'KOI', row:6, disc:'vinyl_koi.png', shadow:'shadow_rose.png', emoji:'5339487433828353468' },
  { key:'kiss', textKey:'BTN_VINYL_KISS', label:'KISS', ar:'KISS', row:6, disc:'vinyl_kiss.png', shadow:'shadow_rose.png', holeRatio:0.39, emoji:'5474525960143385880' },
  { key:'ali', textKey:'BTN_VINYL_ALI', label:'ALI', ar:'علي رشم', row:6, disc:'vinyl_ali.png', shadow:'shadow_rose.png', emoji:'5460737770798489825' },
  { key:'ocean', textKey:'BTN_VINYL_OCEAN', label:'OCEAN', ar:'OCEAN', row:7, disc:'vinyl_ocean.png', shadow:'shadow_rose.png' },
]);
export function styleOf(key) { return STYLES.find(x=>x.key===key) || STYLES[0]; }
export const SPEEDS = Object.freeze(['full','8','19','33','45']);
export function rotationSeconds(speed) {
  return speed === 'full' ? 0 : SPEEDS.includes(String(speed)) ? 60/Number(speed) : 4;
}
