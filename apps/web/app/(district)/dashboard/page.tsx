"use client";
// District dashboard: who is most likely to stop treatment this week, where each
// patient is on the missed-dose ladder, how their golden checks went, and the
// next steps the agent suggests. A person approves or rejects every step.

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  ClipboardCheck,
  FlaskConical,
  House,
  Phone,
  Stethoscope,
  TriangleAlert,
  Users,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  decideAction,
  getActions,
  getWeeklyRisk,
  type Action,
  type LadderStep,
  type Patient,
  type RiskEntry,
} from "@/lib/api";

const HIGH_RISK = 0.6;

const ACTION_INFO: Record<Action["type"], { label: string; icon: typeof Phone }> = {
  call: { label: "Phone call", icon: Phone },
  asha_visit: { label: "Simulated ASHA visit", icon: House },
  golden_check: { label: "Golden check (urine)", icon: FlaskConical },
  side_effect_referral: { label: "Side-effect referral", icon: Stethoscope },
};

const LADDER_INFO: Record<LadderStep, { label: string; variant: "secondary" | "outline" | "destructive" }> = {
  on_track: { label: "On track", variant: "secondary" },
  call: { label: "Call due (3+ days)", variant: "outline" },
  asha_visit: { label: "Visit due (7+ days)", variant: "destructive" },
};

type Filter = "all" | "high_risk" | "ladder" | "mismatch";

const FILTERS: { value: Filter; label: string }[] = [
  { value: "all", label: "All" },
  { value: "high_risk", label: "High risk" },
  { value: "ladder", label: "On the ladder" },
  { value: "mismatch", label: "Golden-check mismatch" },
];

function hasMismatch(p: Patient): boolean {
  return p.golden_checks.some((c) => c.result === "mismatch");
}

function matchesFilter(entry: RiskEntry, filter: Filter): boolean {
  if (filter === "high_risk") return entry.risk_score >= HIGH_RISK;
  if (filter === "ladder") return entry.ladder_step !== "on_track";
  if (filter === "mismatch") return hasMismatch(entry.patient);
  return true;
}

// One number with a label, for the row of summary tiles at the top.
function StatTile(props: { label: string; value: number; icon: typeof Phone; hint: string }) {
  const Icon = props.icon;
  return (
    <Card size="sm">
      <CardContent className="flex flex-col gap-1">
        <div className="text-muted-foreground flex items-center gap-2 text-xs">
          <Icon className="size-4" aria-hidden />
          {props.label}
        </div>
        <div className="text-2xl font-semibold tabular-nums">{props.value}</div>
        <div className="text-muted-foreground text-xs">{props.hint}</div>
      </CardContent>
    </Card>
  );
}

// The last 28 days as small squares: filled = dose reported, empty = missed.
function DoseStrip({ log }: { log: Patient["dose_log_last_28_days"] }) {
  const taken = log.filter((d) => d === "taken").length;
  return (
    <div
      className="flex gap-px"
      role="img"
      aria-label={`${taken} of ${log.length} doses reported in the last ${log.length} days`}
      title={`${taken}/${log.length} doses reported (oldest left, today right)`}
    >
      {log.map((day, i) => (
        <span
          key={i}
          className={
            day === "taken"
              ? "bg-foreground/70 h-4 w-1.5 rounded-[1px]"
              : "border-destructive h-4 w-1.5 rounded-[1px] border"
          }
        />
      ))}
    </div>
  );
}

function GoldenCheckCell({ entry }: { entry: RiskEntry }) {
  const checks = entry.patient.golden_checks;
  const last = checks.at(-1);
  return (
    <div className="flex flex-col gap-0.5 text-xs">
      {hasMismatch(entry.patient) ? (
        <span className="text-destructive font-medium">Mismatch found</span>
      ) : last ? (
        <span>All {checks.length} matched</span>
      ) : (
        <span className="text-muted-foreground">None yet</span>
      )}
      <span className="text-muted-foreground">every {entry.golden_check_every_days} days</span>
    </div>
  );
}

function ActionRow(props: { action: Action; onDecide: (decision: "approve" | "reject") => void }) {
  const { action } = props;
  const info = ACTION_INFO[action.type];
  const Icon = info.icon;
  return (
    <div className="flex flex-col gap-3 rounded-lg border p-3 sm:flex-row sm:items-start">
      <Icon className="text-muted-foreground mt-0.5 size-5 shrink-0" aria-hidden />
      <div className="flex flex-1 flex-col gap-1">
        <div className="flex flex-wrap items-center gap-2 text-sm font-medium">
          {info.label}
          <span className="text-muted-foreground font-mono text-xs">{action.patient_id}</span>
          {action.status !== "pending" && (
            <Badge variant={action.status === "approved" ? "default" : "outline"}>
              {action.status}
            </Badge>
          )}
        </div>
        <p className="text-sm">{action.draft}</p>
        <p className="text-muted-foreground text-xs">Why: {action.reason}</p>
      </div>
      {action.status === "pending" && (
        <div className="flex gap-2">
          <Button size="sm" onClick={() => props.onDecide("approve")}>
            Approve
          </Button>
          <Button size="sm" variant="outline" onClick={() => props.onDecide("reject")}>
            Reject
          </Button>
        </div>
      )}
    </div>
  );
}

export default function DashboardPage() {
  const [risk, setRisk] = useState<RiskEntry[]>([]);
  const [actions, setActions] = useState<Action[]>([]);
  const [district, setDistrict] = useState("all");
  const [filter, setFilter] = useState<Filter>("all");
  const [error, setError] = useState<string | null>(null);

  // Load every patient's risk and all actions once when the page opens.
  useEffect(() => {
    Promise.all([getWeeklyRisk(100), getActions()])
      .then(([r, a]) => {
        setRisk(r);
        setActions(a);
      })
      .catch(() => setError("Could not reach the back end. Is it running?"));
  }, []);

  async function decide(id: number, decision: "approve" | "reject") {
    try {
      const updated = await decideAction(id, decision);
      // Replace just the changed action in the list.
      setActions((list) => list.map((a) => (a.action_id === id ? updated : a)));
    } catch {
      setError("Could not save that decision. Refresh and try again.");
    }
  }

  const districts = [...new Set(risk.map((r) => r.patient.district))].sort();
  const inDistrict = risk.filter((r) => district === "all" || r.patient.district === district);
  const shown = inDistrict.filter((r) => matchesFilter(r, filter));
  const pending = actions.filter((a) => a.status === "pending");
  const decided = actions.filter((a) => a.status !== "pending");
  const isMock = risk[0]?.is_mock ?? true;

  return (
    <main className="mx-auto flex w-full max-w-6xl flex-1 flex-col gap-6 px-4 py-8">
      <Link href="/" className="text-muted-foreground text-sm">
        ← Home
      </Link>

      <header className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold">District treatment dashboard</h1>
          <p className="text-muted-foreground text-sm">
            Software prototype · simulated patients · Karnataka
          </p>
        </div>
        <label className="flex items-center gap-2 text-sm">
          District
          <select
            value={district}
            onChange={(e) => setDistrict(e.target.value)}
            className="bg-background rounded-md border px-2 py-1"
          >
            <option value="all">All districts</option>
            {districts.map((d) => (
              <option key={d} value={d}>
                {d}
              </option>
            ))}
          </select>
        </label>
      </header>

      {isMock && (
        <p className="rounded-md border p-3 text-sm">
          <Badge variant="outline" className="mr-2">
            mock
          </Badge>
          Risk scores come from simple rules until the dropout model is trained. Patients are
          simulated.
        </p>
      )}
      {error && <p className="text-destructive text-sm">{error}</p>}

      <section className="grid grid-cols-2 gap-3 lg:grid-cols-5" aria-label="Summary">
        <StatTile label="On treatment" value={inDistrict.length} icon={Users} hint="simulated patients" />
        <StatTile
          label="High risk"
          value={inDistrict.filter((r) => r.risk_score >= HIGH_RISK).length}
          icon={TriangleAlert}
          hint={`score ${Math.round(HIGH_RISK * 100)}% or more`}
        />
        <StatTile
          label="Call due"
          value={inDistrict.filter((r) => r.ladder_step === "call").length}
          icon={Phone}
          hint="3–6 days without a dose"
        />
        <StatTile
          label="ASHA visit due"
          value={inDistrict.filter((r) => r.ladder_step === "asha_visit").length}
          icon={House}
          hint="7+ days without a dose"
        />
        <StatTile
          label="Awaiting approval"
          value={pending.length}
          icon={ClipboardCheck}
          hint="drafted actions"
        />
      </section>

      <Card>
        <CardHeader>
          <CardTitle>Suggested actions</CardTitle>
          <CardDescription>
            Drafted by the agent for the highest-risk patients. Nothing is sent until you approve
            it.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          {pending.length === 0 && (
            <p className="text-muted-foreground text-sm">No actions waiting. All decided.</p>
          )}
          {pending.map((a) => (
            <ActionRow key={a.action_id} action={a} onDecide={(d) => decide(a.action_id, d)} />
          ))}
          {decided.length > 0 && (
            <details className="text-sm">
              <summary className="text-muted-foreground cursor-pointer">
                Decided ({decided.length})
              </summary>
              <div className="mt-3 flex flex-col gap-3">
                {decided.map((a) => (
                  <ActionRow key={a.action_id} action={a} onDecide={() => {}} />
                ))}
              </div>
            </details>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Dropout risk this week</CardTitle>
          <CardDescription>
            Highest risk first. Doses are daily self-reports; golden checks test whether they are
            true.
          </CardDescription>
          <div className="flex flex-wrap gap-2 pt-2" role="group" aria-label="Filter patients">
            {FILTERS.map((f) => (
              <Button
                key={f.value}
                size="sm"
                variant={filter === f.value ? "default" : "outline"}
                aria-pressed={filter === f.value}
                onClick={() => setFilter(f.value)}
              >
                {f.label}
              </Button>
            ))}
          </div>
        </CardHeader>
        <CardContent className="overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Patient</TableHead>
                <TableHead>Risk</TableHead>
                <TableHead>Last 28 days</TableHead>
                <TableHead>Ladder</TableHead>
                <TableHead>Golden checks</TableHead>
                <TableHead>Top reasons</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {shown.map((r) => (
                <TableRow key={r.patient.patient_id}>
                  <TableCell>
                    <div className="font-mono text-xs">{r.patient.patient_id}</div>
                    <div className="text-muted-foreground text-xs">
                      {r.patient.district} · day {r.patient.days_on_treatment}
                    </div>
                  </TableCell>
                  <TableCell>
                    <Badge variant={r.risk_score >= HIGH_RISK ? "destructive" : "secondary"}>
                      {Math.round(r.risk_score * 100)}%
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <DoseStrip log={r.patient.dose_log_last_28_days} />
                  </TableCell>
                  <TableCell>
                    <Badge variant={LADDER_INFO[r.ladder_step].variant}>
                      {LADDER_INFO[r.ladder_step].label}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <GoldenCheckCell entry={r} />
                  </TableCell>
                  <TableCell className="text-muted-foreground max-w-xs text-xs whitespace-normal">
                    <ol className="list-decimal pl-4">
                      {r.reasons.map((reason) => (
                        <li key={reason}>{reason}</li>
                      ))}
                    </ol>
                  </TableCell>
                </TableRow>
              ))}
              {shown.length === 0 && (
                <TableRow>
                  <TableCell colSpan={6} className="text-muted-foreground text-center text-sm">
                    No patients match this filter.
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </main>
  );
}
