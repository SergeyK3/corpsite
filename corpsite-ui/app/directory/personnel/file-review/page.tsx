import PersonnelFilesPanel from "../_components/PersonnelFilesPanel";
import PersonnelLkSubNav from "../_components/PersonnelLkSubNav";

export default function FileReviewPage() {
  return <main className="mx-auto max-w-6xl pb-6"><PersonnelLkSubNav activeTab="review" /><div className="px-4"><PersonnelFilesPanel personId={null} fullName="" queue /></div></main>;
}
