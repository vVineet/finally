"use client";

import { useState } from "react";
import { Panel } from "@/components/common/Panel";
import { WatchlistRowContainer } from "./WatchlistRowContainer";
import type { FlashState } from "@/hooks/usePriceStream";
import type { PriceMap, WatchlistEntry } from "@/lib/types";
import { ApiError } from "@/lib/types";

export function Watchlist({
  watchlist,
  prices,
  flashes,
  selectedTicker,
  onSelectTicker,
  onAdd,
  onRemove,
}: {
  watchlist: WatchlistEntry[];
  prices: PriceMap;
  flashes: FlashState;
  selectedTicker: string | null;
  onSelectTicker: (ticker: string) => void;
  onAdd: (ticker: string) => Promise<void>;
  onRemove: (ticker: string) => Promise<void>;
}) {
  const [draft, setDraft] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault();
    const ticker = draft.trim().toUpperCase();
    if (!ticker) return;
    setSubmitting(true);
    setError(null);
    try {
      await onAdd(ticker);
      setDraft("");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to add ticker");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Panel title="Watchlist" aside={`${watchlist.length} tickers`} bodyClassName="flex flex-col">
      <form onSubmit={handleAdd} className="flex gap-1 px-3 py-2 border-b border-border-subtle shrink-0">
        <input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="Add ticker…"
          aria-label="Add ticker to watchlist"
          className="font-data flex-1 min-w-0 bg-bg-input border border-border rounded-sm px-2 py-1 text-xs text-text-primary placeholder:text-text-tertiary focus:outline-none focus:border-accent-blue"
        />
        <button
          type="submit"
          disabled={submitting || !draft.trim()}
          className="px-2 py-1 text-xs rounded-sm bg-accent-blue text-bg-base font-semibold disabled:opacity-40 disabled:cursor-not-allowed"
        >
          Add
        </button>
      </form>
      {error && (
        <div className="px-3 py-1 text-[11px] text-negative" role="alert">
          {error}
        </div>
      )}
      <div className="flex items-center gap-2 px-3 py-1 text-[10px] uppercase tracking-wide text-text-tertiary border-b border-border-subtle shrink-0">
        <span className="w-14">Ticker</span>
        <span className="w-16 text-right">Price</span>
        <span className="w-16 text-right">Chg %</span>
        <span className="flex-1 text-right pr-4">5m</span>
      </div>
      <div className="flex-1 overflow-auto divide-y divide-border-subtle">
        {watchlist.length === 0 && (
          <div className="px-3 py-4 text-text-tertiary text-xs">No tickers yet — add one above.</div>
        )}
        {watchlist.map((entry) => (
          <WatchlistRowContainer
            key={entry.ticker}
            ticker={entry.ticker}
            prices={prices}
            flash={flashes[entry.ticker] ?? null}
            selected={selectedTicker === entry.ticker}
            onSelect={() => onSelectTicker(entry.ticker)}
            onRemove={() => onRemove(entry.ticker)}
          />
        ))}
      </div>
    </Panel>
  );
}
