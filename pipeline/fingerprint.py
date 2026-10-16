"""Price + payer fingerprint: match unnamed payees to named services.

For each unnamed payee among the busiest, compare
  - its exact payment amounts with prices listed for registry resources (Coinbase + facilitator discovery)
  - its paying wallets with the paying wallets of every named payee (Jaccard overlap)
A match needs both: a shared listed price and a strong payer overlap with a payee whose
domain lists that price. Output is a review table; nothing is labeled automatically.
  python fingerprint.py --top 60
"""
import argparse, json
import duckdb, pandas as pd
from common import ROOT

DB = ROOT / "data" / "x402.duckdb"
OUT = ROOT / "config" / "fingerprint_matches.csv"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=60)
    a = ap.parse_args()
    con = duckdb.connect(str(DB), read_only=True)
    data = json.load(open(ROOT / "web" / "public" / "data" / "x402.json"))
    named, un = {}, {}
    for s in data["bySlice"].values():
        for r in s["payees"]:
            (named if r["name"] else un).setdefault(r["payee"], r["name"])
    un = list(un)[:a.top]

    # listed prices per domain
    reg = pd.read_parquet(ROOT / "config" / "registry_payto.parquet")[["payto", "domain", "price_raw"]]
    disc_p = ROOT / "config" / "discovery_payto.parquet"
    if disc_p.exists():
        d = pd.read_parquet(disc_p)
        if "price_raw" in d: reg = pd.concat([reg, d[["payto", "domain", "price_raw"]]])
    reg = reg.dropna(subset=["price_raw"])
    reg["price_raw"] = pd.to_numeric(reg["price_raw"], errors="coerce")
    price_domains = reg.groupby("price_raw").domain.apply(lambda x: set(x)).to_dict()

    payers = con.sql("select payee, list(distinct payer) as ps from payments group by 1").df()
    ps = {r.payee: set(r.ps) for r in payers.itertuples()}
    rows = []
    for u in un:
        amounts = con.sql(f"select amount_raw::bigint as a, count(*) n from payments where payee = '{u}' group by 1 order by n desc limit 5").df()
        listed = {int(x): price_domains.get(int(x), set()) for x in amounts.a}
        mine = ps.get(u, set())
        best = []
        for p, nm in named.items():
            other = ps.get(p, set())
            if not other or not mine: continue
            inter = len(mine & other)
            if inter == 0: continue
            best.append((inter / len(mine | other), inter, p, nm))
        best.sort(reverse=True)
        top = best[0] if best else (0, 0, None, None)
        rows.append({"payee": u, "top_prices": ",".join(str(int(x)) for x in amounts.a),
                     "price_listed_by": "; ".join(sorted(set().union(*listed.values())))[:200] if listed else "",
                     "best_overlap": round(top[0], 3), "shared_payers": top[1], "payers": len(mine),
                     "overlap_with": top[3], "overlap_payee": top[2]})
    df = pd.DataFrame(rows).sort_values("best_overlap", ascending=False)
    df.to_csv(OUT, index=False)
    pd.set_option("display.width", 250); pd.set_option("display.max_colwidth", 50)
    print(df.head(30).to_string(index=False))


if __name__ == "__main__":
    main()
