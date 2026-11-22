"use client";
// The "Result" card on the counter portal: the cough risk score, the recommended action,
// and the practitioner's decision. Forwarding is always done by hand, never automatically:
// the person must agree to be contacted, and the practitioner may dismiss with a reason.

import { useState } from "react";
import { AudioLines, CheckCircle2, Printer, Send } from "lucide-react";

import { Pill } from "@/components/pill";
import { Button } from "@/components/ui/button";
import {
  dismissScreening,
  forwardScreening,
  type Case,
  type DismissReason,
  type ScreenResult,
} from "@/lib/api";
import { ACTION, BAND, DISMISS_REASONS, percent } from "@/lib/labels";
import { cn } from "@/lib/utils";

const BAR = { low: "bg-ok", moderate: "bg-wait", high: "bg-alert" };

export function ResultPanel(props: {
  result: ScreenResult | null;
  onDecided: (forwarded: Case | null) => void;
  onNext: () => void;
  onPrint: () => void;
}) {
  const [consent, setConsent] = useState(false);
  const [dismissing, setDismissing] = useState(false);
  const [reason, setReason] = useState<DismissReason>("low_risk");
  const [done, setDone] = useState<{ kind: "forwarded"; case: Case } | { kind: "dismissed" } | null>(
    null,
  );
  const [error, setError] = useState<string | null>(null);

  const r = props.result;
  if (!r) {
    return (
      <div className="text-muted-foreground flex flex-1 flex-col items-center justify-center gap-3 py-16 text-center text-sm">
        <AudioLines className="size-10 opacity-40" aria-hidden />
        Add the symptoms and a cough recording, then press <b>Get Risk Score</b>.
      </div>
    );
  }

  const action = ACTION[r.next_step];
  const band = r.risk_band ? BAND[r.risk_band] : null;

  async function forward() {
    setError(null);
    try {
      const created = await forwardScreening(r!.screening_id, consent);
      setDone({ kind: "forwarded", case: created });
      props.onDecided(created);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not forward this case.");
    }
  }

  async function dismiss() {
    setError(null);
    try {
      await dismissScreening(r!.screening_id, reason);
      setDone({ kind: "dismissed" });
      props.onDecided(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not dismiss this screening.");
    }
  }

  return (
    <div className="flex flex-col gap-5">
      {/* The score: large number, band pill and a bar with the 50% threshold marked. */}
      <div>
        <div className="flex items-center justify-between">
          <span className="text-muted-foreground text-sm">Cough Risk Score</span>
          {band && (
            <Pill tone={band.tone} dot>
              {band.label}
            </Pill>
          )}
        </div>
        <div className="mt-1 text-5xl font-semibold tabular-nums">
          {r.risk_score === null ? "–" : percent(r.risk_score)}
        </div>
        {r.risk_score !== null && r.risk_band && (
          <div className="bg-secondary relative mt-3 h-2 rounded-full">
            <div
              className={cn("h-full rounded-full", BAR[r.risk_band])}
              style={{ width: `${Math.max(2, r.risk_score * 100)}%` }}
            />
            <span
              className="bg-foreground/40 absolute top-[-3px] left-1/2 h-3.5 w-px"
              title="Referral threshold"
            />
          </div>
        )}
      </div>

      <div className="border-primary/25 bg-accent rounded-xl border p-4">
        <span className="text-primary text-xs font-semibold tracking-wide uppercase">
          Recommended Action
        </span>
        <p className="mt-1 text-lg font-semibold">{action.title}</p>
        <p className="text-muted-foreground text-sm">{action.detail}</p>
        <ul className="mt-3 flex flex-col gap-1 text-sm">
          {r.reasons.map((reason) => (
            <li key={reason} className="flex gap-2">
              <span className="text-primary">•</span>
              {reason}
            </li>
          ))}
        </ul>
      </div>

      {done === null && !dismissing && (
        <div className="flex flex-col gap-3">
          <label className="flex items-start gap-2 text-sm">
            <input
              type="checkbox"
              className="accent-primary mt-0.5 size-4"
              checked={consent}
              onChange={(e) => setConsent(e.target.checked)}
            />
            The person agrees to be contacted by an ASHA worker.
          </label>
          <div className="grid gap-2 sm:grid-cols-2">
            <Button size="lg" onClick={forward} disabled={!consent}>
              <Send aria-hidden /> Forward to ASHA
            </Button>
            <Button size="lg" variant="outline" onClick={() => setDismissing(true)}>
              Dismiss
            </Button>
          </div>
        </div>
      )}

      {done === null && dismissing && (
        <div className="flex flex-col gap-3 rounded-xl border p-4">
          <span className="text-sm font-medium">Reason for Not Forwarding</span>
          <select
            value={reason}
            onChange={(e) => setReason(e.target.value as DismissReason)}
            className="bg-card rounded-lg border px-3 py-2 text-sm"
          >
            {DISMISS_REASONS.map((d) => (
              <option key={d.value} value={d.value}>
                {d.label}
              </option>
            ))}
          </select>
          <div className="grid gap-2 sm:grid-cols-2">
            <Button variant="outline" onClick={() => setDismissing(false)}>
              Back
            </Button>
            <Button variant="destructive" onClick={dismiss}>
              Confirm Dismiss
            </Button>
          </div>
        </div>
      )}

      {done?.kind === "forwarded" && (
        <div className="bg-ok-soft text-ok flex flex-col gap-2 rounded-xl p-4 text-sm">
          <span className="flex items-center gap-2 font-semibold">
            <CheckCircle2 className="size-5" aria-hidden /> Forwarded to ASHA {done.case.asha_name}
          </span>
          <span>
            Case {done.case.case_id}. The ASHA will contact them within 48 hours to arrange the
            chest X-ray{r.next_step === "naat" ? " and sputum test" : ""}.
          </span>
          <Button variant="outline" size="sm" className="self-start" onClick={props.onPrint}>
            <Printer aria-hidden /> Print Referral Slip
          </Button>
        </div>
      )}
      {done?.kind === "dismissed" && (
        <p className="bg-secondary rounded-xl p-4 text-sm">Dismissed and Recorded</p>
      )}

      {error && <p className="text-destructive text-sm">{error}</p>}

      {done !== null && (
        <Button size="lg" variant="ghost" onClick={props.onNext}>
          Screen the Next Person
        </Button>
      )}
    </div>
  );
}
