"use client";
// ASHA screening flow: record a cough, optionally add an X-ray photo, get a risk score.
// The (asha) folder name is in brackets so it groups pages without adding to the URL:
// this page lives at /screen, not /asha/screen.

import Link from "next/link";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { screenMock, type ScreenResult } from "@/lib/api";

const RECORD_SECONDS = 5;

export default function ScreenPage() {
  const [recording, setRecording] = useState(false);
  const [coughUrl, setCoughUrl] = useState<string | null>(null);
  const [xray, setXray] = useState<File | null>(null);
  const [result, setResult] = useState<ScreenResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function recordCough() {
    setError(null);
    try {
      // Ask the browser for the microphone. The user sees a permission popup.
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      const chunks: Blob[] = [];
      recorder.ondataavailable = (e) => chunks.push(e.data);
      recorder.onstop = () => {
        stream.getTracks().forEach((t) => t.stop()); // turn the mic off
        setCoughUrl(URL.createObjectURL(new Blob(chunks, { type: recorder.mimeType })));
        setRecording(false);
      };
      recorder.start();
      setRecording(true);
      setTimeout(() => recorder.stop(), RECORD_SECONDS * 1000);
    } catch {
      setError("Could not use the microphone. Check the browser's permission.");
    }
  }

  async function getScore() {
    setError(null);
    try {
      // TODO (Weeks 5-7): upload the cough clip and X-ray instead of calling the mock.
      setResult(await screenMock());
    } catch {
      setError("Could not reach the back end.");
    }
  }

  return (
    <main className="mx-auto flex w-full max-w-md flex-1 flex-col gap-4 px-4 py-8">
      <Link href="/" className="text-muted-foreground text-sm">
        ← Home
      </Link>
      <h1 className="text-2xl font-semibold">TB screening</h1>

      <Card>
        <CardHeader>
          <CardTitle>1. Record a cough</CardTitle>
          <CardDescription>Ask the person to cough a few times. Recording stops after {RECORD_SECONDS} seconds.</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          <Button size="lg" onClick={recordCough} disabled={recording}>
            {recording ? "Recording…" : coughUrl ? "Record again" : "Start recording"}
          </Button>
          {coughUrl && <audio controls src={coughUrl} className="w-full" />}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>2. Chest X-ray (optional)</CardTitle>
          <CardDescription>Take a clear photo of the X-ray film, or pick an image file.</CardDescription>
        </CardHeader>
        <CardContent>
          <input
            type="file"
            accept="image/*"
            capture="environment"
            onChange={(e) => setXray(e.target.files?.[0] ?? null)}
            className="text-sm"
          />
          {xray && <p className="text-muted-foreground mt-2 text-sm">Selected: {xray.name}</p>}
        </CardContent>
      </Card>

      <Button size="lg" onClick={getScore} disabled={!coughUrl}>
        Get TB risk score
      </Button>

      {error && <p className="text-destructive text-sm">{error}</p>}

      {result && (
        <Card>
          <CardHeader>
            <CardTitle>Risk score: {Math.round(result.risk_score * 100)}%</CardTitle>
            <CardDescription>
              {result.is_mock
                ? "This is a fake number. The models are not trained yet."
                : "Refer for a confirmatory test if the score is high."}
            </CardDescription>
          </CardHeader>
        </Card>
      )}
    </main>
  );
}
