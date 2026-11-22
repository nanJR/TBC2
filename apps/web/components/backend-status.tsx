"use client";
// "use client" means this component runs in the browser, so it can use
// state (useState) and react to clicks. Pages without it run on the server.

import { useEffect, useState } from "react";

import { checkHealth } from "@/lib/api";

type Status = "checking" | "up" | "down";

export function BackendStatus() {
  const [status, setStatus] = useState<Status>("checking");

  // Runs once when the component first appears on screen.
  useEffect(() => {
    checkHealth().then((ok) => setStatus(ok ? "up" : "down"));
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
          status === "up" ? "bg-ok" : status === "down" ? "bg-alert" : "bg-muted-foreground"
        }`}
      />
      Back End:{" "}
      {status === "checking" && "Checking…"}
      {status === "up" && <span className="text-ok font-medium">Running</span>}
      {status === "down" && <span className="text-alert font-medium">Not Reachable</span>}
    </span>
  );
}
