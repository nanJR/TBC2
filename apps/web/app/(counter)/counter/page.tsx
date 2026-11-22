"use client";
// Counter portal, for a pharmacist or local practitioner. Layout follows the Figma:
// the patient-journey card on top, then three cards: New screening, Result and
// Recent screenings. The (counter) folder groups pages without adding to the URL.
//
// The practitioner only sees the cough risk score and the recommended action, and
// decides by hand whether to forward the person to an ASHA.

import { useCallback, useEffect, useState } from "react";
import { CalendarDays } from "lucide-react";

import { AppFooter } from "@/components/app-footer";
import { AuthGate } from "@/components/auth-gate";
import { AppHeader } from "@/components/app-header";
import { NewScreening } from "@/components/counter/new-screening";
import { RecentScreenings } from "@/components/counter/recent-screenings";
import { ResultPanel } from "@/components/counter/result-panel";
import { JourneyCard } from "@/components/journey-card";
import { CountPill, Panel } from "@/components/panel";
import { ReferralSlip } from "@/components/referral-slip";
import {
  getDistricts,
  getOverview,
  getScreenings,
  type Case,
  type Overview,
  type Screening,
  type ScreenResult,
} from "@/lib/api";
import { useThisWeek } from "@/lib/week";

const DISTRICT = "Chamarajanagar"; // the demo counter is in Hanur taluk, a rural forest-fringe area

function CounterPortal() {
  const [districts, setDistricts] = useState<string[]>([DISTRICT]);
  const [overview, setOverview] = useState<Overview | null>(null);
  const [screenings, setScreenings] = useState<Screening[]>([]);
  const [result, setResult] = useState<ScreenResult | null>(null);
  const [forwarded, setForwarded] = useState<Case | null>(null);
  const [round, setRound] = useState(0); // bumping this clears the form for the next person
  const [error, setError] = useState<string | null>(null);
  const week = useThisWeek();

  const refresh = useCallback(() => {
    Promise.all([getOverview(DISTRICT), getScreenings(12)])
      .then(([o, s]) => {
        setOverview(o);
        setScreenings(s);
      })
      .catch(() => setError("Could not reach the back end. Is it running?"));
  }, []);

  useEffect(() => {
    getDistricts().then(setDistricts).catch(() => {});
    refresh();
  }, [refresh]);

  const waiting = screenings.filter((s) => s.decision === "pending").length;

  return (
    <>
      <AppHeader who="Pharmacist · Hanur" />
      <main className="mx-auto flex w-full max-w-[1440px] flex-1 flex-col gap-6 px-4 py-8 sm:px-8 print:hidden">
        {/* A solid band, so the title stands clear of the background drawings. */}
        <div className="bg-card/85 flex flex-wrap items-end justify-between gap-4 rounded-2xl border px-6 py-5 backdrop-blur-sm">
          <div>
            <p className="text-primary text-sm font-medium">{DISTRICT} District · This Week</p>
            <h1 className="text-4xl font-bold tracking-tight">Counter</h1>
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

        <div className="grid items-start gap-6 lg:grid-cols-3">
          <Panel title="New Screening" subtitle="Symptoms and a Cough Recording">
            <NewScreening
              key={round}
              districts={districts}
              onScreened={(r) => {
                setResult(r);
                setForwarded(null);
                refresh();
              }}
            />
          </Panel>

          <Panel title="Result" subtitle="Cough Risk and Recommended Action">
            <ResultPanel
              key={result?.screening_id ?? "empty"}
              result={result}
              onDecided={(c) => {
                setForwarded(c);
                refresh();
              }}
              onPrint={() => window.print()}
              onNext={() => {
                setResult(null);
                setForwarded(null);
                setRound((n) => n + 1);
              }}
            />
          </Panel>

          <Panel
            title="Recent Screenings"
            subtitle="What Happened After Each Check"
            right={
              waiting > 0 && <CountPill>{waiting} Waiting</CountPill>
            }
          >
            <RecentScreenings screenings={screenings} />
          </Panel>
        </div>
      </main>
      <AppFooter />

      {/* Only the slip is printed; everything else is hidden on paper. */}
      {forwarded && (
        <div className="hidden p-8 print:block">
          <ReferralSlip forwarded={forwarded} />
        </div>
      )}
    </>
  );
}

// Only signed-in pharmacists or practitioners (when login is on).
export default function CounterPage() {
  return (
    <AuthGate role="practitioner">
      <CounterPortal />
    </AuthGate>
  );
}
