"""x402scan bazaar sellers: every recipient address -> origin(s), paginated, in bulk.

`public.sellers.bazaar.list` (the route behind x402scan's seller pages) returns groups of
recipient addresses with the origins they serve. Paging through it gives the full
payTo -> service map without one lookup per address.
  python fetch_x402scan_bazaar.py
"""
import json, time, requests
import pandas as pd
from common import ROOT

API = "https://www.x402scan.com/api/trpc/public.sellers.bazaar.list"
OUT = ROOT / "config" / "x402scan_bazaar.parquet"


def page(n, size=100, timeframe=0):
    inp = json.dumps({"json": {"chain": "base", "timeframe": timeframe, "pagination": {"page": n, "page_size": size}}})
    for i in range(6):
        try:
            r = requests.get(API, params={"input": inp}, timeout=120)
            if r.status_code == 429: raise RuntimeError("429")
            return r.json()["result"]["data"]["json"]
        except Exception as e:
            time.sleep(4 * (i + 1))
    return None


def main():
    rows, n = [], 0
    while True:
        d = page(n)
        if d is None:
            print(f"  page {n} failed, stopping"); break
        for it in d["items"]:
            o = (it.get("origins") or [{}])[0]
            for rcp in it.get("recipients") or []:
                rows.append({"payee": rcp.lower(), "origin": o.get("origin"), "title": (o.get("title") or "")[:120],
                             "description": (o.get("description") or "")[:300], "n_origins": len(it.get("origins") or []),
                             "tx_count_365d": it.get("tx_count"), "facilitators": ",".join(it.get("facilitators") or [])})
        if n % 10 == 0:
            print(f"  page {n}/{d.get('total_pages')}  {len(rows):,} recipients", flush=True)
            pd.DataFrame(rows).to_parquet(OUT, index=False)
        if not d.get("hasNextPage"): break
        n += 1
        time.sleep(0.5)
    df = pd.DataFrame(rows).drop_duplicates("payee")
    df.to_parquet(OUT, index=False)
    print(f"-> {OUT}: {len(df):,} recipients, {df.origin.nunique():,} origins")


if __name__ == "__main__":
    main()
