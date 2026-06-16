import PersonnelImportAnalyticsPageClient from "../../_components/PersonnelImportAnalyticsPageClient";

export const dynamic = "force-dynamic";

type Props = { params: Promise<{ batchId: string }> };

export default async function PersonnelImportAnalyticsPage({ params }: Props) {
  const { batchId } = await params;
  const id = Number(batchId);
  return <PersonnelImportAnalyticsPageClient batchId={Number.isFinite(id) ? id : 0} />;
}
