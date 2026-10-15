"use client";
import type { Dataset, SliceId } from "@/lib/types";
import { colorFor } from "@/lib/types";
import { compact } from "@/lib/fmt";

/* One stacked bar per slice, widths on a shared scale so growth reads as length. */
export function SliceMix({ data, current, onPick }: { data: Dataset; current: SliceId; onPick: (s: SliceId) => void }) {
  const max = Math.max(...data.slices.map((s) => s.payments));
  const cats = Array.from(new Set(data.slices.flatMap((s) => data.bySlice[s.id].categories.map((c) => c.category))));
  const order = cats.sort((a, b) => {
    const tot = (c: string) => data.slices.reduce((t, s) => t + (data.bySlice[s.id].categories.find((x) => x.category === c)?.payments ?? 0), 0);
    return tot(b) - tot(a);
  });
  return (
    <div className="mix ui">
      {data.slices.map((s) => {
        const rows = data.bySlice[s.id].categories;
        return (
          <button key={s.id} className="mix-row" aria-pressed={s.id === current} onClick={() => onPick(s.id)}>
            <span className="mix-l">{s.label}</span>
            <span className="mix-t">
              <span className="mix-bar" style={{ width: `${(s.payments / max) * 100}%` }}>
                {order.map((c) => {
                  const r = rows.find((x) => x.category === c);
                  if (!r) return null;
                  return <span key={c} style={{ flexBasis: `${(r.payments / s.payments) * 100}%`, background: colorFor(c) }} title={`${c}: ${compact(r.payments)}`} />;
                })}
              </span>
              <em className="num">{compact(s.payments)}</em>
            </span>
          </button>
        );
      })}
    </div>
  );
}
