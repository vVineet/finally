import { render, screen } from "@testing-library/react";
import { PriceCell } from "../PriceCell";
import { NULL_PLACEHOLDER } from "@/lib/format";

describe("PriceCell", () => {
  it("renders a formatted price", () => {
    render(<PriceCell price={190.5} />);
    expect(screen.getByTestId("price-cell")).toHaveTextContent("190.50");
  });

  it("renders the null placeholder, never $0.00, when price is null (B6)", () => {
    render(<PriceCell price={null} />);
    const cell = screen.getByTestId("price-cell");
    expect(cell).toHaveTextContent(NULL_PLACEHOLDER);
    expect(cell).not.toHaveTextContent("0.00");
  });

  it("applies the up-flash class when flash='up'", () => {
    render(<PriceCell price={190.5} flash="up" />);
    expect(screen.getByTestId("price-cell")).toHaveClass("price-flash-up");
  });

  it("applies the down-flash class when flash='down'", () => {
    render(<PriceCell price={190.5} flash="down" />);
    expect(screen.getByTestId("price-cell")).toHaveClass("price-flash-down");
  });

  it("applies no flash class when flash is unset", () => {
    render(<PriceCell price={190.5} />);
    expect(screen.getByTestId("price-cell")).toHaveClass("price-flash-none");
  });
});
