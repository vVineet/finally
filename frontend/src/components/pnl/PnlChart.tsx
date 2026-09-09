"use client";

import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Panel } from "@/components/common/Panel";
import { usePortfolioHistory } from "@/hooks/usePortfolioHistory";
import { COLORS } from "@/lib/constants";
import { formatCurrency, formatTime } from "@/lib/format";

export function PnlChart({ refreshToken }: { refreshToken?: unknown }) {
  const { snapshots, loading } = usePortfolioHistory(refreshToken);
  const data = snapshots.map((s) => ({ t: s.recorded_at, value: s.total_value }));
  const first = data[0]?.value;
  const last = data[data.length - 1]?.value;
  const up = first !== undefined && last !== undefined ? last >= first : true;
  const color = up ? COLORS.positive : COLORS.negative;

  return (
    <Panel title="Portfolio value" className="h-full" bodyClassName="p-2">
      {loading && data.length === 0 && (
        <div className="h-full flex items-center justify-center text-text-tertiary text-xs">Loading…</div>
      )}
      {!loading && data.length === 0 && (
        <div className="h-full flex items-center justify-center text-text-tertiary text-xs" data-testid="pnl-empty">
          No snapshots yet.
        </div>
      )}
      {data.length > 0 && (
        <ResponsiveContainer width="100%" height="100%" minHeight={140} data-testid="pnl-chart">
          <AreaChart data={data} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
            <defs>
              <linearGradient id="pnlFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={color} stopOpacity={0.35} />
                <stop offset="100%" stopColor={color} stopOpacity={0} />
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
              width={64}
              tickFormatter={(v: number) => formatCurrency(v, { compact: true })}
            />
            <Tooltip
              contentStyle={{ background: COLORS.bgPanel, border: `1px solid ${COLORS.border}`, fontSize: 11 }}
              labelFormatter={(v) => formatTime(typeof v === "string" ? v : undefined)}
              formatter={(value) => [formatCurrency(Number(value)), "Total value"]}
            />
            <Area type="monotone" dataKey="value" stroke={color} strokeWidth={1.5} fill="url(#pnlFill)" isAnimationActive={false} />
          </AreaChart>
        </ResponsiveContainer>
      )}
    </Panel>
  );
}
