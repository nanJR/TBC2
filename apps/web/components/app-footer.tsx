// The one place the pages say what this is: a prototype on simulated data.
// Kept at the bottom so the working screens stay clean.

export function AppFooter() {
  return (
    <footer className="text-muted-foreground mt-auto border-t px-4 py-6 text-center text-xs print:hidden">
      <p>
        TBC² by The MedMinds · Prototype for demonstration only, not for clinical use.
      </p>
      <p className="mt-1">
        All patient records, ABHA data, ASHA names and X-ray van schedules are simulated. No
        real patient data is used, and nothing connects to Ni-kshay or ABDM.
      </p>
    </footer>
  );
}
