// A printable referral slip for a person forwarded to an ASHA. They keep it, and show it
// at the X-ray van or the PHC. It never says "you have TB": a screen only finds people
// who need a test, and only the test can confirm TB.

import type { Case } from "@/lib/api";
import { ACTION } from "@/lib/labels";

export function ReferralSlip({ forwarded }: { forwarded: Case }) {
  const issued = new Date(forwarded.forwarded_at).toLocaleDateString("en-IN");
  return (
    <div className="mx-auto max-w-md rounded-xl border-2 border-black p-6 text-sm">
      <p className="text-lg font-semibold">TBC² · {ACTION[forwarded.counter_action].title}</p>
      <p className="text-muted-foreground">
        Case {forwarded.case_id} · {issued} · {forwarded.practitioner}
      </p>

      <p className="mt-4 font-medium">Why you were referred</p>
      <ul className="list-disc pl-5">
        {forwarded.counter_reasons.map((reason) => (
          <li key={reason}>{reason}</li>
        ))}
      </ul>

      <p className="mt-4 font-medium">What happens next</p>
      <p>
        ASHA {forwarded.asha_name} will contact you within 2 days to arrange a free chest X-ray
        at the mobile X-ray van, and a sputum test if needed. Both are free under the National TB
        Elimination Programme.
      </p>

      <p className="mt-4 border-t pt-3">
        Questions? Ni-kshay Sampark TB helpline: <b>1800-11-6666</b> (toll-free)
      </p>
    </div>
  );
}
