import { render, screen } from "@testing-library/react";
import { PositionsTable } from "../PositionsTable";
import type { Position } from "@/lib/types";

const positions: Position[] = [
  {
    ticker: "AAPL",
    quantity: 10,
    avg_cost: 200,
    current_price: 212,
    market_value: 2120,
    unrealized_pnl: 120,
    unrealized_pnl_percent: 6,
    updated_at: "2026-09-08T12:00:00+00:00",
  },
  {
    // Just-added ticker with no cached price yet — B6: null, not 0.
    ticker: "PYPL",
    quantity: 5,
    avg_cost: 60,
    current_price: null,
    market_value: null,
    unrealized_pnl: null,
    unrealized_pnl_percent: null,
    updated_at: "2026-09-08T12:00:00+00:00",
  },
];

describe("PositionsTable", () => {
  it("renders positions with mock data", () => {
    render(<PositionsTable positions={positions} />);
    expect(screen.getByTestId("position-row-AAPL")).toHaveTextContent("AAPL");
    expect(screen.getByTestId("position-row-AAPL")).toHaveTextContent("$120.00");
  });

  it("renders a placeholder, never $0.00, for a position with no cached price", () => {
    render(<PositionsTable positions={positions} />);
    const row = screen.getByTestId("position-row-PYPL");
    expect(row.textContent).not.toContain("$0.00");
    expect(row.textContent).toContain("—");
  });

  it("renders an empty state with no positions", () => {
    render(<PositionsTable positions={[]} />);
    expect(screen.getByText(/no open positions/i)).toBeInTheDocument();
  });
});
