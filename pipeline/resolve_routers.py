"""Find routers and fee proxies: payees that pass the payment on inside the same transaction.

Some x402 payments go payer -> router -> service in one tx (FluxA routing, Meridian's 1% fee
proxy). The first hop is what AuthorizationUsed+Transfer pairing reports as the payee; the
service is the next hop. For each candidate payee we pull USDC Transfers *from* it during its
busiest sample week and join on tx_hash with its incoming payments.
  python resolve_routers.py --top 80
Output: config/routers.parquet  (payee, forwarded_share, next_hop, next_hop_share)
"""
import argparse, json
import duckdb, pandas as pd
import datetime as dt
from common import RPC, ROOT, TRANSFER, block_at

DB = ROOT / "data" / "x402.duckdb"
OUT = ROOT / "config" / "routers.parquet"
SLICES = {"q1": "2026-02-09", "q2": "2026-05-11", "q3": "2026-08-10", "recent": "2026-10-07"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=80)
    ap.add_argument("--payees", nargs="*", help="extra payees to check (e.g. known proxies)")
    a = ap.parse_args()
    con = duckdb.connect(str(DB), read_only=True)
    data = json.load(open(ROOT / "web" / "public" / "data" / "x402.json"))
    un = {}
    for s in data["bySlice"].values():
        for r in s["payees"]:
            if not r["name"]: un[r["payee"]] = un.get(r["payee"], 0) + r["payments"]
    cands = [p for p, _ in sorted(un.items(), key=lambda kv: -kv[1])][:a.top] + (a.payees or [])
    have = pd.read_parquet(OUT) if OUT.exists() else pd.DataFrame(columns=["payee"])
    cands = [c for c in dict.fromkeys(cands) if c not in set(have.payee)]
    print(f"{len(cands)} payees to check", flush=True)

    rpc, rows = RPC(), []
    for payee in cands:
        busiest = con.sql(f"select slice from payments where payee = '{payee}' group by 1 order by count(*) desc limit 1").fetchone()[0]
        t0 = dt.datetime.fromisoformat(SLICES[busiest]).replace(tzinfo=dt.timezone.utc).timestamp()
        lo, hi = block_at(t0), block_at(t0 + 7 * 86400) - 1
        topic = "0x" + "0" * 24 + payee[2:]
        out = []
        for step in range(lo, hi + 1, 10_000):
            for l in rpc.logs([TRANSFER, topic], step, min(step + 9_999, hi)):
                out.append({"tx_hash": l["transactionHash"], "to": "0x" + l["topics"][2][-40:], "usd": int(l["data"], 16) / 1e6})
        inc = con.sql(f"select tx_hash, amount_usd from payments where payee = '{payee}' and slice = '{busiest}'").df()
        o = pd.DataFrame(out, columns=["tx_hash", "to", "usd"])
        same = o[o.tx_hash.isin(set(inc.tx_hash))]
        fwd_share = same.tx_hash.nunique() / max(len(inc), 1)
        hops = same.groupby("to").usd.sum().sort_values(ascending=False)
        nh = hops.index[0] if len(hops) else None
        rows.append({"payee": payee, "week": busiest, "payments": len(inc), "forwarded_share": round(fwd_share, 4),
                     "next_hop": nh, "next_hop_share": round(float(hops.iloc[0] / hops.sum()), 4) if len(hops) else None,
                     "kept_share": round(1 - same.usd.sum() / max(inc.amount_usd.sum(), 1e-9), 4) if len(same) else None,
                     "hops": json.dumps([[k, round(v, 2)] for k, v in hops.head(5).items()])})
        flag = "ROUTER" if fwd_share > 0.5 else ""
        print(f"  {payee} {busiest} fwd={fwd_share:.0%} next={nh} {flag}", flush=True)
        pd.concat([have, pd.DataFrame(rows)], ignore_index=True).to_parquet(OUT, index=False)
    print(f"-> {OUT}")


if __name__ == "__main__":
    main()
