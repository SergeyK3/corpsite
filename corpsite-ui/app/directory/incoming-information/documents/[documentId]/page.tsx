import IncomingDocumentDetailPageClient from "../../_components/IncomingDocumentDetailPageClient";

export const dynamic = "force-dynamic";

type Props = { params: Promise<{ documentId: string }> };

export default async function IncomingDocumentPage({ params }: Props) {
  const { documentId } = await params;
  return <IncomingDocumentDetailPageClient documentId={documentId} />;
}
