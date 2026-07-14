import EmployeeImportCard2PageClient from "../../../_components/EmployeeImportCard2PageClient";

export const dynamic = "force-dynamic";

export default async function EmployeeCardPage({
  params,
}: {
  params: Promise<{ employeeId: string }>;
}) {
  const { employeeId } = await params;
  return <EmployeeImportCard2PageClient employeeId={employeeId} />;
}
