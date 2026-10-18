/** NT$ amount in 億 (100M), the unit Taiwanese financial reports are read in. */
export function yi(v: number | null | undefined, digits = 1): string {
  if (v === null || v === undefined) return '—';
  return `${(v / 1e8).toLocaleString('zh-TW', { maximumFractionDigits: digits, minimumFractionDigits: digits })} 億`;
}

export function pct(v: number | null | undefined, digits = 1, signed = true): string {
  if (v === null || v === undefined) return '—';
  const s = v.toFixed(digits);
  return `${signed && v > 0 ? '+' : ''}${s}%`;
}

export function lots(v: number): string {
  return `${v > 0 ? '+' : ''}${v.toLocaleString('zh-TW')} 張`;
}

export function ratio(a: number | null, b: number | null): number | null {
  if (a === null || b === null || b === 0) return null;
  return (a / b) * 100;
}

/** Taiwan market convention: red means up, green means down. */
export function upDownClass(v: number | null | undefined): string {
  if (v === null || v === undefined || v === 0) return 'text-slate-600';
  return v > 0 ? 'text-red-600' : 'text-green-700';
}

/** ISO timestamp shown in Taiwan time, e.g. 2026/10/18 23:00. */
export function dateTime(iso: string | null | undefined): string {
  if (!iso) return '—';
  return new Date(iso).toLocaleString('zh-TW', {
    timeZone: 'Asia/Taipei', year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit', hour12: false,
  });
}
