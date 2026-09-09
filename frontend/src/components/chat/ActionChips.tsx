import { formatQuantity } from "@/lib/format";
import type { ChatActions } from "@/lib/types";

/**
 * PLAN §13.A3 / API_CONTRACT.md: the model's prose ("I'll buy...") and
 * what actually happened are rendered as visually distinct elements. A
 * failed trade is unmistakable — red border, "failed" wording, and the
 * backend's error string, never silently dropped.
 */
export function ActionChips({ actions }: { actions: ChatActions | null }) {
  const trades = actions?.trades ?? [];
  const watchlistChanges = actions?.watchlist ?? [];
  if (trades.length === 0 && watchlistChanges.length === 0) return null;

  return (
    <div className="mt-1.5 flex flex-col gap-1" data-testid="action-chips">
      {trades.map((t, i) => {
        const ok = t.status === "success";
        return (
          <div
            key={`trade-${i}`}
            data-testid={`trade-chip-${ok ? "success" : "failed"}`}
            className={`font-data text-[11px] px-2 py-1 rounded-sm border ${
              ok ? "border-positive/50 bg-positive/10 text-positive" : "border-negative/50 bg-negative/10 text-negative"
            }`}
          >
            {ok ? (
              <>
                {t.side === "buy" ? "Bought" : "Sold"} {formatQuantity(t.quantity)} {t.ticker}
                {t.price !== undefined ? ` @ $${t.price.toFixed(2)}` : ""}
              </>
            ) : (
              <>
                Failed to {t.side} {formatQuantity(t.quantity)} {t.ticker}
                {t.error ? `: ${t.error}` : ""}
              </>
            )}
          </div>
        );
      })}
      {watchlistChanges.map((w, i) => {
        const ok = w.status === "success";
        return (
          <div
            key={`watchlist-${i}`}
            data-testid={`watchlist-chip-${ok ? "success" : "failed"}`}
            className={`font-data text-[11px] px-2 py-1 rounded-sm border ${
              ok ? "border-accent-blue/50 bg-accent-blue/10 text-accent-blue" : "border-negative/50 bg-negative/10 text-negative"
            }`}
          >
            {ok ? (
              <>Watchlist: {w.action === "add" ? "added" : "removed"} {w.ticker}</>
            ) : (
              <>Failed to {w.action} {w.ticker}{w.error ? `: ${w.error}` : ""}</>
            )}
          </div>
        );
      })}
    </div>
  );
}
