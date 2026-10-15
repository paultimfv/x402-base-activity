"use client";
import { useState } from "react";
import type { Dataset, SliceId } from "@/lib/types";
import { CompositionBar, PayeeTable, HBars, Cadence } from "./charts";
import { SliceMix } from "./SliceMix";
import { n0, pct, usd } from "@/lib/fmt";
import { Sources } from "./Prose";
import { Spotlight } from "./Spotlight";
import { ThemeToggle } from "./ThemeToggle";

export default function Report({ data }: { data: Dataset }) {
  const [slice, setSlice] = useState<SliceId>("q3");
  const [cat, setCat] = useState<string | null>(null);
  const meta = data.slices.find((s) => s.id === slice)!;
  const d = data.bySlice[slice];
  const pick = (s: SliceId) => { setSlice(s); setCat(null); };
  const labels = Object.fromEntries(data.slices.map((x) => [x.id, x.label]));

  return (
    <main className="page">
      <header className="mast col">
        <h1>x402 payments on Base</h1>
        <p className="dek">USDC payments settled through x402 on Base, from four sample weeks of onchain data.</p>
      </header>

      <nav className="switch" aria-label="Sample week">
        <div className="inner wide">
          <span className="lbl">Week</span>
          {data.slices.map((s) => (
            <button key={s.id} aria-pressed={s.id === slice} onClick={() => pick(s.id)}>{s.label}</button>
          ))}
          <span className="range">{meta.start} to {meta.end} UTC</span>
          <ThemeToggle />
        </div>
      </nav>

      <section aria-label="Payments by category">
        <div className="comp wide" style={{ marginBottom: 0 }}>
          <div className="total">
            <strong className="num">{n0(meta.payments)}</strong> payments by payee category. Click a category to filter the table.
          </div>
        </div>
        <CompositionBar rows={d.categories} total={meta.payments} active={cat} onPick={setCat} />
        <div className="wide">
          <div className="stats">
            <div><div className="v">{n0(meta.payers)}</div><div className="k">paying wallets</div></div>
            <div><div className="v">{n0(meta.payees)}</div><div className="k">payees</div></div>
            <div><div className="v">{usd(meta.median_usd)}</div><div className="k">median payment</div></div>
            <div><div className="v">{meta.facilitator_share === null ? "n/a" : pct(meta.facilitator_share)}</div><div className="k">sent by a listed facilitator (sample)</div></div>
          </div>
        </div>
      </section>

      {d.spotlight && <Spotlight s={d.spotlight} meta={meta} labels={labels} />}

      <figure className="fig wide">
        <p className="figt">Top payees</p>
        <p className="figs">Ranked by number of payments. Payees with fewer than 10 paying wallets are shown in orange.</p>
        <PayeeTable rows={d.payees} active={cat} />
      </figure>

      <figure className="fig wide">
        <p className="figt">Payments by week</p>
        <p className="figs">Bars share one scale. Click a week to select it.</p>
        <SliceMix data={data} current={slice} onPick={pick} />
      </figure>

      <div className="wide twoup">
        <figure className="fig">
          <p className="figt">Payment size</p>
          <p className="figs">Share of payments by amount. Right: total USDC in each range.</p>
          <HBars rows={d.prices} value={(r) => r.payments / meta.payments} label={(r) => r.bucket} sub={(r) => usd(r.usd)} />
        </figure>
        <figure className="fig">
          <p className="figt">Payments per wallet</p>
          <p className="figs">Paying wallets grouped by payments made this week. Bar: share of all payments.</p>
          <HBars rows={d.payer_buckets} value={(r) => r.payments / meta.payments} label={(r) => r.bucket}
            sub={(r) => `${n0(r.payers)} wallets`} color="var(--ink-2)" />
        </figure>
      </div>

      <figure className="fig wide">
        <p className="figt">Payments per hour</p>
        <p className="figs">UTC.</p>
        <Cadence rows={d.hourly} start={meta.start} />
      </figure>

      <figure className="fig wide">
        <p className="figt">Facilitators</p>
        <p className="figs">Transaction sender, from a random sample of transactions.</p>
        <HBars rows={d.facilitators} value={(r) => r.share} label={(r) => r.name} />
      </figure>

      <Sources />

      <footer className="foot col">Data as of {data.generated}.</footer>
    </main>
  );
}
