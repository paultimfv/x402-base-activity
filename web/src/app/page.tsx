import data from "../../public/data/x402.json";
import Report from "@/components/Report";
import type { Dataset } from "@/lib/types";

export default function Page() {
  return <Report data={data as unknown as Dataset} />;
}
