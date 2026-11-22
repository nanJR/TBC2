// The "Recent screenings" card on the counter portal: each person checked, their cough
// risk, and what happened next (forwarded to an ASHA, dismissed, or still waiting).

import { Pill } from "@/components/pill";
import type { Screening } from "@/lib/api";
import { BAND, DISMISS_REASONS, percent, when } from "@/lib/labels";

const DISMISSED = Object.fromEntries(DISMISS_REASONS.map((d) => [d.value, d.label]));

function Outcome({ s }: { s: Screening }) {
  if (s.decision === "forwarded") {
    return (
      <Pill tone="ok" dot>
        Forwarded · Case {s.case_id}
      </Pill>
    );
  }
  if (s.decision === "dismissed") {
    return <Pill>{s.dismiss_reason ? DISMISSED[s.dismiss_reason] : "Dismissed"}</Pill>;
  }
  return (
    <Pill tone="wait" dot>
      Awaiting Decision
    </Pill>
  );
}

export function RecentScreenings({ screenings }: { screenings: Screening[] }) {
  if (screenings.length === 0) {
    return <p className="text-muted-foreground py-8 text-center text-sm">No Screenings Yet</p>;
  }
  return (
    <ul className="flex flex-col">
      {screenings.map((s) => (
        <li key={s.screening_id} className="flex items-center gap-3 border-t py-3.5 first:border-t-0">
          <div className="min-w-0 flex-1">
            <p className="font-medium">
              {s.sex === "F" ? "Female" : "Male"}, {s.age}
              <span className="text-muted-foreground font-normal"> · {s.district}</span>
            </p>
            <p className="text-muted-foreground text-xs">
              {when(s.screened_at)}
              {s.abha_linked && " · ABHA"}
              {s.cough_risk !== null && s.risk_band && (
                <> · {BAND[s.risk_band].label} ({percent(s.cough_risk)})</>
              )}
            </p>
          </div>
          <Outcome s={s} />
        </li>
      ))}
    </ul>
  );
}
