import WorkspaceDetailPageClient from "../../_components/WorkspaceDetailPageClient";

export const dynamic = "force-dynamic";

type Props = { params: Promise<{ workspaceId: string }> };

export default async function WorkspaceDetailPage({ params }: Props) {
  const { workspaceId } = await params;
  const id = Number(workspaceId);
  return <WorkspaceDetailPageClient workspaceId={id} />;
}
