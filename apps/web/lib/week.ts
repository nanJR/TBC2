// "18 to 24 Nov 2026": the week (Monday to Sunday) containing today.

import { useSyncExternalStore } from "react";

function thisWeek(): string {
  const today = new Date();
  const monday = new Date(today);
  monday.setDate(today.getDate() - ((today.getDay() + 6) % 7));
  const sunday = new Date(monday);
  sunday.setDate(monday.getDate() + 6);
  const end = sunday.toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
  return `${monday.getDate()} to ${end}`;
}

// The date is only read in the browser: during the build's pre-render this gives "",
// because reading the clock there is not allowed (cacheComponents).
const noSubscribe = () => () => {};
export const useThisWeek = () => useSyncExternalStore(noSubscribe, thisWeek, () => "");
