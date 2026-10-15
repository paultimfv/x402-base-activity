import type { Dataset } from "@/lib/types";
import { compact, n0, pct, usd } from "@/lib/fmt";

/* Narrative sections. Every number is read from the dataset; the framing is ours. */
export function Prose({ data, which }: { data: Dataset; which: "lede" | "growth" | "price" | "settle" | "method" }) {
  const S = Object.fromEntries(data.slices.map((s) => [s.id, s]));
  const B = data.bySlice as Record<string, Dataset["bySlice"]["q1"]>;
  const q1 = S.q1, q3 = S.q3, rec = S.recent;
  const top3 = B.q3?.payees[0];
  const cat = (sid: string, c: string) => B[sid]?.categories.find((x) => x.category === c);

  if (which === "lede" && q3 && top3) {
    const sp = B.q3.spotlight;
    const ai = cat("q3", "AI inference");
    const restPayers = q3.payers - 1;
    return (
      <section className="prose col">
        <h2>The short answer</h2>
        <p className="finding">
          Most of the recent growth is one wallet calling one AI gateway. In our Q3 sample week,{" "}
          {pct(top3.share)} of all payments went to {top3.name ?? "a single payee"}, and {pct(sp.payments / top3.payments, 1)} of
          those came from a single paying wallet: {n0(sp.payments)} payments in seven days, about{" "}
          {(sp.payments / (7 * 86400)).toFixed(1)} per second.
        </p>
        <p>
          The other {n0(restPayers)} paying wallets that week made {compact(q3.payments - sp.payments)} payments between them.
          That long tail is the more representative picture of x402 today: data and search APIs, AI tools, mint pages and
          test traffic, mostly at fractions of a cent.
        </p>
        <p>
          How we counted: x402 lets a server answer a request with HTTP 402 Payment Required, and a client pay it with a
          signed USDC authorization that a facilitator settles onchain. On Base every such payment is a USDC{" "}
          <code>transferWithAuthorization</code>, logged as an <code>AuthorizationUsed</code> event next to the{" "}
          <code>Transfer</code> it authorizes. We counted every one of those in four sample weeks.
          {ai && <> AI inference was {pct(ai.payments / q3.payments)} of the Q3 week by count.</>}
        </p>
      </section>
    );
  }

  if (which === "growth" && q1 && q3) {
    return (
      <section className="prose col">
        <h2>Where the growth came from</h2>
        <p>
          The Q1 week had {compact(q1.payments)} payments. The Q3 week had {compact(q3.payments)}, about{" "}
          {(q3.payments / q1.payments).toFixed(1)} times as many, while the number of paying wallets went from{" "}
          {n0(q1.payers)} to {n0(q3.payers)}. Volume grew much faster than the number of payers, so the growth came
          from a small set of very active clients, not from many new ones.
        </p>
        {S.q2 && B.q3?.spotlight && (
          <p>
            Take out the single busiest wallet and the Q3 week drops to {compact(q3.payments - B.q3.spotlight.payments)} payments,
            {q3.payments - B.q3.spotlight.payments < S.q2.payments ? " less than" : " compared with"} the {compact(S.q2.payments)} in the Q2 week.
            On this sample, the jump in the Chainalysis curve between Q2 and Q3 is mostly that one client.
          </p>
        )}
        {rec && (
          <p>
            The October week came in at {compact(rec.payments)} payments, {rec.payments < q3.payments ? "below" : "above"} the
            Q3 pace. One busy payee moves the whole curve, which is worth remembering when reading the cumulative chart.
          </p>
        )}
      </section>
    );
  }

  if (which === "price" && q3) {
    const tiny = B.q3.prices.filter((p) => /0\.001|Under/.test(p.bucket)).reduce((t, p) => t + p.payments, 0);
    const big = B.q3.prices.find((p) => p.bucket === "$10 and up");
    return (
      <section className="prose col">
        <h2>Tiny payments, and a lot of them</h2>
        <p>
          The median Q3 payment was {usd(q3.median_usd)}. {pct(tiny / q3.payments)} of payments were a tenth of a cent
          or less. These are per-call API prices, not purchases.
          {big && <> At the other end, payments of $10 or more were {pct(big.payments / q3.payments, 1)} of the count but{" "}
          {usd(big.usd)} of the volume. Those look like ordinary gasless USDC transfers that reuse the same signature method, which is why we read
          x402 activity by count, not dollar volume.</>}
        </p>
      </section>
    );
  }

  if (which === "settle" && q3) {
    return (
      <section className="prose col">
        <h2>Who settles it</h2>
        <p>
          Every x402 payment is submitted onchain by a facilitator, which pays the gas. Matching transaction senders
          against the published facilitator addresses tells us who settles the traffic, and how much of what we counted
          is x402 at all.
          {q3.facilitator_share !== null && <> In the Q3 sample, {pct(q3.facilitator_share)} of transactions came from a
          known facilitator.</>}
        </p>
      </section>
    );
  }

  if (which === "method") {
    return (
      <section className="prose col method">
        <h2 style={{ fontFamily: "var(--font-serif)" }}>Method and limits</h2>
        <h3>What we pulled</h3>
        <ul>
          <li>Every USDC <code>AuthorizationUsed</code> event on Base in four sample weeks (Feb 9, May 11, Aug 10, Oct 7, 2026), paired with the <code>Transfer</code> at the next log index. Every authorization paired, with no exceptions.</li>
          <li>A random 2 to 5% sample of those transactions in full, for the sender (facilitator) and the contract called.</li>
          <li>Labels from Coinbase&apos;s x402 discovery registry (payTo addresses), x402scan&apos;s open facilitator list, and our own reading of contracts and money flows.</li>
        </ul>
        <h3>How unnamed payees are grouped</h3>
        <ul>
          <li><strong>Likely non-x402 transfers:</strong> median payment of $1 or more, and most sampled transactions sent by an address that is not a known facilitator.</li>
          <li><strong>Mints &amp; drops:</strong> 500 or more paying wallets, averaging three payments or fewer each.</li>
          <li><strong>Unlisted per-call services:</strong> median payment under $0.05. Priced like an API, but not in the registry.</li>
          <li>Everything else stays <strong>Unlabeled</strong>.</li>
        </ul>
        <h3>What this is not</h3>
        <ul>
          <li>Not every EIP-3009 payment is x402. Gasless wallet transfers use the same call. The facilitator match is our filter, and it only covers listed facilitators.</li>
          <li>Four weeks are samples, not the full history. They are enough to describe the mix; they are not a replacement for a full backfill.</li>
          <li>Many payers per payee does not mean many people. Separating one operator running many agent wallets from wash activity is the next step: funding sources, sweep destinations and signing-client fingerprints.</li>
        </ul>
      </section>
    );
  }
  return null;
}
