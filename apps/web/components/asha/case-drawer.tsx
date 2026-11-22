"use client";
// One forwarded case in the ASHA portal, as numbered steps from first contact to the
// start of treatment. Each step unlocks when the case reaches it (the server checks the
// same order). Following NTEP: sputum for a NAAT is collected at first contact for
// presumptive TB, without waiting for the X-ray van, and only a NAAT confirms TB.

import { useState, type ReactNode } from "react";
import { Check, ImageUp, Phone, PhoneOff } from "lucide-react";

import { Drawer } from "@/components/drawer";
import { Pill } from "@/components/pill";
import { Button } from "@/components/ui/button";
import {
  bookVan,
  closeCase,
  combineRisk,
  recordContact,
  recordNaat,
  recordSputum,
  recordVanReading,
  startTreatment,
  uploadCaseXray,
  type Case,
  type NaatResult,
  type VanSlot,
  type WeightBand,
} from "@/lib/api";
import {
  ACTION,
  BAND,
  CASE_STATUS,
  CLOSED_REASON,
  HISTORY_LABEL,
  NAAT,
  SYMPTOM_LABEL,
  WEIGHT_BANDS,
  bandOf,
  percent,
  shortDay,
  when,
} from "@/lib/labels";
import { cn } from "@/lib/utils";

const field = "bg-card rounded-lg border px-3 py-2 text-sm outline-none focus:border-primary";
const AFTER_CONTACT = ["contacted", "xray_booked", "xray_done", "risk_combined"];

function Step(props: {
  n: number;
  title: string;
  done: boolean;
  active: boolean;
  summary?: ReactNode;
  children?: ReactNode;
}) {
  return (
    <li className="relative flex gap-4 pb-6 last:pb-0">
      {/* The line joining the step circles. */}
      <span className="bg-border absolute top-8 bottom-0 left-[15px] w-px" aria-hidden />
      <span
        className={cn(
          "relative z-[1] grid size-8 shrink-0 place-items-center rounded-full border text-sm font-semibold",
          props.done && "bg-primary border-primary text-primary-foreground",
          props.active && !props.done && "border-primary text-primary bg-accent",
          !props.done && !props.active && "text-muted-foreground bg-card",
        )}
      >
        {props.done ? <Check className="size-4" /> : props.n}
      </span>
      <div className="flex min-w-0 flex-1 flex-col gap-2 pt-1">
        <span className={cn("font-medium", !props.done && !props.active && "text-muted-foreground")}>
          {props.title}
        </span>
        {props.summary && <div className="text-muted-foreground text-sm">{props.summary}</div>}
        {props.active && props.children}
      </div>
    </li>
  );
}

function RiskBlock({ label, risk, band }: { label: string; risk: number | null; band: Case["combined_band"] }) {
  if (risk === null) return null;
  return (
    <div className="flex items-center gap-3">
      <span className="text-2xl font-semibold tabular-nums">{percent(risk)}</span>
      <span className="text-muted-foreground text-sm">{label}</span>
      {band && (
        <Pill tone={BAND[band].tone} dot>
          {BAND[band].label}
        </Pill>
      )}
    </div>
  );
}

export function CaseDrawer(props: {
  c: Case;
  slots: VanSlot[];
  onChange: (updated: Case) => void;
  onOpenPatient: (patientId: string) => void;
  onClose: () => void;
}) {
  const c = props.c;
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [slotId, setSlotId] = useState(c.xray_slot?.slot_id ?? "");
  const [naat, setNaat] = useState<NaatResult>("mtb_detected_rr_not_detected");
  const [mo, setMo] = useState("");
  const [phc, setPhc] = useState(c.xray_slot?.site ?? "");
  const [weight, setWeight] = useState<WeightBand>("35-49");
  const [nikshayId, setNikshayId] = useState("");
  const [notified, setNotified] = useState(false);
  const [closeReason, setCloseReason] = useState<Parameters<typeof closeCase>[1]>("not_reached");

  // Every step calls the server, then shows the case as the server returned it.
  async function run(call: Promise<Case>) {
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

  const finished = c.status === "on_treatment" || c.status === "closed";
  const overdue = c.status === "new" && new Date(c.contact_due_at) < new Date();
  const presumptive = c.counter_action === "naat";
  const naatFinal = c.naat_result !== null && c.naat_result !== "inconclusive";
  const freeSlots = props.slots.filter((s) => s.booked < s.capacity);

  return (
    <Drawer
      onClose={props.onClose}
      title={
        <span className="flex items-center gap-3">
          Case {c.case_id}
          <Pill tone={finished ? "neutral" : "ok"}>{CASE_STATUS[c.status]}</Pill>
        </span>
      }
      subtitle={`${c.sex === "F" ? "Female" : "Male"}, ${c.age} · Forwarded ${when(c.forwarded_at)} by ${c.practitioner} · ASHA ${c.asha_name}`}
    >
      {/* What the practitioner recorded at the counter. */}
      <section className="bg-secondary/60 flex flex-col gap-3 rounded-xl p-4">
        <span className="text-primary text-xs font-semibold tracking-wide uppercase">
          From the Counter
        </span>
        <RiskBlock
          label="Cough Risk"
          risk={c.cough_risk}
          band={bandOf(c.cough_risk)}
        />
        <p className="text-sm">
          <b>{ACTION[c.counter_action].title}.</b> {c.counter_reasons.join(" ")}
        </p>
        <div className="flex flex-wrap gap-1.5">
          {c.symptoms.map((s) => (
            <Pill key={s} tone="wait">
              {SYMPTOM_LABEL[s]}
            </Pill>
          ))}
          {c.history.map((h) => (
            <Pill key={h}>{HISTORY_LABEL[h]}</Pill>
          ))}
          {c.symptoms.length + c.history.length === 0 && <Pill>No Symptoms or History</Pill>}
        </div>
        <p className="text-muted-foreground text-xs">
          {c.abha_linked ? "History from ABHA (with consent)" : "History entered by hand"} ·{" "}
          {c.has_phone ? "Has a phone" : "No phone: visit in person"}
        </p>
      </section>

      <ol className="flex flex-col">
        <Step
          n={1}
          title="Contact the Person"
          done={c.contacted_at !== null}
          active={c.status === "new"}
          summary={
            c.contacted_at
              ? `Reached ${when(c.contacted_at)} after ${c.contact_attempts} attempt${c.contact_attempts === 1 ? "" : "s"}`
              : `Due by ${when(c.contact_due_at)}${c.contact_attempts ? ` · ${c.contact_attempts} attempt${c.contact_attempts === 1 ? "" : "s"} so far` : ""}`
          }
        >
          {overdue && <Pill tone="alert">Overdue: Reach Them Today</Pill>}
          <div className="flex gap-2">
            <Button disabled={busy} onClick={() => run(recordContact(c.case_id, true))}>
              <Phone aria-hidden /> Reached
            </Button>
            <Button
              variant="outline"
              disabled={busy}
              onClick={() => run(recordContact(c.case_id, false))}
            >
              <PhoneOff aria-hidden /> Not Reached
            </Button>
          </div>
        </Step>

        <Step
          n={2}
          title="Sputum for NAAT"
          done={c.sputum_collected_at !== null || naatFinal}
          active={AFTER_CONTACT.includes(c.status) && c.sputum_collected_at === null && !naatFinal}
          summary={
            c.sputum_collected_at
              ? `Collected ${when(c.sputum_collected_at)} and sent to the TB Unit`
              : presumptive
                ? "Presumptive TB: collect at first contact, don't wait for the van."
                : "Collect if the X-ray risk is high."
          }
        >
          <Button disabled={busy} onClick={() => run(recordSputum(c.case_id))}>
            Sputum Collected and Sent to TB Unit
          </Button>
        </Step>

        <Step
          n={3}
          title="Book the Mobile X-Ray Van"
          done={c.xray_slot !== null}
          active={c.status === "contacted" || c.status === "xray_booked"}
          summary={c.xray_slot && `${c.xray_slot.site} · ${shortDay(c.xray_slot.day)}`}
        >
          <div className="flex gap-2">
            <select
              value={slotId}
              onChange={(e) => setSlotId(e.target.value)}
              className={`${field} flex-1`}
              aria-label="Van visit"
            >
              <option value="">Choose a van visit…</option>
              {freeSlots.map((s) => (
                <option key={s.slot_id} value={s.slot_id}>
                  {s.site} · {shortDay(s.day)} · {s.capacity - s.booked} places left
                </option>
              ))}
            </select>
            <Button
              disabled={busy || !slotId}
              onClick={() => run(bookVan(c.case_id, slotId))}
            >
              {c.xray_slot ? "Change" : "Book"}
            </Button>
          </div>
        </Step>

        <Step
          n={4}
          title="Chest X-Ray"
          done={c.xray_source !== null}
          active={c.status === "xray_booked" || c.status === "xray_done"}
          summary={
            c.xray_source === "van_reading"
              ? `Van reading: ${c.van_reading === "abnormal" ? "Abnormal" : "Normal"}`
              : undefined
          }
        >
          <RiskBlock
            label="X-Ray Risk"
            risk={c.xray_risk}
            band={bandOf(c.xray_risk)}
          />
          <label
            className={cn(
              "border-primary/40 bg-accent text-accent-foreground hover:bg-accent/70",
              "flex cursor-pointer items-center justify-center gap-2 rounded-xl border-2 border-dashed p-4",
              busy && "pointer-events-none opacity-60",
            )}
          >
            <ImageUp className="size-5" aria-hidden />
            <span className="font-semibold">
              {busy ? "Analysing X-Ray…" : c.xray_source === "upload" ? "Upload a Different X-Ray" : "Upload X-Ray Image"}
            </span>
            <input
              type="file"
              accept="image/*"
              className="sr-only"
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) run(uploadCaseXray(c.case_id, file));
              }}
            />
          </label>
          <div className="text-muted-foreground flex flex-wrap items-center gap-2 text-sm">
            Or use the van&apos;s own reading:
            <Button size="sm" variant="outline" disabled={busy} onClick={() => run(recordVanReading(c.case_id, "normal"))}>
              Normal
            </Button>
            <Button size="sm" variant="outline" disabled={busy} onClick={() => run(recordVanReading(c.case_id, "abnormal"))}>
              Abnormal
            </Button>
          </div>
        </Step>

        <Step
          n={5}
          title="Combined Risk Score"
          done={c.combined_action !== null}
          active={c.status === "xray_done" || c.status === "risk_combined"}
        >
          {c.combined_action === null ? (
            <Button size="lg" disabled={busy} onClick={() => run(combineRisk(c.case_id))}>
              Get Combined Risk Score
            </Button>
          ) : (
            <div className="border-primary/25 bg-accent flex flex-col gap-2 rounded-xl border p-4">
              <RiskBlock label="Combined Risk" risk={c.combined_risk} band={c.combined_band} />
              <p className="font-semibold">{ACTION[c.combined_action].title}</p>
              <ul className="text-sm">
                {c.combined_reasons.map((r) => (
                  <li key={r}>• {r}</li>
                ))}
              </ul>
              {c.combined_action === "routine_care" && c.status === "risk_combined" && (
                <Button
                  variant="outline"
                  className="self-start"
                  disabled={busy}
                  onClick={() => run(closeCase(c.case_id, "xray_clear"))}
                >
                  Close Case: X-Ray Clear
                </Button>
              )}
            </div>
          )}
        </Step>

        <Step
          n={6}
          title="NAAT Result (Truenat / CBNAAT)"
          done={naatFinal}
          active={AFTER_CONTACT.includes(c.status) && c.sputum_collected_at !== null}
          summary={
            c.naat_result
              ? `${NAAT[c.naat_result]}${c.naat_attempts > 1 ? ` · Test ${c.naat_attempts}` : ""}`
              : "Needs a sputum sample (step 2)."
          }
        >
          <div className="flex gap-2">
            <select
              value={naat}
              onChange={(e) => setNaat(e.target.value as NaatResult)}
              className={`${field} flex-1`}
              aria-label="NAAT result"
            >
              {Object.entries(NAAT).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
            <Button disabled={busy} onClick={() => run(recordNaat(c.case_id, naat))}>
              Save
            </Button>
          </div>
        </Step>

        <Step
          n={7}
          title="Start 6-Month Treatment"
          done={c.status === "on_treatment"}
          active={c.status === "naat_positive"}
          summary={
            c.status === "on_treatment"
              ? `Started by ${c.mo_name ?? "the Medical Officer"}${c.notified_in_nikshay ? " · Notified in Ni-kshay" : ""}`
              : c.naat_result === "mtb_detected_rr_detected"
                ? "Rifampicin resistance: refer to the DR-TB centre for a drug-resistant regimen."
                : "Daily fixed-dose tablets by weight band: 2 months HRZE, then 4 months HRE."
          }
        >
          <p className="text-muted-foreground text-xs">
            Record this once the PHC Medical Officer has started treatment.
          </p>
          <div className="grid grid-cols-2 gap-2">
            <input value={mo} onChange={(e) => setMo(e.target.value)} placeholder="Medical Officer" className={field} />
            <input value={phc} onChange={(e) => setPhc(e.target.value)} placeholder="PHC" className={field} />
            <select
              value={weight}
              onChange={(e) => setWeight(e.target.value as WeightBand)}
              className={field}
              aria-label="Weight band"
            >
              {WEIGHT_BANDS.map((w) => (
                <option key={w} value={w}>
                  {w === "over-75" ? "Over 75 kg" : `${w} kg`}
                </option>
              ))}
            </select>
            <input
              value={nikshayId}
              onChange={(e) => setNikshayId(e.target.value)}
              placeholder="Ni-kshay ID (optional)"
              className={field}
            />
          </div>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              className="accent-primary size-4"
              checked={notified}
              onChange={(e) => setNotified(e.target.checked)}
            />
            Notified in Ni-kshay (done by the PHC; TB notification is mandatory)
          </label>
          <Button
            size="lg"
            disabled={busy || mo.trim().length < 2 || phc.trim().length < 2}
            onClick={() =>
              run(
                startTreatment(c.case_id, {
                  mo_name: mo.trim(),
                  phc: phc.trim(),
                  weight_band: weight,
                  nikshay_id: nikshayId.trim() || undefined,
                  notified_in_nikshay: notified,
                }),
              )
            }
          >
            Start Treatment and Daily Tracking
          </Button>
        </Step>

        {c.status === "closed" && (
          <Step
            n={8}
            title="Case Closed"
            done
            active={false}
            summary={c.closed_reason ? (CLOSED_REASON[c.closed_reason] ?? c.closed_reason) : undefined}
          />
        )}
      </ol>

      {c.patient_id && (
        <Button variant="outline" onClick={() => props.onOpenPatient(c.patient_id!)}>
          Open Patient {c.patient_id}
        </Button>
      )}

      {error && <p className="text-destructive text-sm">{error}</p>}

      {!finished && (
        <details className="text-sm">
          <summary className="text-muted-foreground cursor-pointer">Close This Case</summary>
          <div className="mt-3 flex gap-2">
            <select
              value={closeReason}
              onChange={(e) => setCloseReason(e.target.value as typeof closeReason)}
              className={`${field} flex-1`}
              aria-label="Reason for closing"
            >
              <option value="not_reached">Not Reached After Several Tries</option>
              <option value="moved_away">Moved Away</option>
              <option value="declined">Person Declined</option>
              <option value="other">Other</option>
            </select>
            <Button variant="destructive" disabled={busy} onClick={() => run(closeCase(c.case_id, closeReason))}>
              Close Case
            </Button>
          </div>
        </details>
      )}
    </Drawer>
  );
}
