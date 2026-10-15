"use client";
import { useState } from "react";
import type { Dataset, SliceId } from "@/lib/types";
import { colorFor } from "@/lib/types";
import { CompositionBar, PayeeTable, HBars, Cadence, ScaleCheck } from "./charts";
import { SliceMix } from "./SliceMix";
import { compact, n0, pct, usd } from "@/lib/fmt";
import { Prose } from "./Prose";
import { Spotlight } from "./Spotlight";

export default function Report({ data }: { data: Dataset }) {
  const [slice, setSlice] = useState<SliceId>("q3");
  const [cat, setCat] = useState<string | null>(null);
  const meta = data.slices.find((s) => s.id === slice)!;
  const d = data.bySlice[slice];
  const pick = (s: SliceId) => { setSlice(s); setCat(null); };

  const scaleRows = data.slices.map((s) => {
    const q = data.chainalysis.find((c) => c.quarter === s.label.split(" ")[0]);
    return { label: s.label, ours: s.payments, theirs: q ? q.increase / 13 : null };
  });

  return (
    <main className="page">
      <header className="mast col">
        <p className="kicker">An onchain research note on x402, October 2026</p>
        <h1>What x402 on Base is actually paying for</h1>
        <p className="dek">
          Chainalysis counts 138.5M x402 transactions on Base, up 65% in three quarters. We rebuilt the
          activity from raw Base logs, one sample week per quarter, and looked at who gets paid, for what,
          and by whom.
        </p>
      </header>

      <nav className="switch" aria-label="Sample week">
        <div className="inner wide">
          <span className="lbl">Sample week</span>
          {data.slices.map((s) => (
            <button key={s.id} aria-pressed={s.id === slice} onClick={() => pick(s.id)}>{s.label}</button>
          ))}
          <span className="range">{meta.start} to {meta.end}, UTC</span>
        </div>
      </nav>

      <section aria-label="Payments by category">
        <div className="comp wide" style={{ marginBottom: 0 }}>
          <div className="total">
            <strong className="num">{n0(meta.payments)}</strong> USDC authorization payments in the week of {meta.start}.
            Click a segment to filter the page.
          </div>
        </div>
        <CompositionBar rows={d.categories} total={meta.payments} active={cat} onPick={setCat} />
        <div className="wide">
          <div className="stats">
            <div><div className="v">{pct(meta.top1_share)}</div><div className="k">of payments went to one payee</div></div>
            <div><div className="v">{n0(meta.payers)}</div><div className="k">wallets paid</div></div>
            <div><div className="v">{usd(meta.median_usd)}</div><div className="k">median payment</div></div>
            <div><div className="v">{meta.facilitator_share === null ? "n/a" : pct(meta.facilitator_share)}</div><div className="k">settled by a known x402 facilitator (sampled)</div></div>
          </div>
        </div>
      </section>

      <Prose data={data} which="lede" />

      {d.spotlight && <Spotlight s={d.spotlight} meta={meta} labels={Object.fromEntries(data.slices.map((x) => [x.id, x.label]))} />}

      <figure className="fig wide">
        <p className="figno">Figure 1</p>
        <p className="figt">Who got paid{cat ? `: ${cat}` : ""}</p>
        <p className="figs">Top payees in the {meta.label} sample week. Wallets with fewer than ten payers are flagged in orange.</p>
        <PayeeTable rows={d.payees} active={cat} />
        <figcaption>Names come from Coinbase&apos;s x402 discovery registry (payTo address match) or our own review of the contract and its money flows. Unidentified means neither applies yet.</figcaption>
      </figure>

      <Prose data={data} which="growth" />

      <figure className="fig wide">
        <p className="figno">Figure 2</p>
        <p className="figt">The mix, week by week</p>
        <p className="figs">Each bar is one sample week, drawn to the same scale. Segments use the colors from the top of the page. Click a week to load it.</p>
        <SliceMix data={data} current={slice} onPick={pick} />
        <figcaption>Sample weeks start Feb 9, May 11, Aug 10 and Oct 7, 2026.</figcaption>
      </figure>

      <Prose data={data} which="price" />

      <div className="wide twoup">
        <figure className="fig">
          <p className="figno">Figure 3</p>
          <p className="figt">What a payment costs</p>
          <p className="figs">Share of {meta.label} payments by size.</p>
          <HBars rows={d.prices} value={(r) => r.payments / meta.payments} label={(r) => r.bucket}
            sub={(r) => usd(r.usd)} />
          <figcaption>Right-hand figure is total USDC in each bucket.</figcaption>
        </figure>
        <figure className="fig">
          <p className="figno">Figure 4</p>
          <p className="figt">How hard each wallet pays</p>
          <p className="figs">Paying wallets grouped by how many payments they made that week, and their share of all payments.</p>
          <HBars rows={d.payer_buckets} value={(r) => r.payments / meta.payments} label={(r) => r.bucket}
            sub={(r) => `${n0(r.payers)} wallets`} color="var(--ink-2)" />
          <figcaption>A handful of wallets making thousands of calls each is what automated clients look like.</figcaption>
        </figure>
      </div>

      <figure className="fig wide">
        <p className="figno">Figure 5</p>
        <p className="figt">When it happens</p>
        <p className="figs">Payments per hour across the {meta.label} week. Human traffic follows the clock; scheduled agents mostly don&apos;t.</p>
        <Cadence rows={d.hourly} start={meta.start} />
      </figure>

      <Prose data={data} which="settle" />

      <div className="wide twoup">
        <figure className="fig">
          <p className="figno">Figure 6</p>
          <p className="figt">Who settles it</p>
          <p className="figs">Facilitator behind each payment, from a random sample of transactions.</p>
          <HBars rows={d.facilitators} value={(r) => r.share} label={(r) => r.name} />
          <figcaption>Facilitator addresses from the open-source x402scan registry. Not listed means the sender is not a known facilitator.</figcaption>
        </figure>
        <figure className="fig">
          <p className="figno">Figure 7</p>
          <p className="figt">Scale check against Chainalysis</p>
          <p className="figs">Our one-week count next to Chainalysis&apos;s average week for that quarter.</p>
          <ScaleCheck rows={scaleRows} />
        </figure>
      </div>

      <Prose data={data} which="method" />

      <footer className="foot col">
        Built from raw Base data: Infura and the public Base RPC for logs and transactions, Coinbase&apos;s x402 discovery
        registry and x402scan&apos;s facilitator list for labels. No third-party analytics tables.
        Data generated {data.generated}.
      </footer>
    </main>
  );
}
