"""EIP-3009 USDC payments on Base for a time slice -> Parquet chunks.

Each payment = AuthorizationUsed(authorizer, nonce) + the Transfer at logIndex+1
(USDC's transferWithAuthorization emits them back to back). Transfers are pulled
only for the authorizers seen in the chunk, so we never touch the ~85 USDC
transfers/block that aren't EIP-3009.

Resumable: one parquet per block chunk; existing chunks are skipped.
  python fetch_payments.py --slice q3 --start 2026-08-10 --days 7
"""
import argparse, time, datetime as dt
import pandas as pd
from concurrent.futures import ThreadPoolExecutor
from common import RPC, RAW, AUTH_USED, TRANSFER, block_at, ts_of

CHUNK = 2000


def fetch_chunk(rpc, lo, hi):
    au = rpc.logs([AUTH_USED], lo, hi)
    payers = sorted({l["topics"][1] for l in au})
    tr = []
    for i in range(0, len(payers), 500):
        tr += rpc.logs([TRANSFER, payers[i:i + 500]], lo, hi)
    by_key = {(l["transactionHash"], int(l["logIndex"], 16)): l for l in tr}
    rows, unpaired = [], 0
    for l in au:
        li = int(l["logIndex"], 16)
        t = by_key.get((l["transactionHash"], li + 1))
        if not t or t["topics"][1] != l["topics"][1]:
            unpaired += 1
            continue
        b = int(l["blockNumber"], 16)
        rows.append({
            "block": b, "ts": ts_of(b), "tx_hash": l["transactionHash"], "log_index": li,
            "tx_index": int(l["transactionIndex"], 16),
            "payer": "0x" + l["topics"][1][-40:], "payee": "0x" + t["topics"][2][-40:],
            "amount_raw": int(t["data"], 16), "nonce": l["topics"][2],
        })
    return rows, len(au), unpaired


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--slice", required=True)
    ap.add_argument("--start", required=True, help="YYYY-MM-DD (UTC)")
    ap.add_argument("--days", type=float, default=7)
    ap.add_argument("--workers", type=int, default=3)
    a = ap.parse_args()

    t0 = dt.datetime.fromisoformat(a.start).replace(tzinfo=dt.timezone.utc).timestamp()
    lo, hi = block_at(t0), block_at(t0 + a.days * 86400) - 1
    out = RAW / "payments" / a.slice
    out.mkdir(parents=True, exist_ok=True)
    chunks = [(s, min(s + CHUNK - 1, hi)) for s in range(lo, hi + 1, CHUNK)]
    todo = [c for c in chunks if not (out / f"{c[0]}_{c[1]}.parquet").exists()]
    print(f"[{a.slice}] blocks {lo:,}..{hi:,}  {len(chunks)} chunks, {len(todo)} to do", flush=True)

    rpc = RPC()
    done, tot, unp, start = 0, 0, 0, time.time()

    def work(c):
        rows, n, u = fetch_chunk(rpc, *c)
        df = pd.DataFrame(rows)
        if not df.empty:
            df["amount_raw"] = df["amount_raw"].astype(str)   # uint256 can exceed int64
        df.to_parquet(out / f"{c[0]}_{c[1]}.parquet", index=False)
        return n, u

    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        for n, u in ex.map(work, todo):
            done += 1; tot += n; unp += u
            if done % 10 == 0 or done == len(todo):
                el = time.time() - start
                print(f"  [{a.slice}] {done}/{len(todo)} chunks  {tot:,} auths  {unp} unpaired  "
                      f"{el/60:.1f}m elapsed, ~{el/done*(len(todo)-done)/60:.1f}m left", flush=True)
    print(f"[{a.slice}] done")


if __name__ == "__main__":
    main()
