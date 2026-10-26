import {expect,it} from 'vitest';
import {buildItemPayload,emptyItemPayloadDraft,itemPayloadDraftFromRecord} from './personnelOrderPayload';

it.each(['TRANSFER','CONCURRENT_DUTY_START'])('%s preserves optional specialty through reopen, edit and clear',type=>{
  const specialty={medical_specialty_id:9001,name_ru:'TEST specialty RU',name_kk:'TEST specialty KK'};
  const placement={position_ru:'TEST RU',position_kk:'TEST KK',org_unit_ru:'TEST unit RU',org_unit_kk:'TEST unit KK',rate:'0.5',total_rate:'1.5',basis_ru:'TEST basis RU',basis_kk:'TEST basis KK'};
  const draft={...emptyItemPayloadDraft(),medical_specialty:specialty,
    ...(type==='TRANSFER'?{transfer:placement}:{concurrent:placement})};
  const saved=buildItemPayload(type,draft);
  const reopened=itemPayloadDraftFromRecord(JSON.parse(JSON.stringify(saved)));
  expect(reopened.medical_specialty).toEqual(specialty);
  expect(buildItemPayload(type,reopened).medical_specialty).toEqual(specialty);
  const cleared=buildItemPayload(type,{...reopened,medical_specialty:null});
  expect(cleared.medical_specialty).toBeNull();
  expect(itemPayloadDraftFromRecord(cleared).medical_specialty).toBeNull();
  expect(buildItemPayload(type,{...reopened,medical_specialty:undefined})).not.toHaveProperty('medical_specialty');
});
