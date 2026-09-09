"use client";

import { Line, LineChart, YAxis } from "recharts";
import type { HistoryPoint } from "@/lib/types";
import { COLORS } from "@/lib/constants";

export function Sparkline({ points, width = 84, height = 28 }: { points: HistoryPoint[]; width?: number; height?: number }) {
  if (points.length < 2) {
    return (
      <div
        style={{ width, height }}
        className="flex items-center justify-center text-text-tertiary text-[10px]"
        data-testid="sparkline-empty"
      >
        · · ·
      </div>
    );
  }

  const first = points[0].price;
  const last = points[points.length - 1].price;
  const color = last >= first ? COLORS.positive : COLORS.negative;
  const data = points.map((p) => ({ price: p.price }));

  return (
    <div style={{ width, height }} data-testid="sparkline">
      {/* Fixed pixel size (never percentage-laid-out), so this renders
          directly rather than through ResponsiveContainer -- avoids
          depending on ResizeObserver, which jsdom doesn't implement. */}
      <LineChart width={width} height={height} data={data} margin={{ top: 2, right: 1, bottom: 2, left: 1 }}>
        <YAxis domain={["dataMin", "dataMax"]} hide />
        <Line type="monotone" dataKey="price" stroke={color} strokeWidth={1.5} dot={false} isAnimationActive={false} />
      </LineChart>
    </div>
  );
}
