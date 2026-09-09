"use client";

import { useState } from "react";
import { ApiError } from "@/lib/types";
import type { Trade } from "@/lib/types";

export function TradeBar({
  onTrade,
  defaultTicker,
}: {
  onTrade: (ticker: string, side: "buy" | "sell", quantity: number) => Promise<{ trade: Trade }>;
  defaultTicker?: string | null;
}) {
  const [ticker, setTicker] = useState(defaultTicker ?? "");
  const [quantity, setQuantity] = useState("");
  const [submitting, setSubmitting] = useState<"buy" | "sell" | null>(null);
  const [feedback, setFeedback] = useState<{ kind: "success" | "error"; text: string } | null>(null);

  const submit = async (side: "buy" | "sell") => {
    const tickerValue = ticker.trim().toUpperCase();
    const qtyValue = Number(quantity);
    if (!tickerValue) {
      setFeedback({ kind: "error", text: "Enter a ticker." });
      return;
    }
    if (!Number.isFinite(qtyValue) || qtyValue <= 0) {
      setFeedback({ kind: "error", text: "Quantity must be a positive number." });
      return;
    }
    setSubmitting(side);
    setFeedback(null);
    try {
      const res = await onTrade(tickerValue, side, qtyValue);
      setFeedback({
        kind: "success",
        text: `${side === "buy" ? "Bought" : "Sold"} ${res.trade.quantity} ${res.trade.ticker} @ $${res.trade.price.toFixed(2)}`,
      });
      setQuantity("");
    } catch (err) {
      setFeedback({ kind: "error", text: err instanceof ApiError ? err.message : "Trade failed." });
    } finally {
      setSubmitting(null);
    }
  };

  return (
    <div className="flex flex-col gap-1.5 border border-border bg-bg-panel px-3 py-2">
      <div className="flex items-center gap-2">
        <input
          value={ticker}
          onChange={(e) => setTicker(e.target.value)}
          placeholder="Ticker"
          aria-label="Trade ticker"
          className="font-data w-24 bg-bg-input border border-border rounded-sm px-2 py-1.5 text-xs uppercase text-text-primary placeholder:text-text-tertiary placeholder:normal-case focus:outline-none focus:border-accent-blue"
        />
        <input
          value={quantity}
          onChange={(e) => setQuantity(e.target.value)}
          placeholder="Qty"
          type="number"
          min="0"
          step="any"
          aria-label="Trade quantity"
          className="font-data w-24 bg-bg-input border border-border rounded-sm px-2 py-1.5 text-xs text-text-primary placeholder:text-text-tertiary focus:outline-none focus:border-accent-blue"
        />
        <button
          type="button"
          onClick={() => submit("buy")}
          disabled={submitting !== null}
          data-testid="buy-button"
          className="px-4 py-1.5 text-xs font-semibold rounded-sm bg-accent-purple text-white disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {submitting === "buy" ? "Buying…" : "Buy"}
        </button>
        <button
          type="button"
          onClick={() => submit("sell")}
          disabled={submitting !== null}
          data-testid="sell-button"
          className="px-4 py-1.5 text-xs font-semibold rounded-sm border border-accent-purple text-accent-purple disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {submitting === "sell" ? "Selling…" : "Sell"}
        </button>
        <span className="text-[10px] text-text-tertiary ml-auto">Market order · instant fill · no fees</span>
      </div>
      {feedback && (
        <div
          role="status"
          className={`text-[11px] px-2 py-1 rounded-sm ${feedback.kind === "success" ? "text-positive bg-positive/10" : "text-negative bg-negative/10"}`}
        >
          {feedback.text}
        </div>
      )}
    </div>
  );
}
