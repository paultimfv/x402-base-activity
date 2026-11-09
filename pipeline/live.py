"""Live x402 on Base: the last 30 days, updated hourly -> web/public/data/x402_live.json.

Same payment definition as the study (fetch_payments.py): AuthorizationUsed + the USDC Transfer at logIndex+1.
Each run reads only the blocks since the last run (one hour of Base is ~1,800 blocks, a handful of eth_getLogs calls),
so it runs on a free public RPC (LIVE_RPC_URL, default publicnode). A hash-keyed 10% sample of payments gets its tx
sender looked up, to estimate the share settled by known x402 facilitators (config/facilitators.csv), the study's filter.

  python pipeline/live.py            # incremental; first run backfills BACKFILL_DAYS
"""
import csv, json, os, time, datetime as dt, statistics
from collections import defaultdict
from pathlib import Path
from common import RPC, AUTH_USED, TRANSFER

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "web/public/data/x402_live.json"
STATE = ROOT / "data/live/state.json"
URL = os.environ.get("LIVE_RPC_URL", "https://base-rpc.publicnode.com")   # Alchemy free caps Base getLogs at 10 blocks
KEEP_DAYS, BACKFILL_DAYS, CHUNK, SAMPLE_MOD = 30, int(os.environ.get("BACKFILL_DAYS", "7")), 2000, 10
BUDGET = time.time() + float(os.environ.get("LIVE_BUDGET_MIN", "40")) * 60
DETAIL_DAYS = 2   # full payee tables for today and yesterday (still filling); older days keep their top 50


def labels():
    out = {}
    with open(ROOT / "config/labels.csv") as f:
        for r in csv.DictReader(f):
            out[r["payee"].lower()] = {"name": r["name"], "category": r["category"]}
    try:
        import pandas as pd
        o = pd.read_parquet(ROOT / "config/x402scan_origins.parquet")
        for _, r in o.iterrows():
            a = str(r.get("payee", r.iloc[0])).lower()
            if a not in out:
                name = r.get("title") or r.get("origin") or ""
                if isinstance(name, str) and name:
                    out[a] = {"name": name[:60], "category": "x402scan origin"}
    except Exception:
        pass
    return out


def facilitators():
    with open(ROOT / "config/facilitators.csv") as f:
        return {r["address"].lower(): r["facilitator"] for r in csv.DictReader(f)}


def fetch(rpc, lo, hi):
    """Pairs in [lo, hi] (see fetch_payments.fetch_chunk)."""
    au = rpc.logs([AUTH_USED], lo, hi)
    payers = sorted({l["topics"][1] for l in au})
    tr = []
    for i in range(0, len(payers), 500):
        tr += rpc.logs([TRANSFER, payers[i:i + 500]], lo, hi)
    by_key = {(l["transactionHash"], int(l["logIndex"], 16)): l for l in tr}
    rows = []
    for l in au:
        t = by_key.get((l["transactionHash"], int(l["logIndex"], 16) + 1))
        if not t or t["topics"][1] != l["topics"][1]:
            continue
        rows.append({"block": int(l["blockNumber"], 16), "tx": l["transactionHash"],
                     "payer": "0x" + l["topics"][1][-40:], "payee": "0x" + t["topics"][2][-40:], "usd": int(t["data"], 16) / 1e6})
    return rows


_bt = {}
def btime(rpc, b):
    """Real block timestamp. Base no longer makes exactly one block per 2 s, so block math from genesis drifts."""
    if b not in _bt:
        _bt[b] = int(rpc.call("eth_getBlockByNumber", [hex(b), False])["timestamp"], 16)
    return _bt[b]


def chunk(rpc, b, e):
    rows = fetch(rpc, b, e)
    sample = [r for r in rows if int(r["tx"], 16) % SAMPLE_MOD == 0]
    senders = {}
    for i in range(0, len(sample), 50):
        txs = rpc.batch([("eth_getTransactionByHash", [r["tx"]]) for r in sample[i:i + 50]])
        for r, t in zip(sample[i:i + 50], txs):
            senders[r["tx"]] = (t or {}).get("from", "").lower()
    return rows, senders, btime(rpc, b), btime(rpc, e)


def main():
    rpc, fac = RPC(URL), facilitators()
    state = json.loads(STATE.read_text()) if STATE.exists() else {"last_block": None, "days": {}}
    head = int(rpc.call("eth_blockNumber", []), 16) - 10      # stay a few blocks behind the tip
    if state["last_block"]:
        lo = state["last_block"] + 1
    else:   # first run: measure the current block time and step back BACKFILL_DAYS
        per_block = (btime(rpc, head) - btime(rpc, head - 200_000)) / 200_000
        lo = head - int(BACKFILL_DAYS * 86400 / per_block)
    days = state["days"]
    print(f"live: blocks {lo:,} -> {head:,} ({(btime(rpc, head) - btime(rpc, lo)) / 3600:.1f} h)", flush=True)
    b = lo
    while b <= head and time.time() < BUDGET:
        e = min(b + CHUNK - 1, head)
        try:
            rows, senders, t_lo, t_hi = chunk(rpc, b, e)
        except Exception as err:   # public RPC hiccup: retry once, else stop here and keep what we have
            print(f"live: chunk {b:,} failed ({str(err)[:120]}), retrying", flush=True)
            time.sleep(5)
            try:
                rows, senders, t_lo, t_hi = chunk(rpc, b, e)
            except Exception as err:
                print(f"live: stopping at block {b:,}: {str(err)[:120]}", flush=True)
                break
        ts = lambda blk: t_lo + (blk - b) * (t_hi - t_lo) / max(e - b, 1)   # linear within a ~1 h chunk
        for r in rows:
            d = dt.datetime.fromtimestamp(ts(r["block"]), dt.timezone.utc).strftime("%Y-%m-%d")
            day = days.setdefault(d, {"payments": 0, "usd": 0.0, "sampled": 0, "sampled_fac": 0, "sizes": [], "payees": {}, "payers": {}})
            day["payments"] += 1; day["usd"] += r["usd"]
            if len(day["sizes"]) < 5000: day["sizes"].append(round(r["usd"], 6))
            p = day["payees"].setdefault(r["payee"], [0, 0.0]); p[0] += 1; p[1] += r["usd"]
            day["payers"][r["payer"]] = day["payers"].get(r["payer"], 0) + 1
            if r["tx"] in senders:
                day["sampled"] += 1; day["sampled_fac"] += senders[r["tx"]] in fac
        state["last_block"] = e
        b = e + 1
        if (b - lo) // CHUNK % 10 == 0:   # long catch-ups: save progress so a killed run doesn't lose it
            STATE.parent.mkdir(parents=True, exist_ok=True)
            STATE.write_text(json.dumps({**state, "days": days}, separators=(",", ":")))
    # trim: keep KEEP_DAYS; older-than-DETAIL_DAYS days keep their top 50 payees and only a payer count
    keep = sorted(days)[-KEEP_DAYS:]
    days = {d: days[d] for d in keep}
    for d in keep[:-DETAIL_DAYS]:
        day = days[d]
        day["payees"] = dict(sorted(day["payees"].items(), key=lambda kv: -kv[1][0])[:50])
        if isinstance(day.get("payers"), dict):
            day["payer_count"] = len(day["payers"]); day["payers"] = {}
    state["days"] = days
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, separators=(",", ":")))

    # public file for the site
    lab = labels()
    name = lambda a: lab.get(a.lower(), {}).get("name")
    ordered = sorted(days)
    series = []
    for d in ordered:
        x = days[d]
        top = sorted(x["payees"].items(), key=lambda kv: -kv[1][0])
        series.append({
            "day": d, "payments": x["payments"], "usd": round(x["usd"], 2),
            "payers": x.get("payer_count") or len(x.get("payers") or {}),
            "median_usd": round(statistics.median(x["sizes"]), 4) if x["sizes"] else None,
            "facilitator_share": round(x["sampled_fac"] / x["sampled"], 3) if x["sampled"] >= 20 else None,
            "top_payee_share": round(top[0][1][0] / x["payments"], 3) if top and x["payments"] else None,
            "top_payee": name(top[0][0]) or top[0][0] if top else None,
        })
    last7 = ordered[-8:-1] if len(ordered) > 7 else ordered[:-1] or ordered   # 7 complete days
    agg = defaultdict(lambda: [0, 0.0])
    for d in last7:
        for a, (n, usd) in days[d]["payees"].items():
            agg[a][0] += n; agg[a][1] += usd
    tot7 = sum(days[d]["payments"] for d in last7) or 1
    payees = [{"payee": a, "name": name(a), "category": lab.get(a.lower(), {}).get("category"),
               "payments": n, "usd": round(usd, 2), "share": round(n / tot7, 4)}
              for a, (n, usd) in sorted(agg.items(), key=lambda kv: -kv[1][0])[:15]]
    out = {"updatedAt": dt.datetime.now(dt.timezone.utc).isoformat(timespec="minutes"),
           "throughBlock": state["last_block"],
           "throughTime": dt.datetime.fromtimestamp(btime(rpc, state["last_block"]), dt.timezone.utc).isoformat(timespec="minutes"),
           "window": {"from": last7[0] if last7 else None, "to": last7[-1] if last7 else None},
           "daily": series, "topPayees7d": payees}
    OUT.write_text(json.dumps(out, indent=1))
    print(f"live: through {out['throughTime']}; {len(series)} days; last full day "
          f"{series[-2]['day'] if len(series) > 1 else '-'} = {series[-2]['payments'] if len(series) > 1 else 0:,} payments", flush=True)


if __name__ == "__main__":
    main()
