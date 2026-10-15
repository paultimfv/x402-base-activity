const USDC = "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913";

/* Data sources and definitions. Descriptive only. */
export function Sources() {
  return (
    <section className="col method" aria-label="Data and method">
      <h2>Data</h2>
      <ul>
        <li>
          Payments: every <code>AuthorizationUsed</code> event on Base{" "}
          <a href={`https://basescan.org/token/${USDC}`} target="_blank" rel="noreferrer">USDC</a>, paired with the{" "}
          <code>Transfer</code> in the next log, for four weeks starting Feb 9, May 11, Aug 10 and Oct 7, 2026 (UTC).
          Pulled with <code>eth_getLogs</code> from a Base RPC node.
        </li>
        <li>Facilitators: a random 1–5% sample of those transactions, matched by sender against the{" "}
          <a href="https://github.com/Merit-Systems/x402scan/tree/main/packages/external/facilitators/src/facilitators" target="_blank" rel="noreferrer">x402scan facilitator list</a>.
        </li>
        <li>Payee names: <code>payTo</code> addresses in the{" "}
          <a href="https://api.cdp.coinbase.com/platform/v2/x402/discovery/resources" target="_blank" rel="noreferrer">Coinbase x402 discovery registry</a>, the{" "}
          <a href="https://www.x402scan.com" target="_blank" rel="noreferrer">x402scan</a> origin index, plus manual labels.
        </li>
        <li>Every address links to Basescan.</li>
      </ul>
      <h2>Categories for unnamed payees</h2>
      <ul>
        <li><strong>Likely non-x402 transfers:</strong> median payment $1 or more, mostly sent by addresses not on the facilitator list.</li>
        <li><strong>Mints &amp; drops:</strong> 500+ paying wallets, three or fewer payments each.</li>
        <li><strong>Unlisted per-call services:</strong> median payment under $0.05.</li>
        <li><strong>Unlabeled:</strong> everything else.</li>
      </ul>
    </section>
  );
}
