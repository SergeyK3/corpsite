// FILE: corpsite-ui/app/directory/employees/page.tsx
import { redirect } from "next/navigation";

export const dynamic = "force-dynamic";

/** Legacy alias — read-only personnel browser lives at /directory/staff (ADR-045). */
export default function EmployeesPage() {
  redirect("/directory/staff");
}
