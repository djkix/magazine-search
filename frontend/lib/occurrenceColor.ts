// Endpoints of the occurrence-count color scale: low occurrence counts read
// as the app's neutral muted gray, high counts ramp toward its emerald
// "success" green, so the most relevant results visually pop the most.
const LOW = { r: 0x8b, g: 0xa0, b: 0xc2 }; // foreground-muted
const HIGH = { r: 0x34, g: 0xd3, b: 0x99 }; // emerald-400

export function occurrenceColorRgb(count: number, max: number): string {
  const t = max > 0 ? Math.min(count / max, 1) : 0;
  const r = Math.round(LOW.r + (HIGH.r - LOW.r) * t);
  const g = Math.round(LOW.g + (HIGH.g - LOW.g) * t);
  const b = Math.round(LOW.b + (HIGH.b - LOW.b) * t);
  return `${r}, ${g}, ${b}`;
}
