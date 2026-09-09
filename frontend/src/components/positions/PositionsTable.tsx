import { Panel } from "@/components/common/Panel";
import { formatCurrency, formatPercent, formatPrice, formatQuantity, NULL_PLACEHOLDER } from "@/lib/format";
import type { Position } from "@/lib/types";

export function PositionsTable({ positions }: { positions: Position[] }) {
  return (
    <Panel title="Positions" aside={`${positions.length} open`} bodyClassName="p-0">
      <table className="w-full text-xs font-data" data-testid="positions-table">
        <thead className="sticky top-0 bg-bg-panel">
          <tr className="text-text-tertiary text-[10px] uppercase tracking-wide font-sans">
            <th className="text-left font-semibold px-3 py-1.5">Ticker</th>
            <th className="text-right font-semibold px-3 py-1.5">Qty</th>
            <th className="text-right font-semibold px-3 py-1.5">Avg cost</th>
            <th className="text-right font-semibold px-3 py-1.5">Price</th>
            <th className="text-right font-semibold px-3 py-1.5">P&amp;L</th>
            <th className="text-right font-semibold px-3 py-1.5">P&amp;L %</th>
          </tr>
        </thead>
        <tbody>
          {positions.length === 0 && (
            <tr>
              <td colSpan={6} className="px-3 py-4 text-text-tertiary text-center font-sans">
                No open positions — buy something with the trade bar below.
              </td>
            </tr>
          )}
          {positions.map((p) => {
            const pnlTone =
              p.unrealized_pnl === null ? "text-text-tertiary" : p.unrealized_pnl > 0 ? "text-positive" : p.unrealized_pnl < 0 ? "text-negative" : "text-text-secondary";
            return (
              <tr key={p.ticker} className="border-t border-border-subtle hover:bg-bg-panel-raised/40" data-testid={`position-row-${p.ticker}`}>
                <td className="px-3 py-1.5 text-left font-semibold text-text-primary">{p.ticker}</td>
                <td className="px-3 py-1.5 text-right">{formatQuantity(p.quantity)}</td>
                <td className="px-3 py-1.5 text-right">{formatCurrency(p.avg_cost)}</td>
                <td className="px-3 py-1.5 text-right">{p.current_price === null ? NULL_PLACEHOLDER : formatPrice(p.current_price)}</td>
                <td className={`px-3 py-1.5 text-right ${pnlTone}`}>{formatCurrency(p.unrealized_pnl)}</td>
                <td className={`px-3 py-1.5 text-right ${pnlTone}`}>{formatPercent(p.unrealized_pnl_percent)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </Panel>
  );
}
