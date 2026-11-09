import data from "../../public/data/x402.json";
import Report from "@/components/Report";
import LivePanel from "@/components/LivePanel";
import { getLive } from "@/lib/live";
import type { Dataset } from "@/lib/types";

export default async function Page() {
  const live = await getLive();
  return <Report data={data as unknown as Dataset} live={<LivePanel live={live} />} />;
}
