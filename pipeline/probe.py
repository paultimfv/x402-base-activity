"""Probe: does the calldata approach catch x402 payments on Base?

Pulls N recent full blocks from Alchemy, finds USDC EIP-3009 calls by selector,
and compares against AuthorizationUsed logs over the same range (the ground truth
for every EIP-3009 settlement, direct or routed through another contract).
"""
import os, sys, json, collections, requests
from pathlib import Path
from dotenv import load_dotenv
from web3 import Web3

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")
RPC = os.environ["BASE_RPC_URL"]
USDC = "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913"
N = int(sys.argv[1]) if len(sys.argv) > 1 else 10

def sel(sig): return "0x" + Web3.keccak(text=sig).hex().removeprefix("0x")[:8]
SELECTORS = {
    sel("transferWithAuthorization(address,address,uint256,uint256,uint256,bytes32,uint8,bytes32,bytes32)"): "transferWithAuth(vrs)",
    sel("transferWithAuthorization(address,address,uint256,uint256,uint256,bytes32,bytes)"): "transferWithAuth(bytes)",
    sel("receiveWithAuthorization(address,address,uint256,uint256,uint256,bytes32,uint8,bytes32,bytes32)"): "receiveWithAuth(vrs)",
    sel("receiveWithAuthorization(address,address,uint256,uint256,uint256,bytes32,bytes)"): "receiveWithAuth(bytes)",
}
AUTH_USED = "0x" + Web3.keccak(text="AuthorizationUsed(address,bytes32)").hex().removeprefix("0x")

def rpc(method, params, tries=6):
    import time
    for i in range(tries):
        try:
            r = requests.post(RPC, json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params}, timeout=60)
            out = r.json()
            if "error" in out: raise RuntimeError(out["error"])
            return out["result"]
        except Exception as e:
            if i == tries - 1: raise
            print(f"  retry {method} ({r.status_code if 'r' in dir() else '?'}): {str(e)[:80]}")
            time.sleep(2 ** i)

head = int(rpc("eth_blockNumber", []), 16) - 5
lo, hi = head - N + 1, head
print(f"blocks {lo:,}..{hi:,} ({N})")

direct = []          # (tx, kind)
tx_by_hash = {}
for b in range(lo, hi + 1):
    blk = rpc("eth_getBlockByNumber", [hex(b), True])
    for tx in blk["transactions"]:
        tx_by_hash[tx["hash"]] = tx
        if (tx.get("to") or "").lower() == USDC and tx["input"][:10] in SELECTORS:
            direct.append((tx, SELECTORS[tx["input"][:10]]))

logs = rpc("eth_getLogs", [{"address": USDC, "topics": [AUTH_USED],
                            "fromBlock": hex(lo), "toBlock": hex(hi)}])
log_txs = {l["transactionHash"] for l in logs}
direct_txs = {t["hash"] for t, _ in direct}

print(f"txs in range: {len(tx_by_hash):,}")
print(f"AuthorizationUsed logs: {len(logs)} in {len(log_txs)} txs")
print(f"direct USDC EIP-3009 calls: {len(direct)}  by kind: {dict(collections.Counter(k for _, k in direct))}")
print(f"log txs caught by calldata: {len(log_txs & direct_txs)}/{len(log_txs)}")

# what are the routed ones? (EIP-3009 settled via another contract)
routed = collections.Counter()
for h in log_txs - direct_txs:
    t = tx_by_hash.get(h, {})
    routed[((t.get("to") or "?").lower(), t.get("input", "")[:10])] += 1
print("routed (to, selector):", routed.most_common(10))

senders = collections.Counter(t["from"].lower() for t, _ in direct)
print("top tx senders (facilitator candidates):")
for a, n in senders.most_common(15): print(f"  {a}  {n}")

# reverted? one eth_getBlockReceipts per block (not per tx) to stay under the CU/s cap
import time
status = {}
for b in range(lo, hi + 1):
    for rc in rpc("eth_getBlockReceipts", [hex(b)]):
        status[rc["transactionHash"]] = rc["status"]
    time.sleep(0.5)
failed = sum(1 for t, _ in direct if status.get(t["hash"]) != "0x1")
print(f"reverted direct calls: {failed}/{len(direct)}")
