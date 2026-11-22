// A white card with a title, as used across both portals (the Figma's three columns).

import type { ReactNode } from "react";

export function Panel(props: {
  title: string;
  subtitle?: string;
  right?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section className="bg-card flex flex-col rounded-2xl border p-6">
      <div className="mb-5 flex items-start justify-between gap-3">
        <div>
          <h2 className="font-semibold">{props.title}</h2>
          {props.subtitle && <p className="text-muted-foreground text-sm">{props.subtitle}</p>}
        </div>
        {props.right}
      </div>
      {props.children}
    </section>
  );
}

/** The small count pill in a panel's corner, e.g. "3 Waiting". */
export function CountPill({ children }: { children: ReactNode }) {
  return (
    <span className="bg-accent text-accent-foreground rounded-full px-2.5 py-1 text-xs font-medium whitespace-nowrap">
      {children}
    </span>
  );
}
