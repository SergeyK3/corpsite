import PersonnelImportRowReviewPageClient from "../../../../_components/PersonnelImportRowReviewPageClient";

export const dynamic = "force-dynamic";

export default async function PersonnelImportRowReviewPage({
  params,
}: {
  params: Promise<{ batchId: string; rowId: string }>;
}) {
  const { batchId, rowId } = await params;
  return (
    <PersonnelImportRowReviewPageClient batchId={Number(batchId)} rowId={Number(rowId)} />
  );
}
