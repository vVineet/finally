"use client";

import { useEffect, useRef, useState } from "react";
import { Panel } from "@/components/common/Panel";
import type { DisplayChatMessage } from "@/hooks/useChat";
import { ChatMessageBubble } from "./ChatMessageBubble";

export function ChatPanel({
  messages,
  loading,
  sending,
  onSend,
}: {
  messages: DisplayChatMessage[];
  loading: boolean;
  sending: boolean;
  onSend: (content: string) => Promise<void>;
}) {
  const [draft, setDraft] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // jsdom (unit tests) doesn't implement Element.scrollTo — guard so
    // tests don't need to stub it just to render the panel.
    scrollRef.current?.scrollTo?.({ top: scrollRef.current.scrollHeight });
  }, [messages, sending]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    const content = draft.trim();
    if (!content || sending) return;
    setDraft("");
    await onSend(content);
  };

  return (
    <Panel
      title="AI assistant"
      aside={
        <span className="flex items-center gap-1">
          <span className="cursor-blink text-accent-yellow">_</span>
        </span>
      }
      className="h-full"
      bodyClassName="flex flex-col"
    >
      <div ref={scrollRef} className="flex-1 overflow-auto px-3 py-3 flex flex-col gap-3" data-testid="chat-history">
        {loading && (
          <div className="text-text-tertiary text-xs" data-testid="chat-loading-history">
            Loading conversation…
          </div>
        )}
        {!loading && messages.length === 0 && (
          <div className="text-text-tertiary text-xs">
            Ask FinAlly about your portfolio, or tell it to make a trade.
          </div>
        )}
        {messages.map((m) => (
          <ChatMessageBubble key={m.id} message={m} />
        ))}
        {sending && (
          <div className="flex items-center gap-1.5 text-text-tertiary text-xs" data-testid="chat-sending-indicator">
            <span className="cursor-blink">●</span>
            <span>Thinking…</span>
          </div>
        )}
      </div>
      <form onSubmit={submit} className="flex gap-1.5 px-3 py-2 border-t border-border-subtle shrink-0">
        <input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="Ask FinAlly…"
          aria-label="Chat message"
          disabled={sending}
          className="flex-1 min-w-0 bg-bg-input border border-border rounded-sm px-2 py-1.5 text-xs text-text-primary placeholder:text-text-tertiary focus:outline-none focus:border-accent-blue disabled:opacity-60"
        />
        <button
          type="submit"
          disabled={sending || !draft.trim()}
          data-testid="chat-send-button"
          className="px-3 py-1.5 text-xs font-semibold rounded-sm bg-accent-purple text-white disabled:opacity-40 disabled:cursor-not-allowed"
        >
          Send
        </button>
      </form>
    </Panel>
  );
}
