import PersonnelImportReviewPageClient from "../../../_components/PersonnelImportReviewPageClient";

export const dynamic = "force-dynamic";

export default async function PersonnelImportReviewPage({
  params,
}: {
  params: Promise<{ batchId: string }>;
}) {
  const { batchId } = await params;
  return <PersonnelImportReviewPageClient batchId={Number(batchId)} />;
}
