import type {EmployeeDTO} from "@/app/directory/employees/_lib/types";

export type ManualOrderSubject={full_name:string;org_unit_name?:string;position_name?:string;specialty?:string};

/** In-memory wording input only: no employee/person/assignment identifier. */
export function manualSubjectWording(fullName:string):EmployeeDTO {
 return {id:null,person_id:null,fio:fullName,department:null,position:null,org_unit:null,
  rate:null,status:"unknown",date_from:null,date_to:null,has_current_assignment:false,assignments:[]};
}
