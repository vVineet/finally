"use client";

import { usePriceHistory } from "@/hooks/usePriceHistory";
import { HISTORY_LIMIT_SPARKLINE } from "@/lib/constants";
import type { PriceMap } from "@/lib/types";
import type { FlashDirection } from "@/hooks/usePriceStream";
import { WatchlistRow } from "./WatchlistRow";

/**
 * Wires a single watchlist ticker's server-backed history (PLAN
 * §13.B13/C4) into the presentational WatchlistRow, keeping that
 * component simple to unit test with mock points directly.
 */
export function WatchlistRowContainer({
  ticker,
  prices,
  flash,
  selected,
  onSelect,
  onRemove,
}: {
  ticker: string;
  prices: PriceMap;
  flash: FlashDirection;
  selected: boolean;
  onSelect: () => void;
  onRemove: () => void;
}) {
  const { points } = usePriceHistory(ticker, prices, HISTORY_LIMIT_SPARKLINE);
  return (
    <WatchlistRow
      ticker={ticker}
      tick={prices[ticker]}
      flash={flash}
      points={points}
      selected={selected}
      onSelect={onSelect}
      onRemove={onRemove}
    />
  );
}
