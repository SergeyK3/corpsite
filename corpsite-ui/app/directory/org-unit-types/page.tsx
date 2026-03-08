// FILE: corpsite-ui/app/directory/org-unit-types/page.tsx

import { notFound } from "next/navigation";
import DictionaryPageClient from "../_components/DictionaryPageClient";
import { getDictionaryConfig } from "../_lib/dictionaries.config";

export default function OrgUnitsPage() {
  const config = getDictionaryConfig("org-units");

  if (!config) {
    notFound();
  }

  return <DictionaryPageClient config={config} />;
}