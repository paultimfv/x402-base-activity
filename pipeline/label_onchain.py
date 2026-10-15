"""Onchain profile of the top payees: what is this address and where does the money go?

For each top payee (by payment count, across all slices):
  - contract or EOA (eth_getCode), EIP-1967 implementation, ERC-20 name/symbol if any
  - USDC outflows during each slice: top destinations and share swept
Output: config/payee_profiles.parquet  (manual labels live in config/labels.csv)
  python label_onchain.py --top 60
"""
import argparse, json
import duckdb, pandas as pd
from eth_abi import decode as abi_decode
from common import RPC, RAW, ROOT, TRANSFER, block_at

IMPL_SLOT = "0x360894a13ba1a3210667c828492db98dca3e2076cc3735a9e9cbc7e8c3e0ae2a"
SLICES = {"q1": "2026-02-09", "q2": "2026-05-11", "q3": "2026-08-10", "recent": "2026-10-07"}


def erc20_meta(rpc, a):
    out = {}
    for fn, sel in (("name", "0x06fdde03"), ("symbol", "0x95d89b41")):
        try:
            raw = rpc.call("eth_call", [{"to": a, "data": sel}, "latest"])
            if raw and len(raw) > 2:
                out[fn] = abi_decode(["string"], bytes.fromhex(raw[2:]))[0][:60]
        except Exception:
            pass
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=60)
    a = ap.parse_args()

    con = duckdb.connect()
    top = con.sql(f"""
        select payee, count(*) n from read_parquet('{RAW}/payments/*/*.parquet')
        group by 1 order by n desc limit {a.top}""").df()
    busiest = con.sql(f"""
        select payee, arg_max(slice, n) as slice from (
          select payee, regexp_extract(filename, 'payments/([a-z0-9]+)/', 1) as slice, count(*) n
          from read_parquet('{RAW}/payments/*/*.parquet', filename = true) group by 1, 2)
        group by 1""").df().set_index("payee")["slice"].to_dict()
    rpc, rows = RPC(), []
    import datetime as dt
    for payee in top["payee"]:
        code = rpc.call("eth_getCode", [payee, "latest"])
        is_contract = len(code) > 2
        prof = {"payee": payee, "is_contract": is_contract, "code_size": (len(code) - 2) // 2}
        if is_contract:
            impl = rpc.call("eth_getStorageAt", [payee, IMPL_SLOT, "latest"])
            prof["impl"] = "0x" + impl[-40:] if int(impl, 16) else None
            prof.update(erc20_meta(rpc, payee))
        # USDC leaving this payee during each slice
        dests = {}
        topic = "0x" + "0" * 24 + payee[2:]
        for s, start in [(busiest[payee], SLICES[busiest[payee]])]:   # busiest week only
            t0 = dt.datetime.fromisoformat(start).replace(tzinfo=dt.timezone.utc).timestamp()
            lo, hi = block_at(t0), block_at(t0 + 7 * 86400) - 1
            for step in range(lo, hi + 1, 10_000):
                for l in rpc.logs([TRANSFER, topic], step, min(step + 9_999, hi)):
                    d = "0x" + l["topics"][2][-40:]
                    dests[d] = dests.get(d, 0) + int(l["data"], 16) / 1e6
        top_d = sorted(dests.items(), key=lambda kv: -kv[1])[:5]
        prof["out_week"] = busiest[payee]
        prof["out_usdc"] = round(sum(dests.values()), 2)
        prof["out_dests"] = json.dumps([[d, round(v, 2)] for d, v in top_d])
        rows.append(prof)
        print(f"  {payee} contract={is_contract} {prof.get('symbol') or ''} out=${prof['out_usdc']:,.0f}", flush=True)
    pd.DataFrame(rows).to_parquet(ROOT / "config" / "payee_profiles.parquet", index=False)


if __name__ == "__main__":
    main()
