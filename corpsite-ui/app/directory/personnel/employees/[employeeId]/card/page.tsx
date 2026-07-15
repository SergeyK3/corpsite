import EmployeeImportCard2PageClient from "../../../_components/EmployeeImportCard2PageClient";
import PprPersonalCardPageClient from "../../../_components/PprPersonalCardPageClient";
import { isPprCardEnabled } from "@/lib/pprCardFeature";

export const dynamic = "force-dynamic";

export default async function EmployeeCardPage({
  params,
}: {
  params: Promise<{ employeeId: string }>;
}) {
  const { employeeId } = await params;
  if (isPprCardEnabled()) {
    return <PprPersonalCardPageClient employeeId={employeeId} />;
  }
  return <EmployeeImportCard2PageClient employeeId={employeeId} />;
}
