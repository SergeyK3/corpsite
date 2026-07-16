import PprPersonalCardPageClient from "../../../_components/PprPersonalCardPageClient";

export const dynamic = "force-dynamic";

export default async function PersonCardPage({
  params,
}: {
  params: Promise<{ personId: string }>;
}) {
  const { personId } = await params;
  return <PprPersonalCardPageClient personId={personId} />;
}
