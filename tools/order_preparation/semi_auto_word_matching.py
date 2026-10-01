"""Offline, explainable journal-row to Word-block candidate research tool."""
from __future__ import annotations
import argparse, hashlib, re
from pathlib import Path
from docx import Document
from openpyxl import Workbook
from prepare_personnel_orders import action_type, clean, extract_requisites, safe_cell

START=re.compile(r"(?im)^\s*(?:\u041f\u0420\u0418\u041a\u0410\u0417|\u0411\u04b0\u0419\u0420\u042b\u049a)\b")
NAME=re.compile(r"\b[\u0400-\u04ff][\u0400-\u04ff-]+\s+[\u0400-\u04ff][\u0400-\u04ff-]+(?:\s+[\u0400-\u04ff][\u0400-\u04ff-]+)?\b")
DATE=re.compile(r"\b\d{1,2}[.]\d{1,2}[.]\d{4}\b")
def digest(v): return hashlib.sha256(v.encode('utf-8')).hexdigest()
def norm(v): return re.sub(r"[^\w\u0400-\u04ff]+", "", clean(v).casefold().replace("ё","е"))
def phrases(t): return [x for x in re.findall(r"[\u0400-\u04ff]{5,}",t.casefold()) if x not in {'приказ','туралы'}]
def blockify(path):
 d=Document(path); p=[x.text for x in d.paragraphs if x.text.strip()]
 for table in d.tables: p += [c.text for r in table.rows for c in r.cells if c.text.strip()]
 starts=[i for i,x in enumerate(p) if START.search(x)] or [0]
 starts.append(len(p)); out=[]
 for n,(a,b) in enumerate(zip(starts,starts[1:]),1):
  text='\n'.join(p[a:b]); raw,no,rd,date,_,_=extract_requisites(text); names='; '.join(NAME.findall(text)[:8]); out.append((n,text,raw,no,rd,date,action_type(text),names))
 return len(p),len(d.tables),out
def match(row,b):
 rid,no,date,theme,fio,expected=row; text,bno,bdate,act,bfio=b[5],b[8],b[10],b[11],b[12]
 flags=[]; contra=[]
 if no: flags.append(('number',norm(no)==norm(bno),no,bno))
 if date: flags.append(('date',date==bdate,date,bdate))
 if fio: flags.append(('fio',norm(fio) in norm(bfio) or norm(bfio) in norm(fio),fio,bfio))
 terms=[x for x in phrases(theme) if len(x)>4]; topic=sum(x in norm(text) for x in terms)>0 if terms else False
 if theme: flags.append(('theme',topic,theme,'text'))
 yes=[x[0] for x in flags if x[1]]; nof=[x[0] for x in flags if not x[1] and x[2] and x[3]]
 if any(x[0]=='number' and x[1] for x in flags) and any(x[0]=='date' and x[1] for x in flags): status='EXACT_REQUISITES_MATCH'
 elif len(yes)>=2 and not any(x in nof for x in ('number','date')): status='STRONG_CONTENT_CANDIDATE'
 elif nof: status='CONFLICT'
 else: status='NO_CANDIDATE'
 return status,yes,nof,'; '.join(f'{k}: {a} ↔ {c}' for k,ok,a,c in flags)
def main():
 ap=argparse.ArgumentParser();ap.add_argument('word_root',type=Path);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
 files=sorted(a.word_root.rglob('*.docx')); catalog=[]
 for f in files:
  paras,tables,blocks=blockify(f); rel=f.relative_to(a.word_root).as_posix(); fh=hashlib.sha256(f.read_bytes()).hexdigest()
  for n,text,raw,no,rd,date,act,names in blocks: catalog.append((rel,n,fh,paras,tables,text,clean(text).casefold(),raw,no,rd,date,act,names,digest(text),digest(clean(text).casefold())))
 # Manual values only; ? means deliberately unknown, not guessed from Word.
 # A question mark/unreadable phrase is deliberately stored as absent evidence.
 inputs=[('R1L','', '2026-08-17','','', ''),('R2L','','2026-08-17','','',''),('R3L','','2026-08-17','','',''),('R1R','','2026-08-17','','',''),('R2R','','2026-08-17','','','')]
 candidates=[]
 for row in inputs:
  scored=[]
  for b in catalog:
   status,yes,conf,why=match(row,b); priority=({'EXACT_REQUISITES_MATCH':3,'STRONG_CONTENT_CANDIDATE':2,'CONFLICT':1,'NO_CANDIDATE':0}[status],len(yes)); scored.append((priority,status,yes,conf,why,b))
  scored.sort(reverse=True,key=lambda x:x[0]); top=[x for x in scored if x[1] in {'EXACT_REQUISITES_MATCH','STRONG_CONTENT_CANDIDATE'}][:5]
  if not top:
   candidates.append([row[0],0,'','', 'NO_CANDIDATE','','','No reliable manual requisites/content overlap; operator input is required.','','','',''])
  if len(top)>1 and top[0][0]==top[1][0]: top=[(x[0],'MULTIPLE_CANDIDATES',x[2],x[3],x[4],x[5]) for x in top]
  for rank,x in enumerate(top,1): b=x[5]; candidates.append([row[0],rank,b[0],b[1],x[1],','.join(x[2]),','.join(x[3]),x[4],b[8],b[10],b[11],b[12]])
 wb=Workbook(); wb.remove(wb.active)
 tabs={'JournalInput':(['row_id','manual_number','manual_date','manual_theme','manual_fio','expected_word_block'],inputs),'WordCatalog':(['path','block','file_sha256','paragraphs','tables','raw_text','normalized_text','number_raw','number','date_raw','date','action','fio','raw_sha256','normalized_sha256'],catalog),'Candidates':(['row_id','rank','word_path','word_block','status','matches','contradictions','explanation','word_number','word_date','action','word_fio'],candidates),'Alternatives':(['row_id','rank','word_path','word_block','status','matches','contradictions','explanation','word_number','word_date','action','word_fio'],candidates),'ManualDecision':(['row_id','selected_word_path','selected_block','decision','comment'],[[r[0],'','','',''] for r in inputs])}
 for name,(head,rows) in tabs.items():
  ws=wb.create_sheet(name);ws.append(head);[ws.append([safe_cell(v) for v in r]) for r in rows]
 ws=wb.create_sheet('Metrics');ws.append(['metric','value']); ws.append(['word_files',len(files)]);ws.append(['word_blocks',len(catalog)]);ws.append(['journal_rows',len(inputs)]);ws.append(['candidates',len(candidates)])
 ws=wb.create_sheet('Metadata');ws.append(['key','value']);ws.append(['schema','JOURNAL_WORD_MATCH_RESEARCH_V1']);ws.append(['confirmation','only explicit ManualDecision may confirm'])
 a.output.parent.mkdir(parents=True,exist_ok=True);wb.save(a.output)
if __name__=='__main__':main()
