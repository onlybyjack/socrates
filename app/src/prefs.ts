/** Small per-device preferences. Storage can be unavailable; every access is guarded. */
export interface Prefs {
  onboarded: boolean;
  /** Answer by typing instead of the microphone. */
  textMode: boolean;
  micId?: string;
  micLabel?: string;
}

const KEY = "socrates.prefs";
const DEFAULTS: Prefs = { onboarded: false, textMode: false };

export function loadPrefs(): Prefs {
  try {
    const raw = localStorage.getItem(KEY);
    return raw ? { ...DEFAULTS, ...JSON.parse(raw) } : { ...DEFAULTS };
  } catch {
    return { ...DEFAULTS };
  }
}

export function savePrefs(p: Prefs) {
  try {
    localStorage.setItem(KEY, JSON.stringify(p));
  } catch {
    /* storage blocked: preferences last for this session only */
  }
}
