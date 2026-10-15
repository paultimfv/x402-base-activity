export const n0 = (x: number) => Math.round(x).toLocaleString("en-US");

export function compact(x: number): string {
  if (x >= 1e9) return (x / 1e9).toFixed(1) + "B";
  if (x >= 1e6) return (x / 1e6).toFixed(x >= 1e7 ? 1 : 2) + "M";
  if (x >= 1e3) return (x / 1e3).toFixed(x >= 1e4 ? 0 : 1) + "k";
  return String(Math.round(x));
}

export const pct = (x: number, d = 0) => (x * 100).toFixed(d) + "%";

export function usd(x: number): string {
  if (x === 0) return "$0";
  if (x < 0.01) return "$" + x.toFixed(4).replace(/0+$/, "");
  if (x < 1) return "$" + x.toFixed(3).replace(/0+$/, "").replace(/\.$/, "");
  if (x < 100) return "$" + x.toFixed(2);
  if (x < 1000) return "$" + Math.round(x);
  return "$" + compact(x);
}

export const short = (a: string) => a.slice(0, 6) + "…" + a.slice(-4);
