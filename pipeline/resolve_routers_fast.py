"""Faster router check: read ~15 sample receipts per payee instead of a week of outflow logs.

A payee is a pass-through router if, inside the payment's own transaction, it sends USDC
on to another address. Results append to config/routers.parquet (same columns as
resolve_routers.py).
  python resolve_routers_fast.py --top 120
"""
import argparse, json, collections
import duckdb, pandas as pd
from common import RPC, ROOT, TRANSFER, USDC

DB = ROOT / "data" / "x402.duckdb"
OUT = ROOT / "config" / "routers.parquet"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=120)
    ap.add_argument("--n", type=int, default=15)
    a = ap.parse_args()
    data = json.load(open(ROOT / "web" / "public" / "data" / "x402.json"))
    un = collections.Counter()
    for s in data["bySlice"].values():
        for r in s["payees"]:
            if not r["name"]: un[r["payee"]] += r["payments"]
    have = pd.read_parquet(OUT) if OUT.exists() else pd.DataFrame(columns=["payee"])
    cands = [p for p, _ in un.most_common() if p not in set(have.payee)][:a.top]
    con = duckdb.connect(str(DB), read_only=True)
    rpc, rows = RPC("https://mainnet.base.org"), []
    print(f"{len(cands)} payees", flush=True)
    for payee in cands:
        txs = [r[0] for r in con.execute(
            f"select tx_hash from payments where payee = ? using sample reservoir({a.n} rows) repeatable (1)", [payee]).fetchall()]
        fwd, hops = 0, collections.Counter()
        for h in txs:
            rc = rpc.call("eth_getTransactionReceipt", [h])
            outs = [l for l in rc["logs"] if l["address"].lower() == USDC and l["topics"][0] == TRANSFER
                    and l["topics"][1][-40:] == payee[2:]]
            if outs:
                fwd += 1
                for l in outs: hops["0x" + l["topics"][2][-40:]] += int(l["data"], 16)
        tot = sum(hops.values())
        nh = hops.most_common(1)[0][0] if hops else None
        rows.append({"payee": payee, "week": "sample", "payments": len(txs), "forwarded_share": fwd / max(len(txs), 1),
                     "next_hop": nh, "next_hop_share": hops[nh] / tot if nh else None, "kept_share": None,
                     "hops": json.dumps([[k, v / 1e6] for k, v in hops.most_common(5)])})
        if fwd / max(len(txs), 1) > 0.5: print(f"  ROUTER {payee} fwd={fwd}/{len(txs)} next={nh}", flush=True)
    con.close()
    pd.concat([have, pd.DataFrame(rows)], ignore_index=True).to_parquet(OUT, index=False)
    print(f"-> {OUT}: {sum(1 for r in rows if r['forwarded_share'] > 0.5)} routers of {len(rows)}")


if __name__ == "__main__":
    main()
