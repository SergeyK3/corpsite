// FILE: corpsite-ui/app/regular-tasks/page.tsx
import { redirect } from "next/navigation";

import { buildLegacyRegularTaskTemplatesHref } from "../admin/templates/_lib/templateSections";

export const dynamic = "force-dynamic";

type Props = {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
};

export default async function RegularTasksAdminPage({ searchParams }: Props) {
  redirect(buildLegacyRegularTaskTemplatesHref(await searchParams));
}
