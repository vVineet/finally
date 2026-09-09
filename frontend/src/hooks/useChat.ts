"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { ApiError } from "@/lib/types";
import type { ChatHistoryResponse, ChatMessage, ChatSendResponse, Portfolio, WatchlistEntry } from "@/lib/types";

// Local-only extension: messages synthesized on the client (the optimistic
// user echo, and a transport/backend-error notice) are flagged distinctly
// from ones that round-tripped through the server, so the chat panel can
// style a failed send differently from a normal assistant reply.
export interface DisplayChatMessage extends ChatMessage {
  isError?: boolean;
}

export interface UseChatOptions {
  onApplied?: (portfolio: Portfolio, watchlist: WatchlistEntry[]) => void;
}

export function useChat(options?: UseChatOptions) {
  const [messages, setMessages] = useState<DisplayChatMessage[]>([]);
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await api.get<ChatHistoryResponse>("/api/chat/history");
        if (!cancelled) setMessages(res.messages);
      } catch (e) {
        if (!cancelled) setError(e instanceof ApiError ? e.message : "Failed to load chat history");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const send = useCallback(
    async (content: string) => {
      const trimmed = content.trim();
      if (!trimmed) return;

      const userMsg: DisplayChatMessage = {
        id: `local-user-${Date.now()}`,
        role: "user",
        content: trimmed,
        actions: null,
        created_at: new Date().toISOString(),
      };
      setMessages((m) => [...m, userMsg]);
      setSending(true);
      setError(null);

      try {
        const res = await api.post<ChatSendResponse>("/api/chat", { message: trimmed });
        const assistantMsg: DisplayChatMessage = {
          id: `local-assistant-${Date.now()}`,
          role: "assistant",
          content: res.message,
          actions: {
            trades: [...res.trades_executed, ...res.trades_failed],
            watchlist: res.watchlist_changes,
          },
          created_at: new Date().toISOString(),
        };
        setMessages((m) => [...m, assistantMsg]);
        options?.onApplied?.(res.portfolio, res.watchlist);
      } catch (e) {
        const detail = e instanceof ApiError ? e.message : "Could not reach the assistant. Try again.";
        setMessages((m) => [
          ...m,
          {
            id: `local-error-${Date.now()}`,
            role: "assistant",
            content: detail,
            actions: null,
            created_at: new Date().toISOString(),
            isError: true,
          },
        ]);
        setError(detail);
      } finally {
        setSending(false);
      }
    },
    [options]
  );

  return { messages, loading, sending, error, send };
}
