"""Full tx for a deterministic random sample of payment txs -> who settles them and how.

Logs don't carry tx.from (the facilitator / relayer) or tx.to (direct USDC call vs.
smart-account / ERC-4337 / settlement contract). A ~5% sample is plenty for shares.
Sampling keys off the tx hash itself, so it's random but reproducible.
  python fetch_tx_sample.py --slice q3 --rate 0.05
"""
import argparse, time
import pandas as pd
from common import RPC, RAW

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--slice", required=True)
    ap.add_argument("--rate", type=float, default=0.05)
    ap.add_argument("--batch", type=int, default=10)
    ap.add_argument("--url", default="https://mainnet.base.org", help="RPC for tx lookups (keeps Infura free for getLogs)")
    a = ap.parse_args()

    pay = pd.read_parquet(RAW / "payments" / a.slice, columns=["tx_hash"])
    hashes = sorted(set(pay["tx_hash"]))
    cut = int(a.rate * 0xFFFFFFFF)
    sample = [h for h in hashes if int(h[-8:], 16) < cut]
    out = RAW / "txs" / f"{a.slice}.parquet"
    out.parent.mkdir(parents=True, exist_ok=True)
    have = set(pd.read_parquet(out)["tx_hash"]) if out.exists() else set()
    todo = [h for h in sample if h not in have]
    print(f"[{a.slice}] {len(hashes):,} txs, sample {len(sample):,}, {len(todo):,} to fetch", flush=True)

    import os
    rpc = RPC(a.url)
    rows, t0, B = [], time.time(), a.batch

    def flush():
        df = pd.DataFrame(rows)
        if out.exists(): df = pd.concat([pd.read_parquet(out), df], ignore_index=True)
        df.drop_duplicates("tx_hash").to_parquet(out, index=False)
        rows.clear()
        return len(df)

    for i in range(0, len(todo), B):
        for tx in rpc.batch([("eth_getTransactionByHash", [h]) for h in todo[i:i + B]]):
            rows.append({"tx_hash": tx["hash"], "tx_from": tx["from"].lower(),
                         "tx_to": (tx.get("to") or "").lower(), "selector": tx["input"][:10],
                         "input": tx["input"], "gas_price": int(tx.get("gasPrice") or "0x0", 16),
                         "tx_type": tx.get("type")})
        if len(rows) >= 2000:
            n = flush()
            print(f"  [{a.slice}] {i + B:,}/{len(todo):,} ({time.time()-t0:.0f}s, {n:,} saved)", flush=True)
        time.sleep(0.25)
    n = flush()
    print(f"[{a.slice}] -> {out} ({n:,} rows)")

if __name__ == "__main__":
    main()
