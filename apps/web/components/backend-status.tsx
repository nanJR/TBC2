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
    <div className="flex flex-col gap-4">
      <p className="text-sm">
        Back end:{" "}
        {status === "checking" && <span>checking…</span>}
        {status === "up" && <span className="font-medium text-green-700">running</span>}
        {status === "down" && (
          <span className="font-medium text-red-700">
            not reachable (start it with <code>uv run fastapi dev app/main.py</code>)
          </span>
        )}
      </p>
    </div>
  );
}
