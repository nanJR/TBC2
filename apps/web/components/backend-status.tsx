"use client";
// "use client" means this component runs in the browser, so it can use
// state (useState) and react to clicks. Pages without it run on the server.

import { useEffect, useState } from "react";

import { checkHealth } from "@/lib/api";

type Status = "checking" | "waking" | "up" | "down";

// The hosted API (Render free plan) sleeps when idle and takes up to about a minute to
// wake. So if the first check fails, keep asking every few seconds before giving up.
const RETRY_EVERY_MS = 5_000;
const GIVE_UP_AFTER_MS = 120_000;

export function BackendStatus() {
  const [status, setStatus] = useState<Status>("checking");

  // Runs once when the component first appears on screen. These checks also wake the API.
  useEffect(() => {
    let stopped = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const started = Date.now();

    async function check() {
      const ok = await checkHealth();
      if (stopped) return;
      if (ok) {
        setStatus("up");
      } else if (Date.now() - started < GIVE_UP_AFTER_MS) {
        setStatus("waking");
        timer = setTimeout(check, RETRY_EVERY_MS);
      } else {
        setStatus("down");
      }
    }

    check();
    return () => {
      stopped = true;
      clearTimeout(timer);
    };
  }, []);

  return (
    // A small pill: green dot when the API answers, red when it doesn't.
    <span
      className="bg-card text-muted-foreground inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-xs"
      title={status === "down" ? "Start it with: uv run fastapi dev app/main.py" : undefined}
    >
      <span
        aria-hidden
        className={`size-2 rounded-full ${
          status === "up"
            ? "bg-ok"
            : status === "down"
              ? "bg-alert"
              : status === "waking"
                ? "bg-wait animate-pulse"
                : "bg-muted-foreground"
        }`}
      />
      Back End:{" "}
      {status === "checking" && "Checking…"}
      {status === "waking" && <span className="text-wait font-medium">Waking Up…</span>}
      {status === "up" && <span className="text-ok font-medium">Running</span>}
      {status === "down" && <span className="text-alert font-medium">Not Reachable</span>}
    </span>
  );
}
