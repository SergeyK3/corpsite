"use client";

import PersonnelBaselinesJournalSection from "./PersonnelBaselinesJournalSection";

/** Standalone wrapper kept for backward compatibility; route redirects to /import#baselines. */
export default function PersonnelBaselinesPageClient() {
  return <PersonnelBaselinesJournalSection />;
}
