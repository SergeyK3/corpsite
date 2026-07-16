import PprPersonalCardPageClient from "../../../_components/PprPersonalCardPageClient";

export const dynamic = "force-dynamic";

export default async function EmployeeCardPage({
  params,
}: {
  params: Promise<{ employeeId: string }>;
}) {
  const { employeeId } = await params;
  return <PprPersonalCardPageClient employeeId={employeeId} />;
}
