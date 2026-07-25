import { redirect } from "next/navigation";

import { buildApplicantsRedirectTarget } from "../_lib/personnelLkNav";

export const dynamic = "force-dynamic";

type Props = {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
};

/** Legacy applicants route — preserve deep links and redirect to unified LK registry. */
export default async function PersonnelApplicantsRedirectPage({ searchParams }: Props) {
  const sp = await searchParams;
  redirect(buildApplicantsRedirectTarget(sp));
}
