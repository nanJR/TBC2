"use client";
// ASHA screening flow: record who this is, their symptoms, a cough and an optional X-ray.
// The (asha) folder name is in brackets so it groups pages without adding to the URL:
// this page lives at /screen, not /asha/screen.
//
// The questions come from the TB Mukt Bharat Abhiyaan 2026 document. Symptoms always lead
// to a test, whatever the models say. A model can add a referral but never cancel one.

import Link from "next/link";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { recordingToWav } from "@/lib/audio";
import {
  screen,
  type ModelScore,
  type ScreenResult,
  type Symptom,
  type Vulnerability,
} from "@/lib/api";

const RECORD_SECONDS = 5;

const SYMPTOMS: { value: Symptom; label: string }[] = [
  { value: "cough_over_2_weeks", label: "Cough for more than 2 weeks" },
  { value: "cough_under_2_weeks", label: "Cough for less than 2 weeks" },
  { value: "fever", label: "Fever" },
  { value: "night_sweats", label: "Night sweats" },
  { value: "coughing_blood", label: "Coughing up blood" },
  { value: "chest_pain", label: "Chest pain" },
  { value: "shortness_of_breath", label: "Shortness of breath" },
  { value: "weight_loss", label: "Weight loss" },
  { value: "loss_of_appetite", label: "Loss of appetite" },
  { value: "fatigue", label: "Fatigue" },
  { value: "lymph_node_swelling", label: "Swelling in the neck or other glands" },
];

const VULNERABILITIES: { value: Vulnerability; label: string }[] = [
  { value: "underweight", label: "Underweight (BMI under 18.5)" },
  { value: "diabetes", label: "Diabetes" },
  { value: "hiv", label: "HIV" },
  { value: "smoker", label: "Smokes" },
  { value: "alcohol_use", label: "Drinks alcohol regularly" },
  { value: "past_tb", label: "Had TB before" },
  { value: "household_contact", label: "Lives with someone who has TB" },
];

const NEXT_STEP = {
  naat: {
    title: "Send for a NAAT test",
    detail: "Collect a sputum sample and arrange the test. Only a test can confirm TB.",
  },
  offer_xray: {
    title: "Offer a chest X-ray",
    detail: "This person has no symptoms but is at higher risk of TB.",
  },
  routine_care: {
    title: "No referral from this screen",
    detail: "Ask them to come back if any symptom appears.",
  },
};

function toggled<T>(list: T[], item: T): T[] {
  return list.includes(item) ? list.filter((x) => x !== item) : [...list, item];
}

function Checklist<T extends string>(props: {
  options: { value: T; label: string }[];
  selected: T[];
  onChange: (next: T[]) => void;
}) {
  return (
    <div className="flex flex-col gap-3">
      {props.options.map((option) => (
        <label key={option.value} className="flex items-center gap-3 text-sm">
          <input
            type="checkbox"
            className="size-5"
            checked={props.selected.includes(option.value)}
            onChange={() => props.onChange(toggled(props.selected, option.value))}
          />
          {option.label}
        </label>
      ))}
    </div>
  );
}

function ScoreLine({ name, result }: { name: string; result: ModelScore }) {
  return (
    <div className="text-sm">
      <p className="font-medium">
        {name}: {result.flagged ? "flagged" : "not flagged"} (score{" "}
        {Math.round(result.score * 100)}%)
      </p>
      <p className="text-muted-foreground">{result.note}</p>
    </div>
  );
}

export default function ScreenPage() {
  const [age, setAge] = useState("");
  const [symptoms, setSymptoms] = useState<Symptom[]>([]);
  const [vulnerabilities, setVulnerabilities] = useState<Vulnerability[]>([]);
  const [recording, setRecording] = useState(false);
  const [cough, setCough] = useState<Blob | null>(null);
  const [coughUrl, setCoughUrl] = useState<string | null>(null);
  const [xray, setXray] = useState<File | null>(null);
  const [imageSource, setImageSource] = useState<"digital" | "phone_photo">("digital");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<ScreenResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const ageNumber = Number(age);
  const ageIsValid = age !== "" && Number.isInteger(ageNumber) && ageNumber >= 0 && ageNumber <= 120;

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
        const recorded = new Blob(chunks, { type: recorder.mimeType });
        setCough(recorded);
        setCoughUrl(URL.createObjectURL(recorded));
        setRecording(false);
      };
      recorder.start();
      setRecording(true);
      setTimeout(() => recorder.stop(), RECORD_SECONDS * 1000);
    } catch {
      setError("Could not use the microphone. Check the browser's permission.");
    }
  }

  async function submit() {
    setError(null);
    setResult(null);
    setBusy(true);
    try {
      setResult(
        await screen({
          age: ageNumber,
          symptoms,
          vulnerabilities,
          imageSource,
          cough: cough ? await recordingToWav(cough) : null,
          xray,
        }),
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not reach the back end.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="mx-auto flex w-full max-w-md flex-1 flex-col gap-4 px-4 py-8">
      <Link href="/" className="text-muted-foreground text-sm">
        ← Home
      </Link>
      <h1 className="text-2xl font-semibold">TB screening</h1>
      <p className="border-destructive text-destructive rounded-md border p-3 text-sm">
        Prototype for learning only. Not for clinical use. Don&apos;t enter or upload real
        patient data. Use public dataset samples.
      </p>

      <Card>
        <CardHeader>
          <CardTitle>1. About this person</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <label className="flex flex-col gap-1 text-sm">
            Age in years
            <input
              type="number"
              inputMode="numeric"
              min={0}
              max={120}
              value={age}
              onChange={(e) => setAge(e.target.value)}
              className="rounded-md border px-3 py-2"
            />
          </label>
          <Checklist
            options={VULNERABILITIES}
            selected={vulnerabilities}
            onChange={setVulnerabilities}
          />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>2. Symptoms</CardTitle>
          <CardDescription>Tick everything that applies.</CardDescription>
        </CardHeader>
        <CardContent>
          <Checklist options={SYMPTOMS} selected={symptoms} onChange={setSymptoms} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>3. Record a cough (optional)</CardTitle>
          <CardDescription>
            Ask the person to cough a few times. Recording stops after {RECORD_SECONDS} seconds.
          </CardDescription>
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
          <CardTitle>4. Chest X-ray (optional)</CardTitle>
          <CardDescription>
            A digital X-ray image works best. Phone photos of X-ray film haven&apos;t been tested.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          <input
            type="file"
            accept="image/*"
            onChange={(e) => setXray(e.target.files?.[0] ?? null)}
            className="text-sm"
          />
          <label className="flex items-center gap-3 text-sm">
            <input
              type="checkbox"
              className="size-5"
              checked={imageSource === "phone_photo"}
              onChange={(e) => setImageSource(e.target.checked ? "phone_photo" : "digital")}
            />
            This is a phone photo of X-ray film
          </label>
        </CardContent>
      </Card>

      <Button size="lg" onClick={submit} disabled={!ageIsValid || busy || recording}>
        {busy ? "Checking…" : "Get next step"}
      </Button>

      {error && <p className="text-destructive text-sm">{error}</p>}

      {result && (
        <Card>
          <CardHeader>
            <CardTitle>{NEXT_STEP[result.next_step].title}</CardTitle>
            <CardDescription>{NEXT_STEP[result.next_step].detail}</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-3">
            <ul className="list-disc pl-5 text-sm">
              {result.reasons.map((reason) => (
                <li key={reason}>{reason}</li>
              ))}
            </ul>
            {result.xray && <ScoreLine name="X-ray model" result={result.xray} />}
            {result.xray_heatmap_png && (
              <figure className="flex flex-col gap-1">
                {/* A generated picture from the server, so next/image has nothing to optimise. */}
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={`data:image/png;base64,${result.xray_heatmap_png}`}
                  alt="X-ray with red shading where the model found signs that raised its score"
                  className="w-full rounded-md"
                />
                <figcaption className="text-muted-foreground text-xs">
                  Red areas raised the model&apos;s score. This isn&apos;t a diagnosis.
                </figcaption>
              </figure>
            )}
            {result.cough && <ScoreLine name="Cough model" result={result.cough} />}
            <ul className="text-muted-foreground list-disc pl-5 text-xs">
              {result.notes.map((note) => (
                <li key={note}>{note}</li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}
    </main>
  );
}
