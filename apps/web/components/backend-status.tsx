"use client";
// "use client" means this component runs in the browser, so it can use
// state (useState) and react to clicks. Pages without it run on the server.

import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { checkHealth, screenMock, type ScreenResult } from "@/lib/api";

type Status = "checking" | "up" | "down";

export function BackendStatus() {
  const [status, setStatus] = useState<Status>("checking");
  const [result, setResult] = useState<ScreenResult | null>(null);

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

      <Button
        disabled={status !== "up"}
        onClick={() => screenMock().then(setResult)}
        className="self-start"
      >
        Try a mock screening
      </Button>

      {result && (
        <p className="text-sm">
          TB risk score: <strong>{Math.round(result.risk_score * 100)}%</strong>
          {result.is_mock && " (fake number, models not trained yet)"}
        </p>
      )}
    </div>
  );
}
