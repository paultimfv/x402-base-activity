"""DuckDB -> web/public/data/x402.json (everything the dashboard renders)."""
import json, re, datetime as dt
import duckdb, pandas as pd
from common import ROOT

DB = ROOT / "data" / "x402.duckdb"
OUT = ROOT / "web" / "public" / "data" / "x402.json"
SLICES = [("q1", "Q1 2026", "2026-02-09"), ("q2", "Q2 2026", "2026-05-11"),
          ("q3", "Q3 2026", "2026-08-10"), ("recent", "Oct 2026", "2026-10-07")]
# Chainalysis chart: quarterly increase in cumulative x402 txs on Base
CHAINALYSIS = [("Q1", 13.7e6), ("Q2", 17.6e6), ("Q3", 23.3e6)]

# registry description -> category (manual labels.csv overrides)
RULES = [
    ("API gateways", r"gateway|marketplace|thousands of apis|unified api|api hub|all x402|pay per call in usdc"),
    ("Agent games", r"\bgame\b|territory|arena"),
    ("Infra & testing", r"health|probe|\btest|ping|heartbeat|status check"),
    ("AI inference", r"chat|completion|llm|inference|\bmodel|gpt|claude|image gen|generate (an )?image|agent verdict|ai-written|\bai\b"),
    ("Mints & drops", r"\bmint|nft|airdrop|launch a token|claim"),
    ("Content & paywalls", r"article|paywall|content|read the|premium|subscribe"),
    ("Data & search APIs", r"search|enrich|data|price|balance|api|scrape|tweet|news|lookup|signal|markdown|crawl|weather|onchain"),
]


def categorize(desc):
    d = (desc or "").lower()
    for cat, pat in RULES:
        if re.search(pat, d): return cat
    return None


def main():
    con = duckdb.connect(str(DB), read_only=True)
    q = lambda s: con.sql(s).df()
    has_tx = con.sql("select count(*) from information_schema.tables where table_name='tx_sample'").fetchone()[0] > 0

    reg = q("select payee, top_domain, domains, sample_description from registry_payee")
    reg["auto_cat"] = reg["sample_description"].map(categorize)
    # x402scan origins for payees the Coinbase registry doesn't list
    xs_path = ROOT / "config" / "x402scan_origins.parquet"
    bz_path = ROOT / "config" / "x402scan_bazaar.parquet"
    if xs_path.exists() or bz_path.exists():
        parts = [pd.read_parquet(x)[["payee", "n_origins", "origin", "title", "description"]] for x in (xs_path, bz_path) if x.exists()]
        xs = pd.concat(parts, ignore_index=True).dropna(subset=["origin"]).drop_duplicates("payee")
        xs = xs[xs.n_origins > 0].copy()
        xs["top_domain"] = xs["origin"].str.replace(r"^https?://", "", regex=True).str.rstrip("/")
        xs["sample_description"] = (xs["title"].fillna("") + " " + xs["description"].fillna("")).str.strip()
        xs["auto_cat"] = xs["sample_description"].map(categorize)
        xs["domains"] = xs["top_domain"]
        xs = xs[~xs.payee.isin(set(reg.payee))][["payee", "top_domain", "domains", "sample_description", "auto_cat"]]
        reg = pd.concat([reg, xs], ignore_index=True)
    # discovery endpoints of other facilitators (PayAI, Dexter, three.ws, ...)
    dp = ROOT / "config" / "discovery_payto.parquet"
    if dp.exists():
        ds = pd.read_parquet(dp)
        ds = ds[~ds.payto.isin(set(reg.payee))]
        if len(ds):
            g = ds.groupby("payto").agg(top_domain=("domain", lambda x: x.mode().iloc[0]),
                                        domains=("domain", lambda x: ", ".join(sorted(set(x)))[:200]),
                                        sample_description=("description", "first")).reset_index().rename(columns={"payto": "payee"})
            g["auto_cat"] = g["sample_description"].map(categorize)
            reg = pd.concat([reg, g], ignore_index=True)
    labels = q("select * from labels")
    fac = pd.read_csv(ROOT / "config" / "facilitators.csv")

    payee_fac = pd.DataFrame(columns=["payee", "facilitator"])
    if has_tx:
        con.register("fac", fac)
        payee_fac = q("""
            select p.payee, mode(coalesce(f.facilitator, 'Not listed')) as facilitator,
                   avg((f.address is not null)::int) as fac_share, count(*) as sampled
            from tx_sample t join payments p using (tx_hash) left join fac f on f.address = t.tx_from
            group by 1""")

    info = reg.merge(labels, on="payee", how="outer").merge(payee_fac, on="payee", how="outer")
    info["category_final"] = info["category"].fillna(info["auto_cat"]).fillna("Unlabeled")
    td = info["top_domain"].where(info["top_domain"].fillna("").str.len() > 0)
    info["name_final"] = info["name"].where(info["name"].fillna("").str.len() > 0).fillna(td)
    con_info = duckdb.connect()
    if "fac_share" not in info: info["fac_share"] = None
    con_info.register("info", info[["payee", "category_final", "name_final", "top_domain", "notes", "facilitator", "fac_share"]]
                      .rename(columns={"category_final": "category", "name_final": "name", "top_domain": "domain"}))

    out = {"generated": dt.date.today().isoformat(),
           "chainalysis": [{"quarter": k, "increase": v} for k, v in CHAINALYSIS],
           "slices": [], "bySlice": {}, "notes": {}}

    for sid, label, start in SLICES:
        p = q(f"select payee, payer, amount_usd, block_time, via from payments where slice = '{sid}'")
        if p.empty: continue
        con_info.register("p", p)
        pp = con_info.sql("""
            select p.payee, count(*) as n, count(distinct payer) as payers, median(amount_usd) as med, sum(amount_usd) as usd,
                   any_value(i.name) as name, coalesce(any_value(i.category), 'Unlabeled') as category,
                   any_value(i.domain) as domain, any_value(i.notes) as notes, any_value(i.facilitator) as facilitator,
                   bool_or(i.domain is not null) as in_reg, any_value(i.fac_share) as fac_share,
                   mode(p.via) as via
            from p left join info i using (payee) group by 1 order by n desc""").df()
        total = len(p)
        # behavioral categories for payees nobody has named (rules shown on the page)
        def behave(r):
            if r.category != "Unlabeled": return r.category
            nm = r["name"]                     # r.name would be the row's index label, not the column
            if isinstance(nm, str) and nm: return "Other x402 services"   # named in a registry, no keyword match
            via = r.via if isinstance(r.via, str) else ""
            if via == "auth-capture escrow": return "Coinbase checkout merchants (unnamed)"
            if via == "FluxA router": return "Routed via FluxA (service unnamed)"
            if via == "Meridian fee proxy": return "Routed via Meridian (service unnamed)"
            fs = r.fac_share if pd.notna(r.fac_share) else None
            if r.med >= 1 and fs is not None and fs < 0.5: return "Likely non-x402 transfers"
            if r.n / r.payers <= 3 and r.payers >= 500: return "Mints & drops"
            if r.payers <= 3: return "Single-client traffic"
            if r.med < 0.05: return "Unlisted per-call services"
            return "Unlabeled"
        pp["category"] = pp.apply(behave, axis=1)
        dbg = ROOT / "data" / f"payee_categories_{sid}.parquet"
        pp[["payee", "n", "payers", "med", "name", "category", "via", "fac_share"]].to_parquet(dbg, index=False)
        cats = pp.groupby("category").agg(payments=("n", "sum"), usd=("usd", "sum"), payees=("payee", "count")).reset_index()
        con_info.register("pcat", pp[["payee", "category"]])
        cat_payers = con_info.sql("""select c.category, count(distinct payer) as payers
                                     from p join pcat c using (payee) group by 1""").df()
        cats = cats.merge(cat_payers, on="category")

        buckets = [("Under $0.001", 0, 0.001), ("$0.001", 0.001, 0.0010001), ("$0.001 to $0.01", 0.0010001, 0.01),
                   ("$0.01 to $0.10", 0.01, 0.1), ("$0.10 to $1", 0.1, 1), ("$1 to $10", 1, 10), ("$10 and up", 10, 1e18)]
        prices = [{"bucket": b, "payments": int(((p.amount_usd >= lo) & (p.amount_usd < hi)).sum()),
                   "usd": float(p.amount_usd[(p.amount_usd >= lo) & (p.amount_usd < hi)].sum())} for b, lo, hi in buckets]

        per = p.groupby("payer").size()
        pb = [("1 payment", 1, 1), ("2 to 10", 2, 10), ("11 to 100", 11, 100), ("101 to 1,000", 101, 1000),
              ("1,001 to 10,000", 1001, 10000), ("Over 10,000", 10001, 10**12)]
        payer_buckets = [{"bucket": b, "payers": int(((per >= lo) & (per <= hi)).sum()),
                          "payments": int(per[(per >= lo) & (per <= hi)].sum())} for b, lo, hi in pb]

        t0 = pd.Timestamp(start, tz="UTC")
        h = ((pd.to_datetime(p.block_time, utc=True) - t0).dt.total_seconds() // 3600).astype(int).clip(0, 167)
        hourly = [{"h": int(k), "payments": int(v)} for k, v in h.value_counts().sort_index().items()]

        facs, routing, fshare = [], [], None
        if has_tx:
            t = q(f"select t.tx_from, t.tx_to from tx_sample t where t.slice = '{sid}'")
            if not t.empty:
                t = t.merge(fac[["address", "facilitator"]], left_on="tx_from", right_on="address", how="left")
                t["facilitator"] = t["facilitator"].fillna("Not listed")
                vc = t["facilitator"].value_counts()
                top = vc.head(7)
                facs = [{"name": k, "share": float(v / len(t)), "n": int(v)} for k, v in top.items()]
                rest = len(t) - top.sum()
                if rest: facs.append({"name": "Other listed", "share": float(rest / len(t)), "n": int(rest)})
                fshare = float((t["facilitator"] != "Not listed").mean())
                direct = (t["tx_to"] == "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913").mean()
                routing = [{"kind": "Direct USDC call", "share": float(direct)}, {"kind": "Via another contract", "share": float(1 - direct)}]

        top_rows = []
        for r in pp.head(50).itertuples():
            top_rows.append({"payee": r.payee, "name": r.name if isinstance(r.name, str) else None,
                             "category": r.category, "domain": r.domain if isinstance(r.domain, str) else None,
                             "payments": int(r.n), "share": float(r.n / total), "payers": int(r.payers),
                             "per_payer": float(r.n / r.payers), "median_usd": float(r.med), "usd": float(r.usd),
                             "in_registry": bool(r.in_reg), "facilitator": r.facilitator if isinstance(r.facilitator, str) else None,
                             "note": r.notes if isinstance(r.notes, str) else
                                     (f"settled by {r.facilitator}" if not isinstance(r.name, str) and isinstance(r.facilitator, str)
                                      and r.facilitator != "Not listed" else None)})

        # spotlight: the single busiest paying wallet of the week
        tp = p.groupby("payer").size().sort_values(ascending=False)
        w = tp.index[0]
        pw = p[p.payer == w]
        days = ((pd.to_datetime(pw.block_time, utc=True) - t0).dt.total_seconds() // 86400).astype(int).clip(0, 6)
        top_payee = pw.payee.value_counts().index[0]
        tname = pp.loc[pp.payee == top_payee, "name"]
        spotlight = {"payer": w, "payments": int(len(pw)), "share": float(len(pw) / total),
                     "usd": float(pw.amount_usd.sum()), "distinct_prices": int(pw.amount_usd.nunique()),
                     "payees": int(pw.payee.nunique()), "top_payee": top_payee,
                     "top_payee_name": tname.iloc[0] if len(tname) and isinstance(tname.iloc[0], str) else None,
                     "daily": [int((days == d).sum()) for d in range(7)],
                     "seen_in": [s2 for s2, _, _ in SLICES if q(f"select count(*) from payments where slice='{s2}' and payer='{w}'").iloc[0, 0] > 0]}

        end = (t0 + pd.Timedelta(days=6)).date().isoformat()
        out["slices"].append({
            "id": sid, "label": label, "start": start, "end": end,
            "payments": total, "txs": int(q(f"select count(distinct tx_hash) from payments where slice='{sid}'").iloc[0, 0]),
            "payers": int(p.payer.nunique()), "payees": int(p.payee.nunique()),
            "usd_small": float(p.amount_usd[p.amount_usd < 10].sum()), "median_usd": float(p.amount_usd.median()),
            "top1_share": float(pp.n.iloc[0] / total), "top5_share": float(pp.n.head(5).sum() / total),
            "facilitator_share": fshare,
        })
        out["bySlice"][sid] = {"categories": cats.sort_values("payments", ascending=False).to_dict("records"),
                               "payees": top_rows, "prices": prices, "facilitators": facs, "routing": routing,
                               "hourly": hourly, "payer_buckets": payer_buckets,
                               "spotlight": spotlight}
        print(f"  {sid}: {total:,} payments, {len(pp):,} payees, cats {dict(zip(cats.category, cats.payments))}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, default=float))
    print(f"-> {OUT} ({OUT.stat().st_size/1024:.0f} KB)")


if __name__ == "__main__":
    main()
