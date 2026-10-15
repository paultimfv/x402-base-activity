"""x402scan origin lookup: payTo address -> service origin (domain, title, description).

x402scan indexes x402 services beyond the Coinbase registry. Its site's public tRPC
route `public.origins.list.origins` takes a payTo address. We look up the busiest
payees that the Coinbase registry and manual labels don't name.
  python fetch_x402scan.py --top 300
"""
import argparse, json, time, requests
import duckdb, pandas as pd
from common import ROOT

API = "https://www.x402scan.com/api/trpc/public.origins.list.origins"
DB = ROOT / "data" / "x402.duckdb"
OUT = ROOT / "config" / "x402scan_origins.parquet"


def lookup(addr):
    inp = json.dumps({"json": {"chain": "base", "address": addr}})
    for i in range(5):
        try:
            r = requests.get(API, params={"input": inp}, timeout=60)
            if r.status_code == 429: raise RuntimeError("429")
            d = r.json()
            return d["result"]["data"]["json"] or []
        except Exception:
            time.sleep(3 * (i + 1))
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=300)
    a = ap.parse_args()
    con = duckdb.connect(str(DB), read_only=True)
    todo = con.sql(f"""
        select p.payee, count(*) n from payments p
        left join registry_payee r using (payee) left join labels l using (payee)
        where r.payee is null and l.payee is null
        group by 1 order by n desc limit {a.top}""").df()
    have = pd.read_parquet(OUT) if OUT.exists() else pd.DataFrame(columns=["payee"])
    todo = todo[~todo.payee.isin(set(have.payee))]
    print(f"{len(todo)} payees to look up", flush=True)
    rows = []
    for k, payee in enumerate(todo.payee, 1):
        res = lookup(payee)
        if res is None:
            print(f"  {payee} lookup failed", flush=True); continue
        o = res[0] if res else {}
        rows.append({"payee": payee, "n_origins": len(res), "origin": o.get("origin"),
                     "title": (o.get("title") or "")[:120], "description": (o.get("description") or "")[:300],
                     "all_origins": json.dumps([x.get("origin") for x in res][:10])})
        if res: print(f"  {payee} -> {o.get('origin')} | {o.get('title')}", flush=True)
        if k % 25 == 0:
            pd.concat([have, pd.DataFrame(rows)], ignore_index=True).to_parquet(OUT, index=False)
            print(f"  {k}/{len(todo)} done", flush=True)
        time.sleep(1.0)
    df = pd.concat([have, pd.DataFrame(rows)], ignore_index=True)
    df.to_parquet(OUT, index=False)
    print(f"-> {OUT}: {int((df.n_origins > 0).sum())} of {len(df)} payees matched")


if __name__ == "__main__":
    main()
