// Live x402: pipeline/live.py commits web/public/data/x402_live.json every hour; the site reads it straight from GitHub
// and re-checks every 5 minutes, so new data shows up without a redeploy. The copy bundled at build time is the fallback.
import { cacheLife } from "next/cache";
import fallback from "../../public/data/x402_live.json";

export type { Live } from "./live-types";
import type { Live } from "./live-types";
const RAW = "https://raw.githubusercontent.com/paultimfv/x402-base-activity/main/web/public/data/x402_live.json";

export async function getLive(): Promise<Live> {
  "use cache";
  cacheLife({ stale: 60, revalidate: 300, expire: 86400 });
  try {
    const r = await fetch(RAW);
    if (r.ok) {
      const d = (await r.json()) as Live;
      if (d?.daily?.length) return d;
    }
  } catch {}
  return fallback;
}
