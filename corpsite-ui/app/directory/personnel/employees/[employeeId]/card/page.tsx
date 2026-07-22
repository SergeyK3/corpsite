import { Suspense } from "react";
import { notFound } from "next/navigation";

import EmployeePersonalCardRedirectClient from "../../../_components/EmployeePersonalCardRedirectClient";
import {
  buildLegacyCardQueryStringFromPageSearchParams,
  parseRouteEmployeeId,
} from "@/lib/employeeCardNav";

export const dynamic = "force-dynamic";

export default async function EmployeeCardCompatibilityPage({
  params,
  searchParams,
}: {
  params: Promise<{ employeeId: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const { employeeId } = await params;
  const parsedEmployeeId = parseRouteEmployeeId(employeeId);
  if (!parsedEmployeeId) {
    notFound();
  }

  const legacyQueryString = buildLegacyCardQueryStringFromPageSearchParams(await searchParams);

  return (
    <Suspense
      fallback={
        <div className="px-4 py-16 text-center text-sm text-zinc-500">Переход к личной карточке…</div>
      }
    >
      <EmployeePersonalCardRedirectClient
        employeeId={parsedEmployeeId}
        legacyQueryString={legacyQueryString}
      />
    </Suspense>
  );
}
