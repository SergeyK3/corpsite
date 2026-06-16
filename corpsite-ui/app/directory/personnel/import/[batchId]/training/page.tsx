import PersonnelImportTrainingPageClient from "../../../_components/PersonnelImportTrainingPageClient";

export const dynamic = "force-dynamic";

type Props = { params: Promise<{ batchId: string }> };

export default async function PersonnelImportTrainingPage({ params }: Props) {
  const { batchId } = await params;
  const id = Number(batchId);
  return <PersonnelImportTrainingPageClient batchId={Number.isFinite(id) ? id : 0} />;
}
