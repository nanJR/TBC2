// The TBC² mark, from the team's sketch: a C drawn as a circular arrow (the cycle of
// care: screen, test, treat, follow up) around the letters T and B. The C's top end
// turns into the base of the ². Built on one circle (centre 50,52, radius 38) with the
// T and B centred inside it. The B sits close to the T's stem, and the stem runs below
// the B, so it reads as "TB" rather than "T3". app/icon.svg is the same drawing for the browser tab.

import { cn } from "@/lib/utils";

export const LOGO = {
  ring: "M78.24 26.57 A38 38 0 1 0 78.24 77.43", // the C, open at the right
  // Arrowhead on the C's lower end: a filled triangle whose base sits where the C stops,
  // at right angles to the curve, with the tip straight ahead, so both sides match.
  arrow: "M83.44 82.11 L84.93 70 L73.04 72.75 Z",
  two: "M78.24 26.57 H96.24 M83.24 15.57 C83.24 12.07 86.04 10.07 89.24 10.07 C92.64 10.07 95.24 12.27 95.24 15.57 C95.24 19.07 92.24 21.57 81.24 26.57",
  t: "M32 34 H62 M44 34 V73",
  b: "M49.5 42 H58 A5.25 5.25 0 0 1 58 52.5 H54 M54 52.5 H58.5 A6.25 6.25 0 0 1 58.5 65 H49.5",
};

export function LogoMark({ className }: { className?: string }) {
  return (
    <svg
      viewBox="4 4 100 96"
      fill="none"
      stroke="currentColor"
      strokeLinecap="butt"
      strokeLinejoin="miter"
      shapeRendering="geometricPrecision"
      role="img"
      aria-label="TBC²"
      className={cn("text-primary h-9 w-auto", className)}
    >
      {/* Strokes are on the heavy side so the mark stays crisp at small sizes. */}
      <path d={LOGO.ring} strokeWidth={7} />
      <path d={LOGO.arrow} fill="currentColor" stroke="none" />
      <path d={LOGO.two} strokeWidth={5} />
      <path d={`${LOGO.t} ${LOGO.b}`} strokeWidth={6} />
    </svg>
  );
}
