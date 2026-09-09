"use client";

import { ResponsiveContainer, Treemap } from "recharts";
import { Panel } from "@/components/common/Panel";
import { COLORS } from "@/lib/constants";
import { formatPercent } from "@/lib/format";
import type { Position } from "@/lib/types";

interface HeatmapDatum {
  name: string;
  size: number;
  pnlPercent: number | null;
  // recharts' TreemapDataType requires an index signature.
  [key: string]: unknown;
}

// Interpolates between the negative/positive accent colors by magnitude
// of P&L%, capped at ±15% so one blown-out position doesn't wash out the
// rest of the map. Null (no cached price yet) renders neutral gray.
function colorFor(pnlPercent: number | null): string {
  if (pnlPercent === null) return COLORS.textTertiary;
  const capped = Math.max(-15, Math.min(15, pnlPercent));
  const intensity = Math.abs(capped) / 15; // 0..1
  const base = capped >= 0 ? COLORS.positive : COLORS.negative;
  // Blend toward the panel background at low intensity so small moves
  // read as muted, not full-saturation blocks.
  return blend(COLORS.bgPanelRaised, base, 0.35 + intensity * 0.65);
}

function blend(from: string, to: string, t: number): string {
  const f = hexToRgb(from);
  const target = hexToRgb(to);
  const r = Math.round(f.r + (target.r - f.r) * t);
  const g = Math.round(f.g + (target.g - f.g) * t);
  const b = Math.round(f.b + (target.b - f.b) * t);
  return `rgb(${r}, ${g}, ${b})`;
}

function hexToRgb(hex: string): { r: number; g: number; b: number } {
  const clean = hex.replace("#", "");
  const num = parseInt(clean, 16);
  return { r: (num >> 16) & 255, g: (num >> 8) & 255, b: num & 255 };
}

function HeatmapCell(props: {
  x?: number;
  y?: number;
  width?: number;
  height?: number;
  name?: string;
  pnlPercent?: number | null;
}) {
  const { x = 0, y = 0, width = 0, height = 0, name = "", pnlPercent = null } = props;
  const showLabel = width > 42 && height > 26;
  return (
    <g>
      <rect
        x={x}
        y={y}
        width={width}
        height={height}
        fill={colorFor(pnlPercent ?? null)}
        stroke={COLORS.bgBase}
        strokeWidth={2}
      />
      {showLabel && (
        <>
          <text x={x + 6} y={y + 16} fontSize={11} fontFamily={COLORS.fontMono} fill={COLORS.textPrimary}>
            {name}
          </text>
          <text x={x + 6} y={y + 30} fontSize={10} fontFamily={COLORS.fontMono} fill={COLORS.textPrimary} opacity={0.85}>
            {formatPercent(pnlPercent ?? null)}
          </text>
        </>
      )}
    </g>
  );
}

export function PortfolioHeatmap({ positions }: { positions: Position[] }) {
  const data: HeatmapDatum[] = positions
    .filter((p) => p.market_value !== null && p.market_value > 0)
    .map((p) => ({
      name: p.ticker,
      size: p.market_value as number,
      pnlPercent: p.unrealized_pnl_percent,
    }));

  return (
    <Panel title="Positions heatmap" aside={`${data.length} positions`} className="h-full" bodyClassName="p-1">
      {data.length === 0 ? (
        <div className="h-full flex items-center justify-center text-text-tertiary text-xs" data-testid="heatmap-empty">
          No open positions yet.
        </div>
      ) : (
        <ResponsiveContainer width="100%" height="100%" minHeight={140} data-testid="heatmap">
          <Treemap
            data={data}
            dataKey="size"
            aspectRatio={4 / 3}
            stroke={COLORS.bgBase}
            isAnimationActive={false}
            content={<HeatmapCell />}
          />
        </ResponsiveContainer>
      )}
    </Panel>
  );
}
