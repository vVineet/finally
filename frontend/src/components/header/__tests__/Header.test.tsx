import { render, screen } from "@testing-library/react";
import { Header } from "../Header";

describe("Header", () => {
  it("renders the live total value and cash balance", () => {
    render(<Header totalValue={10482.3} cashBalance={6200.1} status="connected" onReset={jest.fn()} />);
    expect(screen.getByTestId("header-total-value")).toHaveTextContent("$10,482.30");
    expect(screen.getByTestId("header-cash-balance")).toHaveTextContent("$6,200.10");
  });

  it("renders the placeholder rather than $0.00 before the first portfolio load", () => {
    render(<Header totalValue={null} cashBalance={null} status="connecting" onReset={jest.fn()} />);
    expect(screen.getByTestId("header-total-value")).toHaveTextContent("—");
  });

  it.each([
    ["connected", "Connected"],
    ["connecting", "Connecting"],
    ["reconnecting", "Reconnecting"],
    ["disconnected", "Disconnected"],
  ] as const)("shows the %s connection status as %s", (status, label) => {
    render(<Header totalValue={0} cashBalance={0} status={status} onReset={jest.fn()} />);
    expect(screen.getByTestId("connection-status")).toHaveAttribute("data-status", status);
    expect(screen.getByTestId("connection-status")).toHaveTextContent(label);
  });
});
