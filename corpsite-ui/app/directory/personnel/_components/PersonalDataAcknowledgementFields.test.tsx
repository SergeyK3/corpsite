import {cleanup,render,screen} from '@testing-library/react';
import {afterEach,expect,it,vi} from 'vitest';
import PersonalDataAcknowledgementFields from './PersonalDataAcknowledgementFields';
afterEach(cleanup);
it('does not require new given names and previews unchanged source initials',()=>{
 render(<PersonalDataAcknowledgementFields value={{new_surname_ru:'Новая',new_surname_kk:'Жаңа',new_given_name_ru:'',new_given_name_kk:''}} sourceGivenNames={{ru:'Айдар',kk:'Әли'}} onChange={vi.fn()}/>);
 expect(screen.getByLabelText('Новое имя RU')).not.toBeRequired();expect(screen.getByLabelText('Новое имя KK')).not.toBeRequired();
 expect(screen.getByTestId('personal-data-acknowledgement-preview')).toHaveTextContent('Новая А.');expect(screen.getByTestId('personal-data-acknowledgement-preview')).toHaveTextContent('Ә. Жаңа');
});
it('has only the existing four fields and does not ask for a manual initial',()=>{
 render(<PersonalDataAcknowledgementFields value={{new_surname_ru:'Ержанова',new_surname_kk:'Ержанова',new_given_name_ru:'',new_given_name_kk:''}} sourceGivenNames={{ru:'Айгерим',kk:'Айгерим'}} onChange={vi.fn()}/>);
 expect(screen.queryByLabelText('Инициал имени RU')).not.toBeInTheDocument();expect(screen.queryByLabelText('Инициал имени KK')).not.toBeInTheDocument();expect(screen.getAllByRole('textbox')).toHaveLength(4);
 expect(screen.getByLabelText('Новое имя RU')).not.toBeRequired();expect(screen.getByTestId('personal-data-acknowledgement-preview')).toHaveTextContent('Ержанова А.');expect(screen.getByTestId('personal-data-acknowledgement-preview')).toHaveTextContent('А. Ержанова');
});
