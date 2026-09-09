"use client";

import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Panel } from "@/components/common/Panel";
import { usePriceHistory } from "@/hooks/usePriceHistory";
import { COLORS, HISTORY_LIMIT_MAIN } from "@/lib/constants";
import { formatPrice, formatTime } from "@/lib/format";
import type { PriceMap } from "@/lib/types";

export function MainChart({ ticker, prices }: { ticker: string | null; prices: PriceMap }) {
  const { points, loading } = usePriceHistory(ticker, prices, HISTORY_LIMIT_MAIN);
  const tick = ticker ? prices[ticker] : undefined;
  const data = points.map((p) => ({ t: p.t, price: p.price }));
  const first = data[0]?.price;
  const last = data[data.length - 1]?.price;
  const up = first !== undefined && last !== undefined ? last >= first : true;
  const lineColor = up ? COLORS.positive : COLORS.negative;

  return (
    <Panel
      title={ticker ? `${ticker} — price` : "Price chart"}
      aside={tick ? `$${formatPrice(tick.price)}` : undefined}
      className="h-full"
      bodyClassName="p-2"
    >
      {!ticker && (
        <div className="h-full flex items-center justify-center text-text-tertiary text-xs">
          Select a ticker from the watchlist to see its chart.
        </div>
      )}
      {ticker && loading && data.length === 0 && (
        <div className="h-full flex items-center justify-center text-text-tertiary text-xs" data-testid="main-chart-loading">
          Loading history…
        </div>
      )}
      {ticker && !loading && data.length === 0 && (
        <div className="h-full flex items-center justify-center text-text-tertiary text-xs" data-testid="main-chart-empty">
          No price history yet for {ticker}.
        </div>
      )}
      {ticker && data.length > 0 && (
        <ResponsiveContainer width="100%" height="100%" minHeight={180} data-testid="main-chart">
          <AreaChart data={data} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
            <defs>
              <linearGradient id="mainChartFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={lineColor} stopOpacity={0.35} />
                <stop offset="100%" stopColor={lineColor} stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid stroke={COLORS.border} strokeDasharray="2 4" vertical={false} />
            <XAxis
              dataKey="t"
              tickFormatter={(v: string) => formatTime(v)}
              tick={{ fill: COLORS.textTertiary, fontSize: 10 }}
              axisLine={{ stroke: COLORS.border }}
              tickLine={false}
              minTickGap={40}
            />
            <YAxis
              domain={["auto", "auto"]}
              tick={{ fill: COLORS.textTertiary, fontSize: 10 }}
              axisLine={{ stroke: COLORS.border }}
              tickLine={false}
              width={56}
              tickFormatter={(v: number) => v.toFixed(2)}
            />
            <Tooltip
              contentStyle={{ background: COLORS.bgPanel, border: `1px solid ${COLORS.border}`, fontSize: 11 }}
              labelFormatter={(v) => formatTime(typeof v === "string" ? v : undefined)}
              formatter={(value) => [`$${Number(value).toFixed(2)}`, "Price"]}
            />
            <Area type="monotone" dataKey="price" stroke={lineColor} strokeWidth={1.5} fill="url(#mainChartFill)" isAnimationActive={false} />
          </AreaChart>
        </ResponsiveContainer>
      )}
    </Panel>
  );
}
