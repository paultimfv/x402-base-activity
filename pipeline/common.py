"""Shared config + a small resilient JSON-RPC client for Base."""
import os, re, time, itertools, requests
from pathlib import Path
from dotenv import load_dotenv
from web3 import Web3

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")
RAW = ROOT / "data" / "raw"

USDC = "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913"
def topic(sig): return "0x" + Web3.keccak(text=sig).hex().removeprefix("0x")
AUTH_USED = topic("AuthorizationUsed(address,bytes32)")
TRANSFER = topic("Transfer(address,address,uint256)")

# Base: 2s blocks since genesis, so block <-> time is exact arithmetic
BASE_GENESIS_TS = 1686789347
def block_at(ts): return (int(ts) - BASE_GENESIS_TS) // 2
def ts_of(block): return BASE_GENESIS_TS + 2 * int(block)


def _infura_base():
    url = os.environ.get("INFURA_BASE_URL")
    if url: return url
    m = re.search(r"/v3/([0-9a-f]+)", os.environ.get("INFURA_URL", ""))
    return f"https://base-mainnet.infura.io/v3/{m.group(1)}" if m else None


class RPC:
    """Infura for getLogs/tx lookups (Alchemy free caps getLogs at 10 blocks)."""
    def __init__(self, url=None, timeout=90):
        self.url = url or _infura_base() or os.environ["BASE_RPC_URL"]
        self.timeout = timeout
        self._ids = itertools.count(1)

    def _post(self, payload, tries=12):
        for i in range(tries):
            try:
                r = requests.post(self.url, json=payload, timeout=self.timeout)
                if r.status_code == 429: raise RuntimeError("429")
                return r.json()
            except Exception as e:
                if i == tries - 1: raise
                time.sleep(min(2 ** i, 60))

    def call(self, method, params):
        out = self._post({"jsonrpc": "2.0", "id": next(self._ids), "method": method, "params": params})
        if "error" in out: raise RuntimeError(str(out["error"])[:300])
        return out["result"]

    def batch(self, calls):
        """[(method, params)] -> results in order; Infura reports rate limits per item, so check each."""
        payload = [{"jsonrpc": "2.0", "id": i, "method": m, "params": p} for i, (m, p) in enumerate(calls)]
        for attempt in range(7):
            out = self._post(payload)
            if isinstance(out, list) and all("result" in o for o in out):
                return [o["result"] for o in sorted(out, key=lambda o: o["id"])]
            time.sleep(min(2 ** attempt, 30))
        raise RuntimeError(f"batch failed: {str(out)[:300]}")

    def logs(self, topics, lo, hi, address=USDC):
        """getLogs with adaptive halving when the 10k-result cap is hit."""
        try:
            return self.call("eth_getLogs", [{"address": address, "topics": topics,
                                              "fromBlock": hex(lo), "toBlock": hex(hi)}])
        except RuntimeError as e:
            if "10000 results" not in str(e) or hi <= lo: raise
            mid = (lo + hi) // 2
            return self.logs(topics, lo, mid, address) + self.logs(topics, mid + 1, hi, address)
