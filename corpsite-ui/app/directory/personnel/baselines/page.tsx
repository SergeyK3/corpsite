import { redirect } from "next/navigation";

export const dynamic = "force-dynamic";

export default function PersonnelBaselinesPage() {
  redirect("/directory/personnel/import#baselines");
}
