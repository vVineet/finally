"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { PortfolioHistoryResponse, PortfolioSnapshot } from "@/lib/types";

const POLL_INTERVAL_MS = 30_000; // matches the backend's snapshot cadence (PLAN §7)

/**
 * Backs the P&L chart with server-persisted snapshots (B2: bounded via
 * `limit`, never an unbounded scan). `refreshToken` lets callers force an
 * immediate refetch right after a trade, since the backend records a
 * snapshot synchronously on every trade execution.
 */
export function usePortfolioHistory(refreshToken?: unknown, limit = 200) {
  const [snapshots, setSnapshots] = useState<PortfolioSnapshot[]>([]);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      const res = await api.get<PortfolioHistoryResponse>(`/api/portfolio/history?limit=${limit}`);
      setSnapshots(res.snapshots);
    } catch {
      // Non-fatal — the P&L chart just stays on its last known data.
    } finally {
      setLoading(false);
    }
  }, [limit]);

  useEffect(() => {
    refresh();
  }, [refresh, refreshToken]);

  useEffect(() => {
    const id = setInterval(refresh, POLL_INTERVAL_MS);
    return () => clearInterval(id);
  }, [refresh]);

  return { snapshots, loading };
}
