import {expect,it} from 'vitest';
import {personalDataTemplateIssues} from './personalDataTemplate';
const valid={title_ru:'Персональные данные',title_kk:'Жеке деректер',print_title_ru:'Персональные данные',print_title_kk:'Жеке деректер',preamble_ru:'Основание изменения',preamble_kk:'Өзгерту негізі',body_template_ru:'{{personal_data.changes_ru}}',body_template_kk:'{{personal_data.changes_kk}}',basis_template_ru:'{{identity_document.number}}',basis_template_kk:'{{identity_document.number}}'};
it('accepts real tokens and manually edited wording for name and patronymic changes',()=>{
 expect(personalDataTemplateIssues(valid)).toEqual([]);
 expect(personalDataTemplateIssues({...valid,body_template_ru:'Имя и отчество уточняет кадровик: '+valid.body_template_ru})).toEqual([]);
});
it.each(['body_template_ru','body_template_kk','basis_template_ru','basis_template_kk','print_title_kk'])('blocks editorial square placeholders in %s',field=>{
 expect(personalDataTemplateIssues({...valid,[field]:'[новые данные]'})).toHaveLength(1);
});
it('requires both language fields and explicit print headings',()=>{
 expect(personalDataTemplateIssues({...valid,body_template_kk:'',print_title_ru:null})).toHaveLength(2);
});
