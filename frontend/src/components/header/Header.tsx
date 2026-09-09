import { ConnectionDot } from "@/components/common/ConnectionDot";
import { formatCurrency } from "@/lib/format";
import type { ConnectionStatus } from "@/lib/types";

export function Header({
  totalValue,
  cashBalance,
  status,
  onReset,
}: {
  totalValue: number | null;
  cashBalance: number | null;
  status: ConnectionStatus;
  onReset: () => void;
}) {
  return (
    <header className="flex items-center justify-between px-4 h-14 shrink-0 border-b border-border bg-bg-panel">
      <div className="flex items-baseline gap-1 select-none">
        <span className="font-data text-lg font-bold tracking-tight text-text-primary">FIN</span>
        <span className="font-data text-lg font-bold text-accent-yellow cursor-blink">|</span>
        <span className="font-data text-lg font-bold tracking-tight text-text-primary">ALLY</span>
      </div>

      <div className="flex items-center gap-6">
        <div className="flex flex-col items-end">
          <span className="text-[10px] text-text-tertiary uppercase tracking-wide">Total value</span>
          <span className="font-data text-base font-semibold text-text-primary" data-testid="header-total-value">
            {formatCurrency(totalValue)}
          </span>
        </div>
        <div className="flex flex-col items-end">
          <span className="text-[10px] text-text-tertiary uppercase tracking-wide">Cash</span>
          <span className="font-data text-sm text-text-secondary" data-testid="header-cash-balance">
            {formatCurrency(cashBalance)}
          </span>
        </div>
        <button
          type="button"
          onClick={onReset}
          className="text-[11px] text-text-tertiary hover:text-negative border border-border rounded-sm px-2 py-1"
          title="Reset portfolio to $10,000 and defaults"
        >
          Reset
        </button>
        <ConnectionDot status={status} />
      </div>
    </header>
  );
}
