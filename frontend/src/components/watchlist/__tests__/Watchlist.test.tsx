import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Watchlist } from "../Watchlist";
import { ApiError } from "@/lib/types";
import type { WatchlistEntry } from "@/lib/types";

jest.mock("@/lib/api", () => ({
  api: {
    get: jest.fn().mockResolvedValue({ ticker: "AAPL", points: [] }),
    post: jest.fn(),
    del: jest.fn(),
  },
}));

const watchlist: WatchlistEntry[] = [
  { ticker: "AAPL", added_at: "2026-09-08T00:00:00+00:00" },
  { ticker: "GOOGL", added_at: "2026-09-08T00:00:00+00:00" },
];

describe("Watchlist CRUD", () => {
  it("renders every watchlist entry", () => {
    render(
      <Watchlist
        watchlist={watchlist}
        prices={{}}
        flashes={{}}
        selectedTicker={null}
        onSelectTicker={jest.fn()}
        onAdd={jest.fn()}
        onRemove={jest.fn()}
      />
    );
    expect(screen.getByTestId("watchlist-row-AAPL")).toBeInTheDocument();
    expect(screen.getByTestId("watchlist-row-GOOGL")).toBeInTheDocument();
  });

  it("calls onAdd with the uppercased, trimmed ticker and clears the input", async () => {
    const onAdd = jest.fn().mockResolvedValue(undefined);
    const user = userEvent.setup();
    render(
      <Watchlist
        watchlist={watchlist}
        prices={{}}
        flashes={{}}
        selectedTicker={null}
        onSelectTicker={jest.fn()}
        onAdd={onAdd}
        onRemove={jest.fn()}
      />
    );

    await user.type(screen.getByLabelText(/add ticker/i), "  pypl  ");
    await user.click(screen.getByRole("button", { name: "Add" }));

    expect(onAdd).toHaveBeenCalledWith("PYPL");
    await waitFor(() => expect(screen.getByLabelText(/add ticker/i)).toHaveValue(""));
  });

  it("shows an error and keeps the input when onAdd rejects", async () => {
    const onAdd = jest.fn().mockRejectedValue(new ApiError(400, "Invalid ticker format: nope"));
    const user = userEvent.setup();
    render(
      <Watchlist
        watchlist={watchlist}
        prices={{}}
        flashes={{}}
        selectedTicker={null}
        onSelectTicker={jest.fn()}
        onAdd={onAdd}
        onRemove={jest.fn()}
      />
    );

    await user.type(screen.getByLabelText(/add ticker/i), "???");
    await user.click(screen.getByRole("button", { name: "Add" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Invalid ticker format");
  });

  it("calls onRemove with the ticker when its remove button is clicked", async () => {
    const onRemove = jest.fn().mockResolvedValue(undefined);
    const user = userEvent.setup();
    render(
      <Watchlist
        watchlist={watchlist}
        prices={{}}
        flashes={{}}
        selectedTicker={null}
        onSelectTicker={jest.fn()}
        onAdd={jest.fn()}
        onRemove={onRemove}
      />
    );

    await user.click(screen.getByLabelText("Remove AAPL from watchlist"));
    expect(onRemove).toHaveBeenCalledWith("AAPL");
  });

  it("calls onSelectTicker when a row is clicked", async () => {
    const onSelectTicker = jest.fn();
    const user = userEvent.setup();
    render(
      <Watchlist
        watchlist={watchlist}
        prices={{}}
        flashes={{}}
        selectedTicker={null}
        onSelectTicker={onSelectTicker}
        onAdd={jest.fn()}
        onRemove={jest.fn()}
      />
    );

    await user.click(screen.getByTestId("watchlist-row-GOOGL"));
    expect(onSelectTicker).toHaveBeenCalledWith("GOOGL");
  });

  it("renders an empty state with no watchlist entries", () => {
    render(
      <Watchlist
        watchlist={[]}
        prices={{}}
        flashes={{}}
        selectedTicker={null}
        onSelectTicker={jest.fn()}
        onAdd={jest.fn()}
        onRemove={jest.fn()}
      />
    );
    expect(screen.getByText(/no tickers yet/i)).toBeInTheDocument();
  });
});
