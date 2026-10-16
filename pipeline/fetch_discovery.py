"""x402 discovery endpoints from every facilitator that publishes one -> Base payTo labels.

The x402 spec has facilitators expose GET {facilitator}/discovery/resources, paginated with
limit/offset. Coinbase's is fetched by fetch_registry.py; this covers the others listed in
the x402scan facilitator package.
  python fetch_discovery.py
"""
import json, time, requests
from urllib.parse import urlparse
import pandas as pd
from common import ROOT

FACILITATORS = {
    "PayAI": "https://facilitator.payai.network",
    "Dexter": "https://facilitator.dexter.cash",
    "FluxA": "https://facilitator.fluxapay.xyz",
    "Questflow": "https://facilitator.questflow.ai",
    "AurraCloud": "https://x402-facilitator.aurracloud.com",
    "AnySpend": "https://mainnet.anyspend.com/x402",
    "Bitrefill": "https://api.bitrefill.com/x402",
    "three.ws": "https://three.ws/api/x402-facilitator",
    "Relai": "https://facilitator.x402.fi",
    "UltravioletaDAO": "https://facilitator.ultravioletadao.xyz",
}
BASE_NETS = {"eip155:8453", "base"}
OUT = ROOT / "config" / "discovery_payto.parquet"


NO_TYPE = {"https://facilitator.ultravioletadao.xyz"}   # x402 v2 endpoints reject the type filter


def pages(base):
    off, n = 0, 0
    while True:
        params = {"limit": 100, "offset": off}
        if base not in NO_TYPE: params["type"] = "http"
        try:
            r = requests.get(f"{base}/discovery/resources", params=params, timeout=40)
        except Exception as e:
            print(f"    error {str(e)[:80]}"); return
        if r.status_code == 429:
            time.sleep(5); continue
        if not r.ok:
            print(f"    HTTP {r.status_code}"); return
        try:
            d = r.json()
        except Exception:
            print("    not JSON"); return
        if isinstance(d.get("data"), dict): d = d["data"]          # AnySpend wraps the payload
        items = d.get("items") or d.get("resources") or []
        yield from items
        n += len(items)
        total = (d.get("pagination") or {}).get("total")
        if not items or (total is not None and off + 100 >= total) or len(items) < 100:
            return
        off += 100
        time.sleep(0.4)


def main():
    rows = []
    for name, url in FACILITATORS.items():
        k = 0
        for it in pages(url):
            k += 1
            res = it.get("resource") or it.get("url") or ""          # v1 "resource", v2 "url"
            if isinstance(res, dict): res = res.get("url", "")
            for acc in it.get("accepts") or []:
                if acc.get("network") not in BASE_NETS or not acc.get("payTo"): continue
                rows.append({"payto": acc["payTo"].lower(), "domain": urlparse(res).hostname or "", "resource": res,
                             "description": (acc.get("description") or it.get("description") or "")[:200],
                             "source": name})
        print(f"  {name:16} {k:>6} resources", flush=True)
    df = pd.DataFrame(rows).drop_duplicates(["payto", "resource"])
    df.to_parquet(OUT, index=False)
    print(f"-> {OUT}: {len(df):,} Base options, {df.payto.nunique() if len(df) else 0:,} payTo wallets")


if __name__ == "__main__":
    main()
