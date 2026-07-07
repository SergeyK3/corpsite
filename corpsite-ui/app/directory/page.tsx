// ROUTE: /directory
// FILE: corpsite-ui/app/directory/page.tsx
import { redirect } from "next/navigation";

export const dynamic = "force-dynamic";

type Props = {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
};

/** Legacy directory hub — canonical personnel browser at /directory/staff (ADR-045, CCR-005). */
export default async function DirectoryHomePage({ searchParams }: Props) {
  const sp = await searchParams;
  const q = new URLSearchParams();
  Object.entries(sp).forEach(([k, v]) => {
    if (typeof v === "string") q.set(k, v);
  });
  const qs = q.toString();
  redirect(qs ? `/directory/staff?${qs}` : "/directory/staff");
}
