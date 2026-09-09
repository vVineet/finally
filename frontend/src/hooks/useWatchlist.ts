"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { ApiError } from "@/lib/types";
import type { WatchlistEntry, WatchlistResponse } from "@/lib/types";

// C3: watchlist responses never include price -- ticker + added_at only.
// Prices come exclusively from usePriceStream.
export function useWatchlist() {
  const [watchlist, setWatchlist] = useState<WatchlistEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const res = await api.get<WatchlistResponse>("/api/watchlist");
      setWatchlist(res.watchlist);
      setError(null);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Failed to load watchlist");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const add = useCallback(async (ticker: string) => {
    const res = await api.post<WatchlistResponse>("/api/watchlist", { ticker });
    setWatchlist(res.watchlist);
  }, []);

  const remove = useCallback(async (ticker: string) => {
    const res = await api.del<WatchlistResponse>(`/api/watchlist/${encodeURIComponent(ticker)}`);
    setWatchlist(res.watchlist);
  }, []);

  return { watchlist, loading, error, add, remove, setWatchlist };
}
