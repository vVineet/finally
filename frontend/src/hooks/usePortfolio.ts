"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { ApiError } from "@/lib/types";
import type { Portfolio, ResetResponse, TradeResponse } from "@/lib/types";

export function usePortfolio() {
  const [portfolio, setPortfolio] = useState<Portfolio | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const data = await api.get<Portfolio>("/api/portfolio");
      setPortfolio(data);
      setError(null);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Failed to load portfolio");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  // C2: mutating endpoints return updated state directly -- never a
  // follow-up GET after trade/reset.
  const trade = useCallback(async (ticker: string, side: "buy" | "sell", quantity: number) => {
    const res = await api.post<TradeResponse>("/api/portfolio/trade", { ticker, side, quantity });
    setPortfolio(res.portfolio);
    return res;
  }, []);

  const reset = useCallback(async () => {
    const res = await api.post<ResetResponse>("/api/portfolio/reset");
    setPortfolio(res.portfolio);
    return res;
  }, []);

  return { portfolio, loading, error, trade, reset, refresh, setPortfolio };
}
