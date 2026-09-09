"use client";

import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import type { HistoryPoint, HistoryResponse, PriceMap } from "@/lib/types";
import { HISTORY_LIMIT_MAIN } from "@/lib/constants";

/**
 * PLAN §13.B13/C4: sparklines and the main chart share ONE history
 * source and must survive a page refresh -- so this hook seeds from the
 * server's ring-buffer endpoint (`GET /api/history/{ticker}`) rather
 * than accumulating from an empty array since the component mounted.
 *
 * After the initial seed, it extends the buffer with live ticks read
 * from the shared SSE price map (already-open connection, no extra
 * polling), capped at `limit`. An unknown/brand-new ticker returns `200`
 * with `points: []` -- rendered as an empty chart, not an error.
 */
export function usePriceHistory(
  ticker: string | null,
  prices: PriceMap,
  limit: number = HISTORY_LIMIT_MAIN
): { points: HistoryPoint[]; loading: boolean } {
  const [points, setPoints] = useState<HistoryPoint[]>([]);
  const [loading, setLoading] = useState(false);
  const lastAppliedTimestamp = useRef<string | null>(null);

  // Seed from the server whenever the selected ticker (or limit) changes.
  useEffect(() => {
    if (!ticker) {
      setPoints([]);
      return;
    }
    let cancelled = false;
    setLoading(true);
    lastAppliedTimestamp.current = null;
    api
      .get<HistoryResponse>(`/api/history/${encodeURIComponent(ticker)}?limit=${limit}`)
      .then((res) => {
        if (cancelled) return;
        setPoints(res.points);
        const last = res.points[res.points.length - 1];
        lastAppliedTimestamp.current = last ? last.t : null;
      })
      .catch(() => {
        if (!cancelled) setPoints([]);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [ticker, limit]);

  // Extend with live SSE ticks for the active ticker only.
  useEffect(() => {
    if (!ticker) return;
    const tick = prices[ticker];
    if (!tick) return;

    const t = new Date(tick.timestamp * 1000).toISOString();
    if (t === lastAppliedTimestamp.current) return; // already applied this tick
    lastAppliedTimestamp.current = t;

    setPoints((prev) => {
      const next = [...prev, { t, price: tick.price }];
      return next.length > limit ? next.slice(next.length - limit) : next;
    });
  }, [ticker, prices, limit]);

  return { points, loading };
}
