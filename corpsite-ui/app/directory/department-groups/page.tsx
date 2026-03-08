// FILE: corpsite-ui/app/directory/department-groups/page.tsx

import { notFound } from "next/navigation";
import DictionaryPageClient from "../_components/DictionaryPageClient";
import { getDictionaryConfig } from "../_lib/dictionaries.config";

export default function DepartmentGroupsPage() {
  const config = getDictionaryConfig("department-groups");

  if (!config) {
    notFound();
  }

  return <DictionaryPageClient config={config} />;
}