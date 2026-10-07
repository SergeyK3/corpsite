import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import PersonnelTemplateTypeDialog from "./PersonnelTemplateTypeDialog";
import { changePersonnelTemplateType, type PersonnelOrderTemplateDraft, type PersonnelOrderTemplateCatalogItem } from "../_lib/personnelOrderTemplatesApi.client";
const state = vi.hoisted(() => ({language: 'ru' as 'ru' | 'kk'}));
vi.mock("@/app/directory/personnel/_lib/personnelSectionLanguage", () => ({usePersonnelSectionLanguage: () => state}));
vi.mock("../_lib/personnelOrderTemplatesApi.client", () => ({changePersonnelTemplateType: vi.fn()}));
afterEach(() => {cleanup();vi.resetAllMocks();state.language='ru';});
const draft = {template_id:101,template_version_id:1327,revision:3,item_type_code:'RETURN_FROM_CHILDCARE_LEAVE',name_ru:'Об отзыве из отпуска',name_kk:'Еңбек демалысынан шақырту туралы'} as PersonnelOrderTemplateDraft;
const catalog = [{type_code:'RETURN_FROM_CHILDCARE_LEAVE',title_ru:'Выход из ухода',title_kk:'Бала күтімінен шығу'},{type_code:'LEAVE.ANNUAL.RECALL',title_ru:'Отзыв',title_kk:'Шақырту'}] as PersonnelOrderTemplateCatalogItem[];
it.each(['ru','kk'] as const)('changes only the type of the exact saved draft in %s', async language => {
  state.language=language; const changed=vi.fn(); const result={...draft,item_type_code:'LEAVE.ANNUAL.RECALL',revision:4};
  vi.mocked(changePersonnelTemplateType).mockResolvedValue(result);
  render(<PersonnelTemplateTypeDialog draft={draft} catalog={catalog} onClose={vi.fn()} onChanged={changed}/>);
  const label=language==='kk'?'Бұйрық түрі':'Вид приказа';
  fireEvent.change(screen.getByLabelText(label),{target:{value:'LEAVE.ANNUAL.RECALL'}});
  fireEvent.click(screen.getByRole('button',{name:language==='kk'?'Түрді өзгерту':'Изменить вид',exact:true}));
  await waitFor(() => expect(changed).toHaveBeenCalledWith(result));
  expect(changePersonnelTemplateType).toHaveBeenCalledWith(draft,'LEAVE.ANNUAL.RECALL');
  expect(screen.getByText(language==='kk'?draft.name_kk!:draft.name_ru!)).toBeVisible();
});
it('shows the concrete reason when a used draft cannot change type', async () => {
  vi.mocked(changePersonnelTemplateType).mockRejectedValue(new Error('Шаблон использован; изменение вида недоступно'));
  const changed=vi.fn();render(<PersonnelTemplateTypeDialog draft={draft} catalog={catalog} onClose={vi.fn()} onChanged={changed}/>);
  fireEvent.change(screen.getByLabelText('Вид приказа'),{target:{value:'LEAVE.ANNUAL.RECALL'}});
  fireEvent.click(screen.getByRole('button',{name:'Изменить вид',exact:true}));
  expect(await screen.findByRole('alert')).toHaveTextContent('Шаблон использован');expect(changed).not.toHaveBeenCalled();
});
