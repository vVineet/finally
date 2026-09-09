import type { ConnectionStatus } from "@/lib/types";

const STATUS_META: Record<ConnectionStatus, { color: string; label: string; pulse?: boolean }> = {
  connected: { color: "var(--positive)", label: "Connected" },
  connecting: { color: "var(--accent-yellow)", label: "Connecting", pulse: true },
  reconnecting: { color: "var(--accent-yellow)", label: "Reconnecting", pulse: true },
  disconnected: { color: "var(--negative)", label: "Disconnected" },
};

export function ConnectionDot({ status }: { status: ConnectionStatus }) {
  const meta = STATUS_META[status];
  return (
    <div className="flex items-center gap-1.5" data-testid="connection-status" data-status={status}>
      <span
        className={`inline-block h-2 w-2 rounded-full ${meta.pulse ? "animate-pulse" : ""}`}
        style={{ backgroundColor: meta.color }}
        aria-hidden
      />
      <span className="text-[11px] text-text-secondary">{meta.label}</span>
    </div>
  );
}
