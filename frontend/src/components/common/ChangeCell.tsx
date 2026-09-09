import { formatPercent } from "@/lib/format";

/**
 * "Chg %" column. PLAN §13.A1: this must be the day-change field (against
 * a per-ticker open price captured at first tick this process), never
 * the tick-over-tick `change_percent` (which jitters ±0.05%). The label
 * says "Chg %" rather than "Today" or "Daily" -- per the coordinator's
 * guidance this is since-process-start, not a real trading-day move, and
 * the simulator has no true previous close to reference.
 */
export function ChangeCell({ percent, className = "" }: { percent: number | null | undefined; className?: string }) {
  const tone =
    percent === null || percent === undefined
      ? "text-text-tertiary"
      : percent > 0
        ? "text-positive"
        : percent < 0
          ? "text-negative"
          : "text-text-secondary";
  return (
    <span className={`font-data ${tone} ${className}`} data-testid="change-cell">
      {formatPercent(percent)}
    </span>
  );
}
