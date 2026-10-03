import { redirect } from "next/navigation";

export const dynamic = "force-dynamic";

export default function TestPersonnelDataPage() {
  redirect("/admin/system/data-cleanup");
}
