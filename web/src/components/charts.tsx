"use client";
import { useState } from "react";
import type { CategoryRow, PayeeRow, PriceRow, FacRow, HourRow } from "@/lib/types";
import { colorFor } from "@/lib/types";
import { compact, n0, pct, usd, short } from "@/lib/fmt";

/* ---------- Composition bar: one week of payments by what they paid for ---------- */
export function CompositionBar({
  rows, total, active, onPick,
}: { rows: CategoryRow[]; total: number; active: string | null; onPick: (c: string | null) => void }) {
  const sorted = [...rows].sort((a, b) => b.payments - a.payments);
  return (
    <div className="comp wide">
      <div className="bar" role="group" aria-label="Payments by category">
        {sorted.map((r) => {
          const share = r.payments / total;
          const dim = active !== null && active !== r.category;
          return (
            <button
              key={r.category}
              className="seg"
              data-dim={dim}
              style={{ flexBasis: `${share * 100}%`, flexGrow: 0, background: colorFor(r.category) }}
              onClick={() => onPick(active === r.category ? null : r.category)}
              aria-pressed={active === r.category}
              aria-label={`${r.category}: ${pct(share)} of payments`}
              title={`${r.category}: ${n0(r.payments)} payments (${pct(share, 1)})`}
            >
              {share > 0.09 && (
                <span className="in">
                  <b>{pct(share)}</b>
                  {r.category}
                </span>
              )}
            </button>
          );
        })}
      </div>
      <div className="legend">
        {sorted.map((r) => (
          <button key={r.category} className={active === r.category ? "on" : ""}
            onClick={() => onPick(active === r.category ? null : r.category)}>
            <i style={{ background: colorFor(r.category) }} />
            {r.category} <span className="num">{pct(r.payments / total, 1)}</span>
          </button>
        ))}
        {active && <button onClick={() => onPick(null)}>Show all</button>}
      </div>
    </div>
  );
}

/* ---------- Payee table ---------- */
export function PayeeTable({ rows, active, limit = 15 }: { rows: PayeeRow[]; active: string | null; limit?: number }) {
  const [all, setAll] = useState(false);
  const shown = rows.filter((r) => !active || r.category === active).slice(0, all ? 50 : limit);
  const max = Math.max(...rows.map((r) => r.share), 0.0001);
  return (
    <div className="tbl-wrap">
      <table className="tbl">
        <thead>
          <tr>
            <th className="l">Payee</th>
            <th className="l">Share of payments</th>
            <th>Payments</th>
            <th>Paying wallets</th>
            <th>Per wallet</th>
            <th>Typical price</th>
            <th>Volume</th>
          </tr>
        </thead>
        <tbody>
          {shown.map((r) => (
            <tr key={r.payee}>
              <td className="l">
                <span className="sw" style={{ background: colorFor(r.category) }} />
                <span className="name">{r.name ?? (r.category === "Unlabeled" ? "Unidentified" : r.category.replace(/s$/, "").replace(/ services?$/, " service"))}</span>
                <div className="sub" title={r.note ?? r.domain ?? undefined}>
                  <a className="addr" href={`https://basescan.org/address/${r.payee}`} target="_blank" rel="noreferrer">{short(r.payee)}</a>
                  {r.note ? <> · {r.note}</> : r.domain ? <> · {r.domain}</> : null}
                </div>
              </td>
              <td className="l barcell">
                <div className="mini"><span style={{ width: `${(r.share / max) * 100}%` }} /></div>
                <div className="sub num">{pct(r.share, 1)}</div>
              </td>
              <td>{compact(r.payments)}</td>
              <td className={r.payers < 10 ? "flag" : ""}>{n0(r.payers)}</td>
              <td>{compact(r.per_payer)}</td>
              <td>{usd(r.median_usd)}</td>
              <td>{usd(r.usd)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {rows.filter((r) => !active || r.category === active).length > limit && (
        <p className="ui" style={{ fontSize: 14, margin: "12px 0 0" }}>
          <button className="linkbtn" onClick={() => setAll(!all)}>{all ? "Show top 15" : "Show top 50"}</button>
        </p>
      )}
    </div>
  );
}

/* ---------- Horizontal bars (prices, facilitators, payer buckets) ---------- */
export function HBars({
  rows, value, label, fmt = (v: number) => pct(v, 1), color = "var(--base)", sub,
}: {
  rows: any[]; value: (r: any) => number; label: (r: any) => string;
  fmt?: (v: number) => string; color?: string | ((r: any) => string); sub?: (r: any) => string;
}) {
  const max = Math.max(...rows.map(value), 1e-9);
  return (
    <div className="hbars ui">
      {rows.map((r, i) => (
        <div className="hb" key={i}>
          <div className="hb-l">{label(r)}</div>
          <div className="hb-t">
            <span style={{ width: `${(value(r) / max) * 100}%`, background: typeof color === "function" ? color(r) : color }} />
          </div>
          <div className="hb-v num">{fmt(value(r))}{sub && <span className="sub"> {sub(r)}</span>}</div>
        </div>
      ))}
    </div>
  );
}

/* ---------- Hour-of-week cadence ---------- */
export function Cadence({ rows, start }: { rows: HourRow[]; start: string }) {
  const W = 960, H = 180, pad = { l: 44, r: 8, t: 10, b: 26 };
  const max = Math.max(...rows.map((r) => r.payments), 1);
  const x = (h: number) => pad.l + (h / 167) * (W - pad.l - pad.r);
  const y = (v: number) => H - pad.b - (v / max) * (H - pad.t - pad.b);
  const path = rows.map((r, i) => `${i ? "L" : "M"}${x(r.h).toFixed(1)},${y(r.payments).toFixed(1)}`).join("");
  const area = `${path}L${x(167)},${H - pad.b}L${x(0)},${H - pad.b}Z`;
  const d0 = new Date(start + "T00:00:00Z");
  return (
    <svg className="chart" viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label="Payments per hour across the week">
      {[0, 0.5, 1].map((f) => (
        <g key={f}>
          <line className="grid" x1={pad.l} x2={W - pad.r} y1={y(max * f)} y2={y(max * f)} />
          <text x={pad.l - 8} y={y(max * f) + 4} textAnchor="end">{compact(max * f)}</text>
        </g>
      ))}
      {Array.from({ length: 7 }, (_, d) => {
        const day = new Date(d0.getTime() + d * 86400e3);
        return (
          <g key={d}>
            <line className="grid" x1={x(d * 24)} x2={x(d * 24)} y1={pad.t} y2={H - pad.b} />
            <text x={x(d * 24) + 4} y={H - 8}>{day.toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric", timeZone: "UTC" })}</text>
          </g>
        );
      })}
      <path d={area} fill="var(--base-soft)" opacity={0.7} />
      <path d={path} fill="none" stroke="var(--base)" strokeWidth={1.5} />
    </svg>
  );
}

/* ---------- Scale check: weekly pace, ours vs Chainalysis ---------- */
export function ScaleCheck({ rows }: { rows: { label: string; ours: number; theirs: number | null }[] }) {
  const max = Math.max(...rows.flatMap((r) => [r.ours, r.theirs ?? 0]));
  return (
    <div className="scale ui">
      {rows.map((r) => (
        <div key={r.label} className="sc-row">
          <div className="sc-l">{r.label}</div>
          <div className="sc-bars">
            <div className="sc-b"><span style={{ width: `${(r.ours / max) * 100}%`, background: "var(--base)" }} /><em className="num">{compact(r.ours)}</em></div>
            {r.theirs !== null && (
              <div className="sc-b"><span style={{ width: `${(r.theirs / max) * 100}%`, background: "var(--ink-3)" }} /><em className="num">{compact(r.theirs)}</em></div>
            )}
          </div>
        </div>
      ))}
      <div className="legend-s"><i style={{ background: "var(--base)" }} />EIP-3009 USDC payments we counted, one week<i style={{ background: "var(--ink-3)" }} />Chainalysis quarterly increase ÷ 13</div>
    </div>
  );
}
