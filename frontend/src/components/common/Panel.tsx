import type { ReactNode } from "react";

export function Panel({
  title,
  aside,
  children,
  className = "",
  bodyClassName = "",
}: {
  title: string;
  aside?: ReactNode;
  children: ReactNode;
  className?: string;
  bodyClassName?: string;
}) {
  return (
    <section className={`flex flex-col min-h-0 border border-border bg-bg-panel ${className}`}>
      <header className="flex items-center justify-between shrink-0 px-3 py-1.5 border-b border-border-subtle">
        <h2 className="text-[11px] tracking-wide uppercase text-text-secondary font-semibold">{title}</h2>
        {aside && <div className="text-[11px] text-text-tertiary">{aside}</div>}
      </header>
      <div className={`flex-1 min-h-0 overflow-auto ${bodyClassName}`}>{children}</div>
    </section>
  );
}
