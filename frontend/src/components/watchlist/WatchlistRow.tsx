"use client";

import type { HistoryPoint, PriceTick } from "@/lib/types";
import type { FlashDirection } from "@/hooks/usePriceStream";
import { PriceCell } from "@/components/common/PriceCell";
import { ChangeCell } from "@/components/common/ChangeCell";
import { Sparkline } from "./Sparkline";

export function WatchlistRow({
  ticker,
  tick,
  flash,
  points,
  selected,
  onSelect,
  onRemove,
}: {
  ticker: string;
  tick: PriceTick | undefined;
  flash: FlashDirection;
  points: HistoryPoint[];
  selected: boolean;
  onSelect: () => void;
  onRemove: () => void;
}) {
  return (
    <div
      role="button"
      tabIndex={0}
      onClick={onSelect}
      onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && onSelect()}
      data-testid={`watchlist-row-${ticker}`}
      className={`group flex items-center gap-2 px-3 py-1.5 cursor-pointer border-l-2 ${
        selected ? "border-l-accent-yellow bg-bg-panel-raised" : "border-l-transparent hover:bg-bg-panel-raised/60"
      }`}
    >
      <div className="w-14 shrink-0">
        <div className={`font-data font-semibold ${selected ? "text-accent-yellow" : "text-text-primary"}`}>{ticker}</div>
      </div>
      <div className="w-16 shrink-0 text-right">
        <PriceCell price={tick?.price ?? null} flash={flash} />
      </div>
      <div className="w-16 shrink-0 text-right">
        <ChangeCell percent={tick?.day_change_percent ?? null} />
      </div>
      <div className="flex-1 flex justify-end">
        <Sparkline points={points} />
      </div>
      <button
        type="button"
        aria-label={`Remove ${ticker} from watchlist`}
        onClick={(e) => {
          e.stopPropagation();
          onRemove();
        }}
        className="w-4 shrink-0 text-text-tertiary hover:text-negative opacity-0 group-hover:opacity-100 transition-opacity"
      >
        ×
      </button>
    </div>
  );
}
