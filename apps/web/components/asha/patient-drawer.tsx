"use client";
// One patient on treatment in the ASHA portal: where they are in the 6 months, the last
// 28 days of dose reports, today's dose, and IsoScreen urine tests (a spot check that
// the reported doses were really taken). IsoScreen only works for regimens with isoniazid.

import { useState } from "react";
import { Check, X } from "lucide-react";

import { Drawer } from "@/components/drawer";
import { Pill } from "@/components/pill";
import { Button } from "@/components/ui/button";
import { recordDose, recordIsoScreen, type IsoScreenTest, type RiskEntry } from "@/lib/api";
import { titleCase, todayIso, treatmentStage } from "@/lib/labels";
import { cn } from "@/lib/utils";

const LADDER = {
  on_track: { label: "On Track", tone: "ok" as const },
  call: { label: "Call Due (3+ Days Missed)", tone: "wait" as const },
  asha_visit: { label: "Home Visit Due (7+ Days Missed)", tone: "alert" as const },
};

const ISO_RESULT: Record<IsoScreenTest["result"], { label: string; tone: "ok" | "alert" | "neutral" }> = {
  inh_detected: { label: "INH Detected", tone: "ok" },
  inh_not_detected: { label: "INH Not Detected", tone: "alert" },
  indeterminate: { label: "Indeterminate", tone: "neutral" },
};

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-muted-foreground text-xs">{label}</div>
      <div className="text-sm font-medium">{value}</div>
    </div>
  );
}

/** The last 28 days as small bars: teal = dose reported, red outline = missed. */
export function DoseStrip({ log }: { log: RiskEntry["patient"]["dose_log_last_28_days"] }) {
  if (log.length === 0) return <span className="text-muted-foreground text-xs">Starts Today</span>;
  const taken = log.filter((d) => d === "taken").length;
  return (
    <div
      className="flex gap-[3px]"
      role="img"
      aria-label={`${taken} of ${log.length} doses reported`}
      title={`${taken}/${log.length} doses reported (oldest left)`}
    >
      {log.map((day, i) => (
        <span
          key={i}
          className={cn(
            "h-5 w-2 rounded-sm",
            day === "taken" ? "bg-primary" : "border-alert bg-alert-soft border",
          )}
        />
      ))}
    </div>
  );
}

export function PatientDrawer(props: {
  entry: RiskEntry;
  onChange: (updated: RiskEntry) => void;
  onClose: () => void;
}) {
  const { entry } = props;
  const p = entry.patient;
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [iso, setIso] = useState<IsoScreenTest["result"]>("inh_detected");
  const [hours, setHours] = useState("");

  const stage = treatmentStage(p.days_on_treatment);
  const drugSensitive = p.regimen === "drug-sensitive";
  const loggedToday = p.last_dose_logged_on === todayIso();
  const riskTone = entry.risk_score >= 0.6 ? "alert" : entry.risk_score >= 0.4 ? "wait" : "ok";

  async function run(call: Promise<RiskEntry>) {
    setBusy(true);
    setError(null);
    try {
      props.onChange(await call);
    } catch (e) {
      setError(e instanceof Error ? e.message : "That didn't work. Try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Drawer
      onClose={props.onClose}
      title={
        <span className="flex items-center gap-3">
          {p.patient_id}
          <Pill tone={riskTone} dot>
            {Math.round(entry.risk_score * 100)}% Dropout Risk
          </Pill>
        </span>
      }
      subtitle={`${p.sex === "F" ? "Female" : "Male"}, ${p.age} · ${p.district} · ASHA ${p.asha_name ?? "not assigned"}`}
    >
      <section className="grid grid-cols-2 gap-4 sm:grid-cols-3">
        <Fact label="Treatment" value={`Month ${stage.month} of 6 · Day ${p.days_on_treatment}`} />
        <Fact label="Phase" value={stage.phase} />
        <Fact
          label="Regimen"
          value={drugSensitive ? "2HRZE / 4HRE, Daily FDC" : "DR-TB Regimen (DR-TB Centre)"}
        />
        <Fact label="Weight Band" value={p.weight_band ? `${p.weight_band.replace("over-", "Over ")} kg` : "Not recorded"} />
        <Fact label="PHC" value={p.phc ?? "Not recorded"} />
        <Fact
          label="Ni-kshay Poshan Yojana"
          value={p.gets_nutrition_support ? "₹1,000 / Month" : "Not Enrolled"}
        />
      </section>

      <section className="flex flex-col gap-2">
        <div className="flex items-center justify-between">
          <h3 className="font-semibold">Why This Risk</h3>
          <Pill tone={LADDER[entry.ladder_step].tone}>{LADDER[entry.ladder_step].label}</Pill>
        </div>
        {entry.reasons.length ? (
          <ol className="text-muted-foreground list-decimal pl-5 text-sm">
            {entry.reasons.map((r) => (
              <li key={r}>{titleCase(r)}</li>
            ))}
          </ol>
        ) : (
          <p className="text-muted-foreground text-sm">No Risk Factors Recorded</p>
        )}
        {!p.gets_nutrition_support && p.undernourished && (
          <p className="text-wait text-sm">
            Undernourished and not receiving Ni-kshay Poshan Yojana: help them add bank details at the PHC.
          </p>
        )}
      </section>

      <section className="flex flex-col gap-3">
        <h3 className="font-semibold">Daily Doses (Last 28 Days)</h3>
        <DoseStrip log={p.dose_log_last_28_days} />
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-muted-foreground text-sm">Today&apos;s Dose:</span>
          {loggedToday ? (
            <Pill tone={p.dose_log_last_28_days.at(-1) === "taken" ? "ok" : "alert"}>
              {p.dose_log_last_28_days.at(-1) === "taken" ? "Taken" : "Missed"} · Recorded
            </Pill>
          ) : (
            <>
              <Button size="sm" disabled={busy} onClick={() => run(recordDose(p.patient_id, "taken"))}>
                <Check aria-hidden /> Taken
              </Button>
              <Button
                size="sm"
                variant="outline"
                disabled={busy}
                onClick={() => run(recordDose(p.patient_id, "missed"))}
              >
                <X aria-hidden /> Missed
              </Button>
            </>
          )}
        </div>
      </section>

      <section className="flex flex-col gap-3">
        <div className="flex items-center justify-between">
          <h3 className="font-semibold">IsoScreen Urine Tests</h3>
          {entry.isoscreen_every_days && (
            <span className="text-muted-foreground text-xs">Every {entry.isoscreen_every_days} Days</span>
          )}
        </div>
        {!drugSensitive ? (
          <p className="text-muted-foreground text-sm">
            Not used: this regimen has no isoniazid, so the strip has nothing to detect.
          </p>
        ) : (
          <>
            {p.isoscreen_tests.length === 0 ? (
              <p className="text-muted-foreground text-sm">No Tests Yet</p>
            ) : (
              <ul className="flex flex-col gap-1.5 text-sm">
                {p.isoscreen_tests
                  .slice()
                  .reverse()
                  .map((t, i) => (
                    <li key={i} className="flex items-center justify-between gap-2">
                      <span>
                        Day {t.day_on_treatment}
                        {t.hours_since_dose !== null && (
                          <span className="text-muted-foreground"> · {t.hours_since_dose} h after dose</span>
                        )}
                      </span>
                      <Pill tone={ISO_RESULT[t.result].tone}>{ISO_RESULT[t.result].label}</Pill>
                    </li>
                  ))}
              </ul>
            )}
            <div className="flex flex-wrap items-end gap-3">
              <label className="flex min-w-48 flex-1 flex-col gap-1 text-xs font-medium">
                Result
                <select
                  value={iso}
                  onChange={(e) => setIso(e.target.value as IsoScreenTest["result"])}
                  className="bg-card rounded-lg border px-3 py-2 text-sm font-normal"
                >
                  <option value="inh_detected">INH Detected (Purple / Blue)</option>
                  <option value="inh_not_detected">INH Not Detected</option>
                  <option value="indeterminate">Indeterminate</option>
                </select>
              </label>
              <label className="flex w-52 flex-col gap-1 text-xs font-medium">
                Hours Since Last Dose (0–240)
                <input
                  type="number"
                  min={0}
                  max={240}
                  value={hours}
                  onChange={(e) => setHours(e.target.value)}
                  placeholder="e.g. 12"
                  className="bg-card rounded-lg border px-3 py-2 text-sm font-normal"
                />
              </label>
              <Button
                variant="outline"
                disabled={busy}
                onClick={() =>
                  run(recordIsoScreen(p.patient_id, iso, hours === "" ? undefined : Number(hours)))
                }
              >
                Record Test
              </Button>
            </div>
            <p className="text-muted-foreground text-xs">
              Ask when they last took their tablets. The strip is most reliable 6 to 48 hours
              after a dose, so a result outside that window may be wrong. Test unannounced, with
              consent.
            </p>
          </>
        )}
      </section>

      {error && <p className="text-destructive text-sm">{error}</p>}

      <p className="text-muted-foreground border-t pt-4 text-xs">
        Ni-kshay Sampark TB helpline: 1800-11-6666 (toll-free)
      </p>
    </Drawer>
  );
}
