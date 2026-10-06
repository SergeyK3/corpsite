import TemplatesPageClient from "./_components/TemplatesPageClient";
import { PersonnelSectionLanguageProvider } from "@/app/directory/personnel/_lib/personnelSectionLanguage";

export default function TemplatesPage() {
  return <PersonnelSectionLanguageProvider><TemplatesPageClient /></PersonnelSectionLanguageProvider>;
}
