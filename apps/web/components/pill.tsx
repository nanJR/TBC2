// A small rounded status label, as in the Figma: green = done, amber = waiting,
// red = needs action, grey = neutral. An optional dot sits before the text.

import type { ReactNode } from "react";

import type { Tone } from "@/lib/labels";
import { cn } from "@/lib/utils";

const TONES: Record<Tone, string> = {
  ok: "bg-ok-soft text-ok",
  wait: "bg-wait-soft text-wait",
  alert: "bg-alert-soft text-alert",
  neutral: "bg-secondary text-muted-foreground",
};

export function Pill(props: { tone?: Tone; dot?: boolean; children: ReactNode; className?: string }) {
  const tone = props.tone ?? "neutral";
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium whitespace-nowrap",
        TONES[tone],
        props.className,
      )}
    >
      {props.dot && <span className="size-1.5 rounded-full bg-current" aria-hidden />}
      {props.children}
    </span>
  );
}
