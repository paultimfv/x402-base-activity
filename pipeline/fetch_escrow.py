"""Commerce Payments escrow events -> the real receiver behind auth-capture payments.

x402's auth-capture scheme (Coinbase Payments checkout) pays the token collector
0x0e3d...7757, which hands funds to the AuthCaptureEscrow 0xbdea...0cff. The escrow emits
PaymentAuthorized / PaymentCharged with the full PaymentInfo struct (operator, payer,
receiver, feeReceiver, ...). Pulling those logs per sample week maps every such payment
to its merchant.
  python fetch_escrow.py
"""
import datetime as dt
import pandas as pd
from eth_abi import decode
from common import RPC, RAW, block_at

ESCROW = "0xbdea0d1bcc5966192b070fdf62ab4ef5b4420cff"
SLICES = {"q1": "2026-02-09", "q2": "2026-05-11", "q3": "2026-08-10", "recent": "2026-10-07"}
INFO = ["address", "address", "address", "address", "uint120", "uint48", "uint48", "uint48",
        "uint16", "uint16", "address", "uint256"]
OUT = RAW / "escrow.parquet"


def main():
    rpc, rows = RPC(), []
    for s, start in SLICES.items():
        t0 = dt.datetime.fromisoformat(start).replace(tzinfo=dt.timezone.utc).timestamp()
        lo, hi = block_at(t0), block_at(t0 + 7 * 86400) - 1
        n = 0
        for step in range(lo, hi + 1, 5_000):
            for l in rpc.logs([], step, min(step + 4_999, hi), address=ESCROW):
                w = bytes.fromhex(l["data"][2:])
                if len(w) < 14 * 32:      # captured / voided / refunded events carry no PaymentInfo
                    continue
                info = decode(INFO, w[:12 * 32])
                rows.append({"slice": s, "tx_hash": l["transactionHash"], "topic0": l["topics"][0],
                             "operator": info[0].lower(), "payer": info[1].lower(), "receiver": info[2].lower(),
                             "max_amount_usd": info[4] / 1e6, "fee_receiver": info[10].lower(),
                             "max_fee_bps": info[9]})
                n += 1
        print(f"  {s}: {n:,} escrow payment events", flush=True)
    df = pd.DataFrame(rows)
    df.to_parquet(OUT, index=False)
    print(f"-> {OUT}: {len(df):,} rows, {df.receiver.nunique():,} receivers")
    print(df.groupby("receiver").size().sort_values(ascending=False).head(10))


if __name__ == "__main__":
    main()
