"use client";
import type { Live } from "@/lib/live-types";
import { HBars } from "./charts";
import { n0, pct, usd } from "@/lib/fmt";

/** "Live" strip above the study: the last 30 days on Base, same payment definition, updated hourly. */
export default function LivePanel({ live }: { live: Live }) {
  const days = live.daily;
  const full = days.slice(0, -1);                 // today is still filling
  const y = full[full.length - 1];
  const last7 = full.slice(-7);
  const p7 = last7.reduce((s, d) => s + d.payments, 0);
  const u7 = last7.reduce((s, d) => s + d.usd, 0);
  const shares = last7.map((d) => d.facilitator_share).filter((v): v is number => v != null);
  const fac = shares.length ? shares.reduce((a, b) => a + b, 0) / shares.length : null;
  const today = days[days.length - 1];
  return (
    <section aria-label="Live, last 30 days">
      <div className="wide">
        <p className="figt">Live: the last {days.length} days</p>
        <p className="figs">
          Same payment definition as the study, read hourly from Base. Through {live.throughTime.replace("T", " ").slice(0, 16)} UTC;
          today so far: {n0(today?.payments ?? 0)} payments.
        </p>
        <div className="stats">
          <div><div className="v">{n0(y?.payments ?? 0)}</div><div className="k">payments yesterday ({y?.day})</div></div>
          <div><div className="v">{n0(p7)}</div><div className="k">payments, last 7 full days ({usd(u7)})</div></div>
          <div><div className="v">{y?.median_usd == null ? "n/a" : usd(y.median_usd)}</div><div className="k">median payment yesterday</div></div>
          <div><div className="v">{fac == null ? "n/a" : pct(fac)}</div><div className="k">sent by a listed facilitator (10% sample, 7 days)</div></div>
        </div>
      </div>
      <div className="wide twoup">
        <figure className="fig">
          <p className="figt">Payments per day</p>
          <p className="figs">UTC days; the latest is still filling.</p>
          <HBars rows={[...days].reverse()} value={(r) => r.payments} label={(r) => r.day.slice(5)} fmt={(v) => n0(v)}
            sub={(r) => usd(r.usd)} />
        </figure>
        <figure className="fig">
          <p className="figt">Top payees, last 7 full days</p>
          <p className="figs">By number of payments; share of all payments in the window.</p>
          <HBars rows={live.topPayees7d} value={(r) => r.share} label={(r) => r.name ?? `${r.payee.slice(0, 6)}…${r.payee.slice(-4)}`}
            sub={(r) => `${n0(r.payments)} · ${usd(r.usd)}`} />
        </figure>
      </div>
    </section>
  );
}
