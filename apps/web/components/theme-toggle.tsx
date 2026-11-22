"use client";
// Light/dark switch. The theme is a "dark" class on <html>: the script in app/layout.tsx
// sets it before the page paints (from the saved choice, or the device setting), and
// this button flips it and remembers the choice. Which icon shows is decided by CSS,
// so the button never disagrees with the page.

import { Moon, Sun } from "lucide-react";

export function ThemeToggle() {
  function toggle() {
    const dark = document.documentElement.classList.toggle("dark");
    try {
      localStorage.setItem("theme", dark ? "dark" : "light");
    } catch {
      // Private windows can block storage; the switch still works for this visit.
    }
  }

  return (
    <button
      type="button"
      onClick={toggle}
      aria-label="Switch Between Light and Dark Mode"
      title="Light / Dark Mode"
      className="hover:bg-secondary text-muted-foreground hover:text-foreground grid size-9 place-items-center rounded-full border transition-colors"
    >
      <Moon className="size-4 dark:hidden" aria-hidden />
      <Sun className="hidden size-4 dark:block" aria-hidden />
    </button>
  );
}
