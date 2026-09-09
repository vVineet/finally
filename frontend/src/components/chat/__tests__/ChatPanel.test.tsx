import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ChatPanel } from "../ChatPanel";
import type { DisplayChatMessage } from "@/hooks/useChat";

describe("ChatPanel loading states", () => {
  it("shows a loading indicator while chat history is being fetched", () => {
    render(<ChatPanel messages={[]} loading sending={false} onSend={jest.fn()} />);
    expect(screen.getByTestId("chat-loading-history")).toBeInTheDocument();
  });

  it("shows a sending indicator, and disables the input, while waiting on the assistant", () => {
    render(<ChatPanel messages={[]} loading={false} sending onSend={jest.fn()} />);
    expect(screen.getByTestId("chat-sending-indicator")).toHaveTextContent(/thinking/i);
    expect(screen.getByLabelText("Chat message")).toBeDisabled();
  });

  it("does not show either loading indicator once history is loaded and nothing is in flight", () => {
    render(<ChatPanel messages={[]} loading={false} sending={false} onSend={jest.fn()} />);
    expect(screen.queryByTestId("chat-loading-history")).not.toBeInTheDocument();
    expect(screen.queryByTestId("chat-sending-indicator")).not.toBeInTheDocument();
  });

  it("renders prose and execution chips as visually distinct blocks (PLAN §13.A3)", () => {
    const messages: DisplayChatMessage[] = [
      {
        id: "1",
        role: "assistant",
        content: "I'll buy 10 AAPL at the current price.",
        actions: {
          trades: [{ ticker: "AAPL", side: "buy", quantity: 10, price: 200, status: "success" }],
        },
        created_at: "2026-09-08T12:00:00+00:00",
      },
    ];
    render(<ChatPanel messages={messages} loading={false} sending={false} onSend={jest.fn()} />);
    expect(screen.getByText(/I'll buy 10 AAPL/)).toBeInTheDocument();
    expect(screen.getByTestId("trade-chip-success")).toHaveTextContent("Bought 10 AAPL @ $200.00");
  });

  it("makes a failed trade unmistakable", () => {
    const messages: DisplayChatMessage[] = [
      {
        id: "1",
        role: "assistant",
        content: "I'll sell 1000 TSLA.",
        actions: {
          trades: [
            {
              ticker: "TSLA",
              side: "sell",
              quantity: 1000,
              status: "failed",
              error: "Insufficient shares: requested 1000, held 0",
            },
          ],
        },
        created_at: "2026-09-08T12:00:00+00:00",
      },
    ];
    render(<ChatPanel messages={messages} loading={false} sending={false} onSend={jest.fn()} />);
    const chip = screen.getByTestId("trade-chip-failed");
    expect(chip).toHaveTextContent(/failed/i);
    expect(chip).toHaveTextContent("Insufficient shares");
  });

  it("calls onSend with the trimmed draft and clears the input", async () => {
    const onSend = jest.fn().mockResolvedValue(undefined);
    const user = userEvent.setup();
    render(<ChatPanel messages={[]} loading={false} sending={false} onSend={onSend} />);

    await user.type(screen.getByLabelText("Chat message"), "  how's my portfolio?  ");
    await user.click(screen.getByTestId("chat-send-button"));

    expect(onSend).toHaveBeenCalledWith("how's my portfolio?");
  });
});
