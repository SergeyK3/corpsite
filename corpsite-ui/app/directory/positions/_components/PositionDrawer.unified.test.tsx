import {apiFetchJson} from "@/lib/api";
import PositionForm from "./PositionForm";
import * as React from 'react';
import {cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react';
import {afterEach,expect,it,vi} from 'vitest';
import PositionDrawer from './PositionDrawer';
vi.mock('@/lib/api',()=>({apiFetchJson:vi.fn(async()=>({items:[{job_code:'CLINICAL_DEPARTMENT_HEAD',job_nameru:'Заведующий клиническим отделением',job_namekk:'Клиникалық бөлімше меңгерушісі',job_namekk_doc:'клиникалық бөлімшесінің меңгерушісі'}]}))}));
afterEach(cleanup);
it('keeps the server failure beside Save outside the scrolling inputs without clearing the draft',async()=>{
 const submit=vi.fn().mockRejectedValue(new Error('Причина отказа сервера (HTTP 422)'));
 render(<PositionForm mode="create" initialValues={{name:'Рентген лаборант',category:'medical'}} onCancel={vi.fn()} onSubmit={submit}/>);
 fireEvent.change(screen.getByLabelText('Документная форма KK'),{target:{value:'Сохранить ручной ввод'}});
 fireEvent.click(screen.getByRole('button',{name:'Сохранить'}));
 const alert=await screen.findByRole('alert');
 expect(alert).toHaveTextContent('Причина отказа сервера (HTTP 422)');
 expect(screen.getByTestId('position-save-footer')).toContainElement(alert);
 expect(screen.getByLabelText('Документная форма KK')).toHaveValue('Сохранить ручной ввод');
 expect(screen.queryByRole('button',{name:'Сохранено'})).not.toBeInTheDocument();
});
it('does not silently accept a save handler that returns no confirmation',async()=>{
 render(<PositionForm mode="create" initialValues={{name:'Рентген лаборант',category:'medical'}} onCancel={vi.fn()} onSubmit={vi.fn()}/>);
 fireEvent.click(screen.getByRole('button',{name:'Сохранить'}));
 expect(await screen.findByRole('alert')).toHaveTextContent('Сохранение не подтверждено');
});
it('keeps exact variant and manual fields after saving state or a server conflict',async()=>{
 const position={position_id:71,name:'Заведующий отделением химиотерапии 1',name_kk:'№ 1 химиотерапия бөлімшесінің меңгерушісі',category:'leaders',job_code:'CLINICAL_DEPARTMENT_HEAD',revision:12,document_form_status:'needs_review' as const};
 const submit=vi.fn();const props={open:true,mode:'edit' as const,position,onClose:vi.fn(),onSubmit:submit};
 const view=render(<PositionDrawer {...props}/>);
 await waitFor(()=>expect(screen.getByRole('option',{name:/CLINICAL_DEPARTMENT_HEAD/})).toBeInTheDocument());
 fireEvent.change(screen.getByLabelText('Документная форма KK'),{target:{value:'Ручная правка формы'}});
 view.rerender(<PositionDrawer {...props} saving/>);
 view.rerender(<PositionDrawer {...props} error="Конфликт версии"/>);
 expect(screen.getByLabelText('Документная форма KK')).toHaveValue('Ручная правка формы');
 expect(screen.getByLabelText(/Название должности/)).toHaveValue(position.name);
 expect(screen.getByLabelText('Статус документной формы KK')).toHaveValue('needs_review');
 fireEvent.click(screen.getByRole('button',{name:'Сохранить'}));
 await waitFor(()=>expect(submit).toHaveBeenCalledWith(expect.objectContaining({name:position.name,job_code:position.job_code,expected_revision:12,document_possessive_kk:'Ручная правка формы'})));
 expect(submit.mock.calls[0][0]).not.toHaveProperty('position_id');
 expect(submit.mock.calls[0][0]).not.toHaveProperty('revision');
});

it('closes an obsolete family editor when the selected family is corrected',async()=>{
 vi.mocked(apiFetchJson).mockResolvedValue({items:[{job_code:'WRONG_TEST',job_nameru:'Ошибочный тестовый вид',job_namekk:'ТЕСТ',job_namekk_doc:'ТЕСТ'},{job_code:'CORRECT_TEST',job_nameru:'Исправленный тестовый вид',job_namekk:'ТЕСТ',job_namekk_doc:'ТЕСТ'}]});
 const submit=vi.fn();
 function Harness(){return <PositionForm mode="create" initialValues={{name:'Рентген лаборант',category:'medical',job_code:'WRONG_TEST',name_kk:'ТЕСТ: KK'}} onCancel={vi.fn()} onSubmit={submit}/>;}
 render(<Harness/>);await screen.findByRole('option',{name:/WRONG_TEST/});
 fireEvent.click(screen.getByText('Настройки общего вида'));fireEvent.click(screen.getByRole('button',{name:'Редактировать или добавить общий вид'}));
 expect(screen.getByLabelText('Код общего вида')).toHaveValue('WRONG_TEST');
 fireEvent.change(screen.getByLabelText('Общий вид должности'),{target:{value:'CORRECT_TEST'}});
 expect(screen.queryByRole('button',{name:'Сохранить общий вид'})).not.toBeInTheDocument();
 fireEvent.click(screen.getByRole('button',{name:'Сохранить'}));await waitFor(()=>expect(submit).toHaveBeenCalledWith(expect.objectContaining({job_code:'CORRECT_TEST',name:'Рентген лаборант',name_kk:'ТЕСТ: KK'})));
 expect(screen.queryByRole('button',{name:'Сохранено'})).not.toBeInTheDocument();
});
