"use client";
// The "New screening" card on the counter portal.
// 1. ABHA (optional): with the person's consent, fetch their age, sex, district and
//    medical history. Anything fetched can still be changed by hand.
// 2. Person and medical history, 3. symptoms (always marked by hand),
// 4. the cough: upload a recording (main option) or record one here.

import { useState } from "react";
import { FileAudio, Mic, ShieldCheck, Upload } from "lucide-react";

import { Button } from "@/components/ui/button";
import { recordingToWav } from "@/lib/audio";
import {
  lookupAbha,
  screen,
  type AbhaRecord,
  type ScreenRequest,
  type ScreenResult,
  type Sex,
  type Symptom,
  type Vulnerability,
} from "@/lib/api";
import { HISTORY, SYMPTOMS } from "@/lib/labels";
import { cn } from "@/lib/utils";

const RECORD_SECONDS = 5;

/** Keep only digits and show them as 12-3456-7890-1234, the way ABHA numbers are printed. */
function formatAbha(raw: string): string {
  const d = raw.replace(/\D/g, "").slice(0, 14);
  return [d.slice(0, 2), d.slice(2, 6), d.slice(6, 10), d.slice(10, 14)].filter(Boolean).join("-");
}

function toggled<T>(list: T[], item: T): T[] {
  return list.includes(item) ? list.filter((x) => x !== item) : [...list, item];
}

// Tappable chips instead of checkboxes: quicker on a phone and easier to scan.
function Chips<T extends string>(props: {
  options: { value: T; label: string }[];
  selected: T[];
  onChange: (next: T[]) => void;
}) {
  return (
    <div className="flex flex-wrap gap-2">
      {props.options.map((o) => {
        const on = props.selected.includes(o.value);
        return (
          <button
            key={o.value}
            type="button"
            aria-pressed={on}
            onClick={() => props.onChange(toggled(props.selected, o.value))}
            className={cn(
              "rounded-full border px-3 py-1.5 text-sm transition-colors",
              on
                ? "border-primary bg-accent text-accent-foreground font-medium"
                : "hover:bg-secondary",
            )}
          >
            {o.label}
          </button>
        );
      })}
    </div>
  );
}

function Section(props: { step: number; title: string; hint?: string; children: React.ReactNode }) {
  return (
    <section className="flex flex-col gap-3 border-t pt-5 first:border-t-0 first:pt-0">
      <div>
        <h3 className="text-sm font-semibold">
          <span className="text-muted-foreground mr-2 tabular-nums">{props.step}</span>
          {props.title}
        </h3>
        {props.hint && <p className="text-muted-foreground text-xs">{props.hint}</p>}
      </div>
      {props.children}
    </section>
  );
}

const field = "bg-card rounded-lg border px-3 py-2 text-sm outline-none focus:border-primary";

export function NewScreening(props: {
  districts: string[];
  onScreened: (result: ScreenResult, request: ScreenRequest) => void;
}) {
  const [abha, setAbha] = useState("");
  const [abhaConsent, setAbhaConsent] = useState(false);
  const [record, setRecord] = useState<AbhaRecord | null>(null);
  const [age, setAge] = useState("");
  const [sex, setSex] = useState<Sex | "">("");
  const [district, setDistrict] = useState("Chamarajanagar");
  const [hasPhone, setHasPhone] = useState(true);
  const [history, setHistory] = useState<Vulnerability[]>([]);
  const [symptoms, setSymptoms] = useState<Symptom[]>([]);
  const [cough, setCough] = useState<Blob | null>(null);
  const [coughName, setCoughName] = useState("");
  const [coughUrl, setCoughUrl] = useState<string | null>(null);
  const [recording, setRecording] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const ageNumber = Number(age);
  const ageIsValid = age !== "" && Number.isInteger(ageNumber) && ageNumber >= 0 && ageNumber <= 120;
  const ready = ageIsValid && sex !== "" && district !== "" && cough !== null;

  async function fetchHistory() {
    setError(null);
    try {
      const found = await lookupAbha(abha, abhaConsent);
      setRecord(found);
      setAge(String(found.age));
      setSex(found.sex);
      setDistrict(found.district);
      setHistory(found.history.filter((h) => h !== "over_60"));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not fetch the ABHA record.");
    }
  }

  function keepCough(sound: Blob, name: string) {
    setCough(sound);
    setCoughName(name);
    setCoughUrl(URL.createObjectURL(sound));
  }

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
        keepCough(new Blob(chunks, { type: recorder.mimeType }), "Recorded at the Counter");
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
    if (!ready || !cough) return;
    setError(null);
    setBusy(true);
    try {
      // Uploaded files and recordings both become 16 kHz WAV, the format scoring expects.
      const wav = await recordingToWav(cough).catch(() => {
        throw new Error("Could not read that sound file. Try a WAV file or record again.");
      });
      const request: ScreenRequest = {
        age: ageNumber,
        sex,
        district,
        hasPhone,
        abhaLinked: record !== null,
        symptoms,
        vulnerabilities: history,
        cough: wav,
      };
      props.onScreened(await screen(request), request);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not reach the back end.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col gap-5">
      <Section step={1} title="ABHA Health Record" hint="Optional. Fills in the details below.">
        <input
          value={abha}
          onChange={(e) => setAbha(formatAbha(e.target.value))}
          inputMode="numeric"
          placeholder="ABHA number, e.g. 91-5528-7340-1196"
          aria-label="ABHA number"
          className={field}
        />
        <label className="flex items-start gap-2 text-sm">
          <input
            type="checkbox"
            className="accent-primary mt-0.5 size-4"
            checked={abhaConsent}
            onChange={(e) => setAbhaConsent(e.target.checked)}
          />
          The person agrees to share their ABHA health records for TB screening.
        </label>
        <Button
          variant="outline"
          onClick={fetchHistory}
          disabled={abha.length !== 17 || !abhaConsent}
        >
          <ShieldCheck aria-hidden /> Fetch History
        </Button>
        {record && (
          <div className="bg-accent rounded-lg p-3 text-sm">
            <p className="text-accent-foreground font-medium">
              History Fetched from ABHA ··{record.abha_last4}
            </p>
            <ul className="text-muted-foreground mt-1 list-disc pl-5 text-xs">
              {record.conditions.map((c) => (
                <li key={c}>{c}</li>
              ))}
            </ul>
          </div>
        )}
      </Section>

      <Section step={2} title="Person and Medical History">
        {/* Flexible row: the district box takes the leftover width so long names fit. */}
        <div className="flex flex-wrap gap-2">
          <input
            type="number"
            inputMode="numeric"
            min={0}
            max={120}
            value={age}
            onChange={(e) => setAge(e.target.value)}
            placeholder="Age"
            aria-label="Age in years"
            className={`${field} w-20`}
          />
          <select
            value={sex}
            onChange={(e) => setSex(e.target.value as Sex | "")}
            aria-label="Sex"
            className={`${field} w-28`}
          >
            <option value="">Sex</option>
            <option value="F">Female</option>
            <option value="M">Male</option>
          </select>
          <select
            value={district}
            onChange={(e) => setDistrict(e.target.value)}
            aria-label="District"
            className={`${field} min-w-40 flex-1`}
          >
            {props.districts.map((d) => (
              <option key={d} value={d}>
                {d}
              </option>
            ))}
          </select>
        </div>
        <Chips options={HISTORY} selected={history} onChange={setHistory} />
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            className="accent-primary size-4"
            checked={hasPhone}
            onChange={(e) => setHasPhone(e.target.checked)}
          />
          Has a phone the ASHA can call
        </label>
      </Section>

      <Section step={3} title="Symptoms" hint="Ask about each one.">
        <Chips options={SYMPTOMS} selected={symptoms} onChange={setSymptoms} />
      </Section>

      <Section step={4} title="Cough Recording" hint="Three or more coughs, in a quiet spot.">
        {/* The label is styled as the big button and opens the file picker. */}
        <label
          className={cn(
            "border-primary/40 bg-accent text-accent-foreground hover:bg-accent/70",
            "flex cursor-pointer flex-col items-center gap-1 rounded-xl border-2 border-dashed p-5",
          )}
        >
          <Upload className="size-6" aria-hidden />
          <span className="font-semibold">Upload Recording</span>
          <span className="text-muted-foreground text-xs">WAV, MP3 or M4A</span>
          <input
            type="file"
            accept="audio/*,.wav"
            className="sr-only"
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) keepCough(file, file.name);
            }}
          />
        </label>
        <button
          type="button"
          onClick={recordCough}
          disabled={recording}
          className="text-muted-foreground hover:text-foreground inline-flex items-center gap-1.5 self-center text-sm"
        >
          <Mic className="size-4" aria-hidden />
          {recording ? `Recording for ${RECORD_SECONDS} s…` : "Or Record Here"}
        </button>
        {coughUrl && (
          <div className="flex flex-col gap-2 rounded-lg border p-3">
            <span className="flex items-center gap-2 text-sm">
              <FileAudio className="text-primary size-4" aria-hidden />
              <span className="truncate">{coughName}</span>
            </span>
            <audio controls src={coughUrl} className="h-9 w-full" />
          </div>
        )}
      </Section>

      {error && <p className="text-destructive text-sm">{error}</p>}

      <Button size="lg" onClick={submit} disabled={!ready || busy || recording}>
        {busy ? "Analysing Cough…" : "Get Risk Score"}
      </Button>
    </div>
  );
}
