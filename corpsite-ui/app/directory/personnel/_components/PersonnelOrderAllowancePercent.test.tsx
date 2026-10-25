import {useState} from 'react';
import {cleanup,fireEvent,render,screen} from '@testing-library/react';
import {afterEach,expect,it} from 'vitest';
import Percent from './PersonnelOrderAllowancePercent';
import {allowancePercentError} from '../_lib/personnelOrderAllowancePercent';
afterEach(cleanup);
it('keeps quick presets and accepts custom whole values without a step of five',()=>{
 function Harness(){const [value,setValue]=useState('25');return <Percent value={value} onChange={setValue} inputClassName=""/>;}
 render(<Harness/>);
 fireEvent.change(screen.getByLabelText('Доплата'),{target:{value:'other'}});
 const input=screen.getByLabelText('Процент доплаты');
 fireEvent.change(input,{target:{value:'36'}});expect(input).toHaveValue(36);
 expect(input).toHaveAttribute('min','1');expect(input).toHaveAttribute('max','100');expect(input).toHaveAttribute('step','1');
 fireEvent.change(screen.getByLabelText('Доплата'),{target:{value:'50'}});
 expect(screen.getByLabelText('Доплата')).toHaveValue('50');expect(screen.queryByLabelText('Процент доплаты')).not.toBeInTheDocument();
});
it.each(['1','25','35','36','50','100'])('allows whole percent %s',v=>expect(allowancePercentError(v)).toBeNull());
it.each(['','0','101','-1','35.5','NaN','Infinity'])('rejects invalid percent %s',v=>expect(allowancePercentError(v)).not.toBeNull());
