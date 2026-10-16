"""Raw Parquet -> local DuckDB with the decoded/derived tables the dashboard reads.

Tables mirror what gets loaded to Neon (load_neon.py): payments, payees, payee_slice,
price_points, facilitators, mix_by_category.
"""
import duckdb
from common import RAW, ROOT

DB = ROOT / "data" / "x402.duckdb"

SQL_RAW = f"""
create or replace table raw_payments as
select regexp_extract(filename, 'payments/([a-z0-9]+)/', 1) as slice,
       block, to_timestamp(ts) as block_time, tx_hash, log_index, tx_index,
       payer, payee as first_hop, amount_raw::hugeint as amount_raw, amount_raw::double / 1e6 as amount_usd, nonce
from read_parquet('{RAW}/payments/*/*.parquet', filename = true);
"""

# The payee is the final recipient: auth-capture payments resolve to the escrow's receiver,
# and payments through a pass-through router resolve to the router's single next hop.
SQL_FINAL = """
create or replace table payments as
select r.* exclude (first_hop),
       coalesce(e.receiver, h.next_hop, rt.next_hop, r.first_hop) as payee,
       r.first_hop,
       case when e.receiver is not null then 'auth-capture escrow'
            when h.next_hop is not null then h.router_label
            when rt.next_hop is not null then 'router' end as via
from raw_payments r
left join router_hops h on h.tx_hash = r.tx_hash and h.router = r.first_hop
left join (select tx_hash, payer, any_value(receiver) as receiver from escrow group by 1, 2) e
       on e.tx_hash = r.tx_hash and e.payer = r.payer and r.first_hop = '0x0e3df9510de65469c4518d7843919c0b8c7a7757'
left join routers rt on rt.payee = r.first_hop;
"""

SQL = f"""

create or replace table registry as
select * from read_parquet('{ROOT}/config/registry_payto.parquet');

create or replace table registry_payee as
select payto as payee,
       count(distinct domain) as n_domains,
       count(*) as n_resources,
       mode(domain) as top_domain,
       string_agg(distinct domain, ', ' order by domain) as domains,
       any_value(description) as sample_description
from registry group by 1;

-- manual + onchain labels (category, name, notes); edited by hand
create or replace table labels as
select * from read_csv('{ROOT}/config/labels.csv', header = true, all_varchar = true);

create or replace table payee_slice as
select p.slice, p.payee,
       count(*) as payments, count(distinct p.payer) as payers,
       sum(p.amount_usd) as usd, median(p.amount_usd) as median_usd,
       count(distinct p.amount_raw) as distinct_prices
from payments p group by 1, 2;

create or replace table payees as
select s.payee,
       sum(payments) as payments, sum(usd) as usd,
       max(payers) as max_slice_payers,
       coalesce(l.name, r.top_domain) as name,
       coalesce(l.category, case when r.payee is not null then 'registry (unlabeled)' else 'unknown' end) as category,
       r.domains, r.n_domains, l.notes
from payee_slice s
left join registry_payee r using (payee)
left join labels l using (payee)
group by s.payee, l.name, r.top_domain, l.category, r.payee, r.domains, r.n_domains, l.notes;

create or replace table price_points as
select slice, payee, amount_usd, count(*) as payments
from payments group by 1, 2, 3;

create or replace table mix_by_category as
select p.slice, coalesce(y.category, 'unknown') as category,
       count(*) as payments, sum(p.amount_usd) as usd,
       count(distinct p.payee) as payees, count(distinct p.payer) as payers
from payments p left join payees y using (payee) group by 1, 2;
"""


def build():
    con = duckdb.connect(str(DB))
    if not (ROOT / "config" / "labels.csv").exists():
        (ROOT / "config" / "labels.csv").write_text("payee,name,category,notes\n")
    con.execute(SQL_RAW)
    esc = RAW / "escrow.parquet"
    con.execute(f"create or replace table escrow as select * from read_parquet('{esc}')" if esc.exists() else
                "create or replace table escrow (tx_hash varchar, payer varchar, receiver varchar)")
    rt = ROOT / "config" / "routers.parquet"
    con.execute(f"""create or replace table routers as select payee, next_hop from read_parquet('{rt}')
                    where forwarded_share >= 0.95 and next_hop_share >= 0.95""" if rt.exists() else
                "create or replace table routers (payee varchar, next_hop varchar)")
    hops = RAW / "router_hops.parquet"
    con.execute(f"create or replace table router_hops as select tx_hash, router, router_label, next_hop from read_parquet('{hops}')"
                if hops.exists() else "create or replace table router_hops (tx_hash varchar, router varchar, router_label varchar, next_hop varchar)")
    con.execute(SQL_FINAL)
    con.execute(SQL)
    txs = list((RAW / "txs").glob("*.parquet"))
    if txs:
        con.execute(f"""
        create or replace table tx_sample as
        select regexp_extract(filename, 'txs/([a-z0-9]+)\\.parquet', 1) as slice, * exclude (filename)
        from read_parquet('{RAW}/txs/*.parquet', filename = true)""")
    for t in ["payments", "registry_payee", "payees", "payee_slice", "mix_by_category"] + (["tx_sample"] if txs else []):
        print(f"  {t:18} {con.sql(f'select count(*) from {t}').fetchone()[0]:>10,}")
    con.close()
    print(f"-> {DB}")


if __name__ == "__main__":
    build()
