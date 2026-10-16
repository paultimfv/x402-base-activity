"""Per-transaction next hop for known pass-through routers and fee proxies.

A proxy can forward to a different service in every transaction (Meridian keeps 1% and
passes the rest on), so the mapping has to be per tx: USDC Transfers *from* the router,
joined to payments on tx_hash. Largest outgoing transfer in the tx is the service.
  python fetch_router_hops.py
"""
import datetime as dt
import pandas as pd
from common import RPC, RAW, TRANSFER, block_at

ROUTERS = {
    "0x9c955c40dc98fce89a133f402ffbf94070e6e299": "FluxA router",
    "0x8e7769d440b3460b92159dd9c6d17302b036e2d6": "Meridian fee proxy",
}
SLICES = {"q1": "2026-02-09", "q2": "2026-05-11", "q3": "2026-08-10", "recent": "2026-10-07"}
OUT = RAW / "router_hops.parquet"


def main():
    rpc, rows = RPC(), []
    for router, label in ROUTERS.items():
        topic = "0x" + "0" * 24 + router[2:]
        for s, start in SLICES.items():
            t0 = dt.datetime.fromisoformat(start).replace(tzinfo=dt.timezone.utc).timestamp()
            lo, hi = block_at(t0), block_at(t0 + 7 * 86400) - 1
            n = 0
            for step in range(lo, hi + 1, 10_000):
                for l in rpc.logs([TRANSFER, topic], step, min(step + 9_999, hi)):
                    rows.append({"tx_hash": l["transactionHash"], "router": router, "router_label": label,
                                 "next_hop": "0x" + l["topics"][2][-40:], "usd": int(l["data"], 16) / 1e6})
                    n += 1
            print(f"  {label} {s}: {n:,} outgoing transfers", flush=True)
    df = pd.DataFrame(rows)
    # one hop per tx: the largest outgoing transfer (the service, not the fee)
    df = df.sort_values("usd", ascending=False).drop_duplicates(["tx_hash", "router"])
    df.to_parquet(OUT, index=False)
    print(f"-> {OUT}: {len(df):,} tx hops")
    print(df.groupby(["router_label", "next_hop"]).size().sort_values(ascending=False).head(12))


if __name__ == "__main__":
    main()
