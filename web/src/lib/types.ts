export type SliceId = "q1" | "q2" | "q3" | "recent";

export interface SliceMeta {
  id: SliceId;
  label: string;
  start: string;
  end: string;
  payments: number;
  txs: number;
  payers: number;
  payees: number;
  usd_small: number;      // volume of payments under $10 (x402-sized)
  median_usd: number;
  top1_share: number;
  top5_share: number;
  facilitator_share: number | null;   // share of sampled txs sent by a known x402 facilitator
}

export interface CategoryRow { category: string; payments: number; usd: number; payees: number; payers: number }

export interface PayeeRow {
  payee: string;
  name: string | null;
  category: string;
  domain: string | null;
  payments: number;
  share: number;
  payers: number;
  per_payer: number;
  median_usd: number;
  usd: number;
  in_registry: boolean;
  facilitator: string | null;
  note: string | null;
}

export interface PriceRow { bucket: string; payments: number; usd: number }
export interface FacRow { name: string; share: number; n: number }
export interface HourRow { h: number; payments: number }

export interface SliceData {
  categories: CategoryRow[];
  payees: PayeeRow[];
  prices: PriceRow[];
  facilitators: FacRow[];
  routing: { kind: string; share: number }[];
  hourly: HourRow[];
  payer_buckets: { bucket: string; payers: number; payments: number }[];
  spotlight: {
    payer: string; payments: number; share: number; usd: number; distinct_prices: number;
    payees: number; top_payee: string; top_payee_name: string | null; daily: number[]; seen_in: string[];
  };
}

export interface Dataset {
  generated: string;
  chainalysis: { quarter: string; increase: number }[];
  slices: SliceMeta[];
  bySlice: Record<SliceId, SliceData>;
  notes: Record<string, string>;
}

export const CATEGORY_COLOR: Record<string, string> = {
  "AI inference": "var(--c-ai)",
  "Data & search APIs": "var(--c-data)",
  "Mints & drops": "var(--c-mint)",
  "Content & paywalls": "var(--c-content)",
  "Infra & testing": "var(--c-infra)",
  "Agent-to-agent jobs": "var(--c-agent)",
  "API gateways": "var(--c-gw)",
  "Agent games": "var(--c-game)",
  "Unlisted per-call services": "var(--c-percall)",
  "Likely non-x402 transfers": "var(--c-nonx)",
  Unlabeled: "var(--c-unknown)",
};
export const colorFor = (c: string) => CATEGORY_COLOR[c] ?? "var(--c-unknown)";
