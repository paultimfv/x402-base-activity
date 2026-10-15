"""Coinbase CDP x402 discovery registry -> payTo address labels (Base only).

The registry lists x402 resources with their accepted payment options; each
option names the network, asset, price and payTo wallet. That's the bridge from
an onchain payee address to a service (domain, endpoint, description).
"""
import json, time, requests, datetime as dt
from urllib.parse import urlparse
import pandas as pd
from common import ROOT

API = "https://api.cdp.coinbase.com/platform/v2/x402/discovery/resources"
BASE_NETS = {"eip155:8453", "base"}
OUT = ROOT / "config" / "registry_payto.parquet"
RAW = ROOT / "data" / "raw" / f"registry_{dt.date.today()}.json"


def page(offset, limit=1000):
    for i in range(4):
        try:
            r = requests.get(API, params={"type": "http", "limit": limit, "offset": offset},
                             headers={"accept": "application/json"}, timeout=40)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            if i == 3: raise
            time.sleep(1 + i)


def main():
    first = page(0)
    total = first.get("pagination", {}).get("total") or len(first["items"])
    items = list(first["items"])
    for off in range(1000, total, 1000):
        items += page(off)["items"]
        time.sleep(0.3)
    RAW.write_text(json.dumps(items))
    print(f"{len(items):,} resources (total {total:,})")

    rows = []
    for it in items:
        res = it.get("resource", "")
        meta = it.get("metadata") or {}
        for acc in it.get("accepts") or []:
            if acc.get("network") not in BASE_NETS or not acc.get("payTo"): continue
            rows.append({
                "payto": acc["payTo"].lower(), "domain": urlparse(res).hostname or "",
                "resource": res, "asset": (acc.get("asset") or "").lower(),
                "price_raw": acc.get("maxAmountRequired") or acc.get("amount"),
                "scheme": acc.get("scheme"), "description": (acc.get("description") or it.get("description") or "")[:200],
                "last_updated": it.get("lastUpdated"), "quality": json.dumps(meta)[:300] if meta else "",
            })
    df = pd.DataFrame(rows)
    df.to_parquet(OUT, index=False)
    print(f"{len(df):,} Base payment options, {df['payto'].nunique():,} payTo wallets, "
          f"{df['domain'].nunique():,} domains -> {OUT}")


if __name__ == "__main__":
    main()
