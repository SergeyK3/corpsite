"use client";
import * as React from "react";
import {getEmployee,getEmployees} from "@/app/directory/employees/_lib/api.client";
import type {EmployeeDTO} from "@/app/directory/employees/_lib/types";
import {mapEmployeesResponseToSearchOptions} from "./personnelOrderEmployeeSearch";

type State={manualName:string|null;query:string;employee:EmployeeDTO|null;matches:EmployeeDTO[];loading:boolean;searching:boolean;finished:boolean;error:string};
type Action={type:"manual"}|{type:"input";query:string}|{type:"pick";query?:string}|{type:"selected";employee:EmployeeDTO;replaceQuery:boolean}|{type:"searching"}|{type:"matches";matches:EmployeeDTO[]}|{type:"error";error:string};
function reducer(state:State,action:Action):State {
 switch(action.type){
  case "manual":return {...state,manualName:state.query.trim(),employee:null,matches:[],loading:false,searching:false,error:""};
  case "input":return {...state,manualName:null,query:action.query,employee:null,matches:[],loading:false,searching:false,finished:false,error:""};
  case "pick":return {...state,manualName:null,...(action.query===undefined?{}:{query:action.query,employee:null}),loading:true,matches:[],error:""};
  case "selected":return {...state,employee:action.employee,query:action.replaceQuery?action.employee.fio||"":state.query,loading:false,searching:false,matches:[],error:""};
  case "searching":return {...state,searching:true,finished:false,error:""};
  case "matches":return {...state,matches:action.matches,searching:false,finished:true};
  case "error":return {...state,loading:false,searching:false,finished:true,error:action.error};
 }
}

export function usePersonnelOrderEmployeeSearch({enabled,initialEmployeeId,initialQuery="",scopeKey,includeAssignments,onReset,onSelected}: {
 enabled:boolean;initialEmployeeId?:number|null;initialQuery?:string;scopeKey:string;includeAssignments:boolean;
 onReset:()=>void;onSelected:(employee:EmployeeDTO)=>void;
}) {
 const [state,dispatch]=React.useReducer(reducer,{manualName:null,query:initialQuery,employee:null,matches:[],loading:false,searching:false,finished:false,error:""});
 const latest=React.useRef(state);latest.current=state;
 const callbacks=React.useRef({onReset,onSelected});callbacks.current={onReset,onSelected};
 const version=React.useRef(0),touched=React.useRef(false),seeded=React.useRef(false);
 const refreshed=React.useRef("");
 const input=React.useCallback((query:string)=>{
  touched.current=true;++version.current;
  if(latest.current.employee||latest.current.loading||latest.current.manualName)callbacks.current.onReset();
  dispatch({type:"input",query});
 },[]);
 const load=React.useCallback(async(id:string,query?:string)=>{
  const request=++version.current;
  if(query!==undefined && (latest.current.manualName || latest.current.employee && latest.current.employee.id!==id))callbacks.current.onReset();
  dispatch({type:"pick",query});
  try{
   const employee=includeAssignments?await getEmployee(id,true):await getEmployee(id);
   if(request!==version.current)return;
   callbacks.current.onSelected(employee);
   dispatch({type:"selected",employee,replaceQuery:query!==undefined});
  }catch{
   if(request===version.current)dispatch({type:"error",error:"Не удалось загрузить данные сотрудника. Повторите выбор."});
  }
 },[includeAssignments]);
 const select=React.useCallback((employee:EmployeeDTO)=>{touched.current=true;void load(String(employee.id),employee.fio||"");},[load]);
 React.useEffect(()=>{
  if(!enabled||seeded.current||touched.current||!initialEmployeeId)return;
  seeded.current=true;void load(String(initialEmployeeId),initialQuery);
 },[enabled,initialEmployeeId,initialQuery,scopeKey,load]);
 React.useEffect(()=>{
  const employee=state.employee,key=`${employee?.id}:${includeAssignments}`;
  if(!enabled||!includeAssignments||!employee||employee.assignments!==undefined||refreshed.current===key)return;
  refreshed.current=key;void load(String(employee.id));
 },[enabled,includeAssignments,state.employee,load]);
 React.useEffect(()=>{
  if(!enabled||state.employee||state.manualName||state.loading||state.query.trim().length<2)return;
  let cancelled=false;const query=state.query.trim();dispatch({type:"searching"});
  void getEmployees({q:query,status:"active",limit:10,offset:0}).then(result=>{
   if(cancelled)return;
   const ids=new Set<number>();
   const matches=mapEmployeesResponseToSearchOptions(result,{activeOnly:true}).filter(row=>{if(ids.has(row.employee_id))return false;ids.add(row.employee_id);return true;})
    .map(row=>result.items.find(employee=>Number(employee.id)===row.employee_id)!).filter(Boolean);
   dispatch({type:"matches",matches});
  }).catch(()=>{if(!cancelled)dispatch({type:"error",error:"Не удалось выполнить поиск сотрудников. Повторите поиск."});});
  return()=>{cancelled=true;};
 },[enabled,state.query,state.employee,state.manualName,state.loading]);
 React.useEffect(()=>()=>{++version.current;seeded.current=false;refreshed.current="";},[]);
 return {...state,input,select,confirmManual:()=>{++version.current;dispatch({type:"manual"});},clear:()=>input("")};
}
