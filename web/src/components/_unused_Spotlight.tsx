import type { SliceData, SliceMeta } from "@/lib/types";
import { compact, n0, pct, usd, short } from "@/lib/fmt";

/* The busiest paying wallet of the selected week, with its day-by-day count. */
export function Spotlight({ s, meta, labels }: { s: SliceData["spotlight"]; meta: SliceMeta; labels: Record<string, string> }) {
  const max = Math.max(...s.daily, 1);
  const perSec = s.payments / (7 * 86400);
  const d0 = new Date(meta.start + "T00:00:00Z");
  return (
    <aside className="spot wide" aria-label="Busiest wallet">
      <div className="spot-text">
        <p className="spot-h">Largest paying wallet, {meta.label} week</p>
        <p className="spot-addr">
          <a className="addr" href={`https://basescan.org/address/${s.payer}`} target="_blank" rel="noreferrer">{short(s.payer)}</a>
          {" "}paid {s.top_payee_name ?? short(s.top_payee)}{s.payees > 1 ? ` and ${s.payees - 1} other payee${s.payees > 2 ? "s" : ""}` : " and no one else"}.
        </p>
        <dl className="spot-dl">
          <div><dt>Payments</dt><dd className="num">{n0(s.payments)}</dd></div>
          <div><dt>Share of the week</dt><dd className="num">{pct(s.share)}</dd></div>
          <div><dt>Average rate</dt><dd className="num">{perSec >= 1 ? perSec.toFixed(1) + " per second" : compact(s.payments / 7) + " a day"}</dd></div>
          <div><dt>Spent</dt><dd className="num">{usd(s.usd)}</dd></div>
          <div><dt>Distinct prices paid</dt><dd className="num">{n0(s.distinct_prices)}</dd></div>
          <div><dt>Active in sample weeks</dt><dd>{s.seen_in.map((x) => labels[x] ?? x).join(", ")}</dd></div>
        </dl>
      </div>
      <div className="spot-chart" role="img" aria-label="Payments per day">
        {s.daily.map((v, i) => (
          <div key={i} className="sd">
            <span className="num">{compact(v)}</span>
            <i style={{ height: `${(v / max) * 100}%` }} />
            <em>{new Date(d0.getTime() + i * 86400e3).toLocaleDateString("en-US", { weekday: "short", timeZone: "UTC" })}</em>
          </div>
        ))}
      </div>
    </aside>
  );
}
