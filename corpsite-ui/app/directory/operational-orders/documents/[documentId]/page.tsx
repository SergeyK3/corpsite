import DocumentDetailPageClient from "../../_components/DocumentDetailPageClient";

export const dynamic = "force-dynamic";

type Props = { params: Promise<{ documentId: string }> };

export default async function DocumentDetailPage({ params }: Props) {
  const { documentId } = await params;
  const id = Number(documentId);
  return <DocumentDetailPageClient documentId={id} />;
}
