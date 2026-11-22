// The "Patient journey" card from the Figma: four counts in a row, each with a bar
// showing what share of the previous step made it this far.

import type { Overview } from "@/lib/api";

function Step(props: { label: string; value: number; of?: number; hint: string }) {
  // The first step is the whole group, so its bar is full.
  const share = props.of === undefined ? 1 : props.of > 0 ? props.value / props.of : 0;
  return (
    <div className="flex flex-col gap-2">
      <span className="text-muted-foreground text-sm">{props.label}</span>
      <span className="text-3xl font-semibold tabular-nums">{props.value.toLocaleString("en-IN")}</span>
      <div className="bg-secondary h-1.5 w-full max-w-72 overflow-hidden rounded-full">
        <div
          className="bg-primary h-full rounded-full"
          style={{ width: `${Math.max(2, Math.round(share * 100))}%` }}
        />
      </div>
      <span className="text-muted-foreground text-xs">{props.hint}</span>
    </div>
  );
}

const pct = (value: number, of: number) => (of > 0 ? `${Math.round((value / of) * 100)}%` : "0%");

export function JourneyCard({ overview, title, subtitle }: {
  overview: Overview | null;
  title: string;
  subtitle: string;
}) {
  // Zeros while the numbers load.
  const o = overview ?? { screened: 0, forwarded: 0, tested: 0, on_treatment: 0, overdue: 0 };
  return (
    <section className="bg-card rounded-2xl border p-6">
      <h2 className="font-semibold">{title}</h2>
      <p className="text-muted-foreground text-sm">{subtitle}</p>
      <div className="mt-6 grid grid-cols-2 gap-6 lg:grid-cols-4">
        <Step label="Screened at Counter" value={o.screened} hint="All Screenings This Week" />
        <Step
          label="Forwarded to ASHA"
          value={o.forwarded}
          of={o.screened}
          hint={`${pct(o.forwarded, o.screened)} of Screened`}
        />
        <Step
          label="Tested (X-Ray + NAAT)"
          value={o.tested}
          of={o.forwarded}
          hint={`${pct(o.tested, o.forwarded)} of Forwarded`}
        />
        <Step
          label="On Treatment"
          value={o.on_treatment}
          of={o.tested}
          hint={`${o.overdue} Case${o.overdue === 1 ? "" : "s"} Overdue for Contact`}
        />
      </div>
    </section>
  );
}
