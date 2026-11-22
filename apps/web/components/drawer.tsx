"use client";
// A panel that slides over the right side of the page, for one case or patient.
// Click outside it or press Escape to close.

import { useEffect, type ReactNode } from "react";
import { X } from "lucide-react";

export function Drawer(props: {
  title: ReactNode;
  subtitle?: ReactNode;
  onClose: () => void;
  children: ReactNode;
}) {
  const { onClose } = props;
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div className="fixed inset-0 z-30 flex justify-end">
      <button
        type="button"
        aria-label="Close"
        className="absolute inset-0 bg-black/30 backdrop-blur-[1px]"
        onClick={onClose}
      />
      <aside
        role="dialog"
        aria-modal="true"
        className="bg-card relative flex h-full w-full max-w-xl flex-col overflow-y-auto border-l shadow-2xl"
      >
        <div className="bg-card/95 sticky top-0 z-10 flex items-start justify-between gap-4 border-b px-6 py-4 backdrop-blur">
          <div>
            <div className="text-lg font-semibold">{props.title}</div>
            {props.subtitle && (
              <div className="text-muted-foreground text-sm">{props.subtitle}</div>
            )}
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="hover:bg-secondary grid size-9 place-items-center rounded-full"
          >
            <X className="size-4" />
          </button>
        </div>
        <div className="flex flex-col gap-6 px-6 py-5">{props.children}</div>
      </aside>
    </div>
  );
}
