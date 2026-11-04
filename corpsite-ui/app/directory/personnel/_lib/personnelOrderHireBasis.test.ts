import {expect,it} from 'vitest';
import {hireBasisFromPayload,hireBasisForEditing,setHireBasisText,newHireBasis} from './personnelOrderHireBasis';
it('proposes standard KK only in the editor without modifying saved data and preserves intentional clearing',()=>{
  const saved={hire_basis:{ru:'личное заявление, трудовой договор',kk:''}};
  const before=JSON.stringify(saved);
  expect(hireBasisFromPayload(saved).kk).toBe('');
  const proposal=hireBasisForEditing(saved);
  expect(proposal.kk).toBe('жеке өтініші, еңбек шарты');
  expect(JSON.stringify(saved)).toBe(before);
  const cleared=setHireBasisText(proposal,'kk','');
  expect(cleared.kk_intentionally_empty).toBe(true);
  expect(hireBasisForEditing({hire_basis:JSON.parse(JSON.stringify(cleared))}).kk).toBe('');
  expect(hireBasisForEditing({hire_basis:{ru:'Индивидуальное основание',kk:''}}).kk).toBe('');
  expect(hireBasisForEditing({hire_basis:{ru:saved.hire_basis.ru,kk:'Ручной KK'}}).kk).toBe('Ручной KK');
});
it('keeps explicit RU/KK defaults and edits separate, including a missing KK',()=>{
  expect(newHireBasis()).toEqual({ru:'личное заявление, трудовой договор',kk:'жеке өтініші, еңбек шарты'});
  const value={hire_basis:{ru:'Ручное RU',kk:''},basis_other_text:'STALE RU'};
  expect(hireBasisFromPayload(value,'kk')).toEqual({ru:'Ручное RU',kk:''});
  expect(value.basis_other_text).toBe('STALE RU');
});
it('uses only the legacy source language and strictly localized linked descriptions',()=>{
  const value={basis_other_text:'OLD',basis_ids:['one']};
  const docs=[{basis_id:'one',description:{ru:'DOC RU',kk:''}}];
  expect(hireBasisFromPayload(value,'ru',docs)).toEqual({ru:'DOC RU\nOLD',kk:''});
  expect(hireBasisFromPayload(value,'kk',docs)).toEqual({ru:'DOC RU',kk:'OLD'});
});
