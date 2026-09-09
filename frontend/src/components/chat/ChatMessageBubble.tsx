import type { DisplayChatMessage } from "@/hooks/useChat";
import { formatTime } from "@/lib/format";
import { ActionChips } from "./ActionChips";

export function ChatMessageBubble({ message }: { message: DisplayChatMessage }) {
  const isUser = message.role === "user";
  return (
    <div className={`flex flex-col ${isUser ? "items-end" : "items-start"}`} data-testid="chat-message" data-role={message.role}>
      <div
        className={`max-w-[85%] rounded-sm px-2.5 py-1.5 text-xs leading-relaxed ${
          isUser
            ? "bg-accent-blue/15 border border-accent-blue/40 text-text-primary"
            : message.isError
              ? "bg-negative/10 border border-negative/40 text-negative"
              : "bg-bg-panel-raised border border-border text-text-primary"
        }`}
      >
        {message.content}
        {!isUser && <ActionChips actions={message.actions} />}
      </div>
      <span className="text-[10px] text-text-tertiary mt-0.5">{formatTime(message.created_at)}</span>
    </div>
  );
}
