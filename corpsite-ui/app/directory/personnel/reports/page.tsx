import { redirect } from "next/navigation";

export const dynamic = "force-dynamic";

type Props = {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
};

function firstValue(value: string | string[] | undefined): string {
  return Array.isArray(value) ? value[0] || "" : value || "";
}

export default async function PersonnelReportsPage({ searchParams }: Props) {
  const params = await searchParams;
  const legacySection = firstValue(params.section).toLowerCase();
  const legacyReport = firstValue(params.report).toLowerCase();
  const opensOrdersReport = legacySection === "orders" || legacyReport === "orders-summary";

  redirect(
    opensOrdersReport
      ? "/directory/personnel/orders?view=reports"
      : "/directory/staff?view=reports",
  );
}
