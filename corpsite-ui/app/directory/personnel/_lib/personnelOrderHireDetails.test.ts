import {expect,it} from 'vitest';
import {emptyHireDetails, hireDetailsFromPayload, hireDetailsLines, hireDetailsPayload} from './personnelOrderHireDetails';
it('prints entered certificate wording independently of a linked radiology record',()=>{
 const certificate={specialty:{medical_specialty_id:41,name_ru:'Радиология',name_kk:'Радиология'},issued_on:'',name_ru:'Лучевая диагностика',name_kk:'Сәулелік диагностика'};
 const payload={hire_details:{...emptyHireDetails(),certificate}};
 expect(hireDetailsLines(payload,'ru')).toEqual(['Сертификат: Лучевая диагностика']);
 expect(hireDetailsLines(payload,'kk')).toEqual(['Сертификат: Сәулелік диагностика']);
 expect(hireDetailsFromPayload(JSON.parse(JSON.stringify(payload)))?.certificate).toEqual(certificate);
 expect(hireDetailsLines({hire_details:{...emptyHireDetails(),certificate:{...certificate,name_kk:''}}},'kk')).toEqual([]);
});

it.each([
  ['17,3','17.3','17,3 года','17,3 жыл'], ['17.3','17.3','17,3 года','17,3 жыл'],
  ['0','0','0 лет','0 жыл'], ['1','1','1 год','1 жыл'], ['2','2','2 года','2 жыл'],
  ['5','5','5 лет','5 жыл'], ['11','11','11 лет','11 жыл'], ['21','21','21 год','21 жыл'],
  ['22','22','22 года','22 жыл'], ['25','25','25 лет','25 жыл'], ['0,5','0.5','0,5 года','0,5 жыл'],
])('renders decimal years %s in both locales without converting into months', (input,stored,ru,kk) => {
  const payload = {hire_details:hireDetailsPayload({...emptyHireDetails(),service_length_years:input})};
  expect(payload.hire_details.service_length_years).toBe(stored);
  expect(hireDetailsLines(payload,'ru')).toEqual([`Трудовой стаж: ${ru}`]);
  expect(hireDetailsLines(payload,'kk')).toEqual([`Еңбек өтілі: ${kk}`]);
  expect(hireDetailsFromPayload(JSON.parse(JSON.stringify(payload)))?.service_length_years).toBe(stored);
});
it('preserves legacy texts and never parses them as decimal years', () => {
  const legacy = {education:{code:'',ru:'',kk:''},service_length:{ru:'17 лет и 3 месяца',kk:'Мұрағат мәтіні'}};
  expect(hireDetailsPayload(legacy)).toEqual(legacy);
  expect(hireDetailsFromPayload({hire_details:legacy})).not.toHaveProperty('service_length_years');
  expect(hireDetailsLines({hire_details:legacy},'ru')).toEqual(['Трудовой стаж: 17 лет и 3 месяца']);
  const cleared = {...legacy,service_length_years:''};
  expect(hireDetailsLines({hire_details:cleared},'ru')).toEqual([]);
  expect(hireDetailsPayload(cleared).service_length).toEqual(legacy.service_length);
  expect(hireDetailsLines({hire_details:{...legacy,service_length_years:'0'}},'ru')).toEqual(['Трудовой стаж: 0 лет']);
});
