"use client";
// ASHA portal, laid out like the Figma: the patient-journey card, then
// - Suggested by TBC² (the main section): next steps drafted for the ASHA. Nothing is
//   sent until approved.
// - Forwarded Cases: people sent by the counter, from first contact to treatment.
// - Likely to Stop Treatment: patients on treatment, highest dropout risk first.
// Opening a case or patient shows its details in a drawer on the right.

import { useCallback, useEffect, useState } from "react";
import { CalendarDays, ChevronRight } from "lucide-react";

import { CaseDrawer } from "@/components/asha/case-drawer";
import { PatientDrawer } from "@/components/asha/patient-drawer";
import { AppFooter } from "@/components/app-footer";
import { AuthGate } from "@/components/auth-gate";
import { AppHeader } from "@/components/app-header";
import { JourneyCard } from "@/components/journey-card";
import { CountPill, Panel } from "@/components/panel";
import { Pill } from "@/components/pill";
import { Button } from "@/components/ui/button";
import {
  decideAction,
  getActions,
  getCases,
  getOverview,
  getVanSlots,
  getWeeklyRisk,
  type Action,
  type Case,
  type Overview,
  type RiskEntry,
  type VanSlot,
} from "@/lib/api";
import { ACTION_TYPE, percent, shortDay, titleCase, treatmentStage, when, type Tone } from "@/lib/labels";
import { useThisWeek } from "@/lib/week";

const DISTRICT = "Chamarajanagar";
const FINISHED = ["on_treatment", "closed"];
const SHOW_PATIENTS = 6;

/** The status pill for a case row, and how urgent it is (lower sorts first). */
function caseBadge(c: Case): { label: string; tone: Tone; urgency: number } {
  if (c.status === "new") {
    if (new Date(c.contact_due_at) < new Date()) return { label: "Overdue", tone: "alert", urgency: 0 };
    if (c.contact_attempts > 0)
      return { label: `Not Reached, ${c.contact_attempts} Tries`, tone: "wait", urgency: 1 };
    return { label: "New", tone: "wait", urgency: 2 };
  }
  if (c.status === "naat_positive") return { label: "Start Treatment", tone: "alert", urgency: 0 };
  if (c.status === "contacted") return { label: "Book X-Ray Van", tone: "wait", urgency: 3 };
  if (c.status === "xray_booked" && c.xray_slot)
    return { label: `X-Ray ${shortDay(c.xray_slot.day)}`, tone: "ok", urgency: 5 };
  if (c.status === "xray_done") return { label: "Get Combined Risk", tone: "wait", urgency: 3 };
  if (c.status === "risk_combined")
    return c.combined_action === "routine_care"
      ? { label: "X-Ray Clear", tone: "ok", urgency: 4 }
      : { label: "Awaiting NAAT", tone: "wait", urgency: 4 };
  if (c.status === "on_treatment") return { label: "On Treatment", tone: "ok", urgency: 9 };
  return { label: "Closed", tone: "neutral", urgency: 9 };
}

function CaseRow({ c, onOpen }: { c: Case; onOpen: () => void }) {
  const badge = caseBadge(c);
  return (
    <li>
      <button
        type="button"
        onClick={onOpen}
        className="hover:bg-secondary/60 -mx-2 flex w-[calc(100%+1rem)] items-center gap-3 rounded-lg border-t px-2 py-3.5 text-left first:border-t-0"
      >
        <div className="min-w-0 flex-1">
          <p className="font-medium">Case {c.case_id}</p>
          <p className="text-muted-foreground truncate text-xs">
            {c.sex === "F" ? "Female" : "Male"}, {c.age} · ASHA {c.asha_name} · {when(c.forwarded_at)}
          </p>
        </div>
        <Pill tone={badge.tone} dot>
          {badge.label}
        </Pill>
        <ChevronRight className="text-muted-foreground size-4 shrink-0" aria-hidden />
      </button>
    </li>
  );
}

function PatientRow({ e, onOpen }: { e: RiskEntry; onOpen: () => void }) {
  const p = e.patient;
  const stage = treatmentStage(p.days_on_treatment);
  const colour = e.risk_score >= 0.6 ? "text-alert" : e.risk_score >= 0.4 ? "text-wait" : "text-ok";
  return (
    <li>
      <button
        type="button"
        onClick={onOpen}
        className="hover:bg-secondary/60 -mx-2 flex w-[calc(100%+1rem)] items-start gap-3 rounded-lg border-t px-2 py-3.5 text-left first:border-t-0"
      >
        <div className="flex min-w-0 flex-1 flex-col gap-2">
          <div>
            <p className="font-medium">{p.patient_id}</p>
            <p className="text-muted-foreground text-xs">
              Month {stage.month} of 6 · {p.phc ?? p.district}
            </p>
          </div>
          {e.reasons.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {e.reasons.slice(0, 2).map((r) => (
                <Pill key={r} tone={/isoscreen|no dose|side effect/i.test(r) ? "alert" : "wait"}>
                  {titleCase(r)}
                </Pill>
              ))}
            </div>
          )}
        </div>
        <div className="text-right">
          <div className={`text-2xl font-semibold tabular-nums ${colour}`}>{percent(e.risk_score)}</div>
          <div className="text-muted-foreground text-xs">Dropout Risk</div>
        </div>
      </button>
    </li>
  );
}

function SuggestionCard(props: { a: Action; onOpen: () => void; onDecide: (d: "approve" | "reject") => void }) {
  const { a } = props;
  return (
    <div className="border-primary/25 bg-accent flex flex-col gap-2 rounded-xl border p-4">
      <div className="flex flex-wrap items-center justify-between gap-x-2 gap-y-1">
        <span className="text-primary text-xs font-semibold">
          {ACTION_TYPE[a.type]} · Suggested by TBC²
        </span>
        <button type="button" onClick={props.onOpen} className="text-primary font-mono text-xs hover:underline">
          {a.patient_id}
        </button>
      </div>
      <p className="text-sm">{a.draft}</p>
      <p className="text-muted-foreground text-xs">Why: {titleCase(a.reason.split("; ")[0] ?? "")}</p>
      {a.status === "pending" ? (
        <div className="flex gap-2 pt-1">
          <Button size="sm" onClick={() => props.onDecide("approve")}>
            Approve
          </Button>
          <Button size="sm" variant="outline" onClick={() => props.onDecide("reject")}>
            Reject
          </Button>
        </div>
      ) : (
        <Pill tone={a.status === "approved" ? "ok" : "neutral"} className="self-start">
          {a.status === "approved" ? "Approved · Sent to ASHA" : "Rejected"}
        </Pill>
      )}
    </div>
  );
}

function AshaPortal() {
  const [overview, setOverview] = useState<Overview | null>(null);
  const [cases, setCases] = useState<Case[]>([]);
  const [risk, setRisk] = useState<RiskEntry[]>([]);
  const [actions, setActions] = useState<Action[]>([]);
  const [slots, setSlots] = useState<VanSlot[]>([]);
  const [openCase, setOpenCase] = useState<string | null>(null);
  const [openPatient, setOpenPatient] = useState<string | null>(null);
  const [showAll, setShowAll] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const week = useThisWeek();

  const load = useCallback(() => {
    Promise.all([
      getOverview(DISTRICT),
      getCases(DISTRICT),
      getWeeklyRisk(200, DISTRICT),
      getActions(),
      getVanSlots(DISTRICT),
    ])
      .then(([o, c, r, a, s]) => {
        setOverview(o);
        setCases(c);
        setRisk(r);
        setActions(a);
        setSlots(s);
      })
      .catch(() => setError("Could not reach the back end. Is it running?"));
  }, []);

  useEffect(load, [load]);

  // Only suggestions for patients in this district.
  const here = new Set(risk.map((e) => e.patient.patient_id));
  const suggestions = actions.filter((a) => here.has(a.patient_id));
  const waiting = suggestions.filter((a) => a.status === "pending").length;
  const open = cases
    .filter((c) => !FINISHED.includes(c.status))
    .sort((a, b) => caseBadge(a).urgency - caseBadge(b).urgency);
  const done = cases.filter((c) => FINISHED.includes(c.status));
  const shownRisk = showAll ? risk : risk.slice(0, SHOW_PATIENTS);
  const selectedCase = cases.find((c) => c.case_id === openCase) ?? null;
  const selectedPatient = risk.find((e) => e.patient.patient_id === openPatient) ?? null;

  async function decide(id: number, decision: "approve" | "reject") {
    try {
      const updated = await decideAction(id, decision);
      setActions((list) => list.map((a) => (a.action_id === id ? updated : a)));
    } catch {
      setError("Could not save that decision. Refresh and try again.");
    }
  }

  return (
    <>
      <AppHeader who="ASHA Mahadevamma S. · Hanur" />
      <main className="mx-auto flex w-full max-w-[1440px] flex-1 flex-col gap-6 px-4 py-8 sm:px-8">
        <div className="bg-card/85 flex flex-wrap items-end justify-between gap-4 rounded-2xl border px-6 py-5 backdrop-blur-sm">
          <div>
            <p className="text-primary text-sm font-medium">{DISTRICT} District · This Week</p>
            <h1 className="text-4xl font-bold tracking-tight">Overview</h1>
          </div>
          {week && (
            <span className="bg-card inline-flex items-center gap-2 rounded-xl border px-4 py-2 text-sm">
              <CalendarDays className="size-4" aria-hidden /> {week}
            </span>
          )}
        </div>

        {error && <p className="text-destructive text-sm">{error}</p>}

        <JourneyCard
          overview={overview}
          title="Patient Journey"
          subtitle="From the First Check at the Counter to Starting Treatment"
        />

        {/* The main section: suggestions waiting for the ASHA's decision. */}
        <section className="border-primary/40 bg-card overflow-hidden rounded-2xl border-2">
          <div className="bg-primary text-primary-foreground flex flex-wrap items-center justify-between gap-3 px-6 py-4">
            <div>
              <h2 className="text-lg font-semibold">Suggested by TBC²</h2>
              <p className="text-primary-foreground/80 text-sm">
                Next Steps for Your Patients · Nothing Is Sent Until You Approve It
              </p>
            </div>
            <span className="bg-primary-foreground text-primary rounded-full px-3 py-1 text-sm font-semibold">
              {waiting} Waiting for You
            </span>
          </div>
          <div className="grid gap-4 p-6 md:grid-cols-2 xl:grid-cols-3">
            {suggestions.map((a) => (
              <SuggestionCard
                key={a.action_id}
                a={a}
                onOpen={() => setOpenPatient(a.patient_id)}
                onDecide={(d) => decide(a.action_id, d)}
              />
            ))}
            {suggestions.length === 0 && (
              <p className="text-muted-foreground py-6 text-sm">No Suggestions Right Now</p>
            )}
          </div>
        </section>

        <div className="grid items-start gap-6 lg:grid-cols-2">
          <Panel
            title="Forwarded Cases"
            subtitle="Contact Them, Book the X-Ray Van and Record Results"
            right={<CountPill>{open.length} Open</CountPill>}
          >
            <ul className="flex flex-col">
              {open.map((c) => (
                <CaseRow key={c.case_id} c={c} onOpen={() => setOpenCase(c.case_id)} />
              ))}
            </ul>
            {open.length === 0 && (
              <p className="text-muted-foreground py-6 text-center text-sm">No Open Cases</p>
            )}
            {done.length > 0 && (
              <details className="mt-3 text-sm">
                <summary className="text-muted-foreground cursor-pointer">Completed ({done.length})</summary>
                <ul className="mt-2 flex flex-col">
                  {done.map((c) => (
                    <CaseRow key={c.case_id} c={c} onOpen={() => setOpenCase(c.case_id)} />
                  ))}
                </ul>
              </details>
            )}
          </Panel>

          <Panel
            title="Likely to Stop Treatment"
            subtitle="From Daily Self-Reports, IsoScreen Tests and Side Effects"
          >
            <ul className="flex flex-col">
              {shownRisk.map((e) => (
                <PatientRow
                  key={e.patient.patient_id}
                  e={e}
                  onOpen={() => setOpenPatient(e.patient.patient_id)}
                />
              ))}
            </ul>
            {risk.length > SHOW_PATIENTS && (
              <Button variant="ghost" className="mt-2" onClick={() => setShowAll((s) => !s)}>
                {showAll ? "Show Fewer" : `Show All ${risk.length} Patients`}
              </Button>
            )}
          </Panel>
        </div>
      </main>
      <AppFooter />

      {selectedCase && (
        <CaseDrawer
          key={selectedCase.case_id}
          c={selectedCase}
          slots={slots}
          onClose={() => setOpenCase(null)}
          onOpenPatient={(id) => {
            setOpenCase(null);
            setOpenPatient(id);
          }}
          onChange={(updated) => {
            setCases((list) => list.map((c) => (c.case_id === updated.case_id ? updated : c)));
            // Counts, van places and (after treatment starts) the patient list may change.
            Promise.all([getOverview(DISTRICT), getVanSlots(DISTRICT), getWeeklyRisk(200, DISTRICT)])
              .then(([o, s, r]) => {
                setOverview(o);
                setSlots(s);
                setRisk(r);
              })
              .catch(() => {});
          }}
        />
      )}
      {selectedPatient && (
        <PatientDrawer
          key={selectedPatient.patient.patient_id}
          entry={selectedPatient}
          onClose={() => setOpenPatient(null)}
          onChange={(updated) =>
            setRisk((list) =>
              list.map((e) => (e.patient.patient_id === updated.patient.patient_id ? updated : e)),
            )
          }
        />
      )}
    </>
  );
}

// Only signed-in ASHAs (when login is on).
export default function AshaPage() {
  return (
    <AuthGate role="asha">
      <AshaPortal />
    </AuthGate>
  );
}
