# x402-activity

What x402 payments on Base are actually paying for, rebuilt from raw chain data.

Live: https://x402-activity.vercel.app

Chainalysis counts 138.5M cumulative x402 transactions on Base, up 65% from 2025-Q4 to 2026-Q3. This project asks the obvious next question: who is getting paid, for what, and by whom. No third-party analytics tables; everything comes from Base RPC calls, Coinbase's public x402 discovery registry, and the open-source x402scan facilitator list.

## Findings (four sample weeks: Feb 9, May 11, Aug 10, Oct 7, 2026)

- **One wallet calling one AI gateway drove the Q3 surge.** In the Aug 10 week, 73% of all 2.56M payments went to BlockRun (a pay-per-request LLM and search gateway), and 99.7% of those came from a single wallet: 1.86M payments in seven days, ~3 per second, $72k spent, at 55k distinct prices (consistent with per-token metering).
- **Without that wallet, Q3 is smaller than Q2**: 707k payments vs 794k.
- **Payments are tiny.** Q3 median $0.006; 72% of payments are a tenth of a cent or less.
- **Settlement is concentrated.** In the Q3 sample, 96% of transactions were sent by a known x402 facilitator, 91% by Coinbase.
- **The long tail** is data and search APIs (StableEnrich, twit.sh, Chainlink for Agents, ...), unlisted per-call services, one-shot mints, and test traffic.

## Pipeline

```
Infura (Base)            eth_getLogs: USDC AuthorizationUsed + matching Transfer      -> data/raw/payments/<week>/*.parquet
mainnet.base.org         eth_getTransactionByHash on a 1-5% hash-keyed sample          -> data/raw/txs/<week>.parquet
CDP discovery API        x402 resources and their payTo wallets                        -> config/registry_payto.parquet
x402scan (GitHub)        facilitator addresses on Base                                 -> config/facilitators.csv
Infura                   payee code, proxy slot, USDC outflows                          -> config/payee_profiles.parquet
                         hand labels                                                   -> config/labels.csv
build_db.py              parquet -> DuckDB (data/x402.duckdb)
export_json.py           DuckDB -> web/public/data/x402.json
web/                     Next.js static page on Vercel
```

How a payment is identified: USDC's `transferWithAuthorization` (EIP-3009) emits `AuthorizationUsed(authorizer, nonce)` immediately followed by `Transfer(from, to, value)`. Pairing the two at `logIndex` and `logIndex + 1` gives payer, payee and amount. Every authorization in all four weeks paired (0 unpaired). Transfers are fetched only for the authorizers seen in each chunk, which avoids pulling the ~85 other USDC transfers per Base block.

Not every EIP-3009 payment is x402 (gasless wallet transfers use the same call). The facilitator match on sampled transactions is the filter, and payees with large payments settled by unknown senders are grouped as "Likely non-x402 transfers".

## Run it

```bash
python3 -m venv .venv && .venv/bin/pip install web3 pandas pyarrow duckdb python-dotenv requests
# .env: INFURA_BASE_URL=https://base-mainnet.infura.io/v3/<key>
cd pipeline
../.venv/bin/python fetch_payments.py --slice q3 --start 2026-08-10 --days 7 --workers 2
../.venv/bin/python fetch_tx_sample.py --slice q3 --rate 0.01
../.venv/bin/python fetch_registry.py
../.venv/bin/python label_onchain.py --top 40
../.venv/bin/python build_db.py && ../.venv/bin/python export_json.py
cd ../web && npm install && npm run build
```

Every step is resumable: payment chunks are one parquet per 2,000 blocks, and the tx sampler saves every 2,000 rows.

## Next

Sybil and entity resolution on the payer side: cluster wallets by funding source, sweep destination, signing-client fingerprint (`validAfter`/`validBefore` windows in the calldata already collected) and timing, then test for circular payee-to-payer flows.
