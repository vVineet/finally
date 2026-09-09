import { act, render, screen } from "@testing-library/react";
import { usePriceStream } from "../usePriceStream";
import { emitPriceMap, getLatestEventSource } from "@/test-utils/mockEventSource";

function Harness() {
  const { prices, status, flashes } = usePriceStream();
  return (
    <div>
      <div data-testid="status">{status}</div>
      <div data-testid="aapl-price">{prices.AAPL?.price ?? "none"}</div>
      <div data-testid="aapl-flash">{flashes.AAPL ?? "none"}</div>
    </div>
  );
}

const baseTick = (overrides: Partial<Record<string, unknown>> = {}) => ({
  ticker: "AAPL",
  price: 190,
  previous_price: 190,
  timestamp: 1000,
  change: 0,
  change_percent: 0,
  direction: "flat",
  ...overrides,
});

describe("usePriceStream", () => {
  beforeEach(() => {
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  it("parses the map-of-tickers SSE payload (PLAN §13.A2) and exposes connected status", () => {
    render(<Harness />);
    const source = getLatestEventSource();

    act(() => {
      source.onopen?.(new Event("open"));
    });
    expect(screen.getByTestId("status")).toHaveTextContent("connected");

    act(() => {
      emitPriceMap({ AAPL: baseTick({ price: 191, previous_price: 190 }) });
    });
    expect(screen.getByTestId("aapl-price")).toHaveTextContent("191");
  });

  it("flashes up on an increase and clears the flash after ~500ms", () => {
    render(<Harness />);

    act(() => {
      emitPriceMap({ AAPL: baseTick({ price: 190, previous_price: 190 }) });
    });
    expect(screen.getByTestId("aapl-flash")).toHaveTextContent("none");

    act(() => {
      emitPriceMap({ AAPL: baseTick({ price: 195, previous_price: 190, direction: "up" }) });
    });
    expect(screen.getByTestId("aapl-flash")).toHaveTextContent("up");

    act(() => {
      jest.advanceTimersByTime(500);
    });
    expect(screen.getByTestId("aapl-flash")).toHaveTextContent("none");
  });

  it("flashes down on a decrease", () => {
    render(<Harness />);

    act(() => {
      emitPriceMap({ AAPL: baseTick({ price: 190, previous_price: 190 }) });
    });
    act(() => {
      emitPriceMap({ AAPL: baseTick({ price: 180, previous_price: 190, direction: "down" }) });
    });
    expect(screen.getByTestId("aapl-flash")).toHaveTextContent("down");
  });

  it("reports disconnected once the EventSource is CLOSED", () => {
    render(<Harness />);
    const source = getLatestEventSource();
    act(() => {
      source.close();
      source.onerror?.(new Event("error"));
    });
    expect(screen.getByTestId("status")).toHaveTextContent("disconnected");
  });
});
