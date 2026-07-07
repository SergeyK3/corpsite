// ROUTE: /directory/employees/[id]
// FILE: corpsite-ui/app/directory/employees/[id]/page.tsx
import { redirect } from "next/navigation";

export const dynamic = "force-dynamic";

type Props = {
  params: Promise<{ id: string }>;
};

/** Legacy employee detail URL — opens staff drawer (ADR-045, CCR-010). */
export default async function EmployeeDetailsRedirectPage({ params }: Props) {
  const { id } = await params;
  const trimmed = String(id ?? "").trim();
  if (!trimmed) {
    redirect("/directory/staff");
  }
  redirect(`/directory/staff?employeeId=${encodeURIComponent(trimmed)}`);
}
