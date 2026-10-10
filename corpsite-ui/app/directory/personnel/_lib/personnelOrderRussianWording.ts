/**
 * Approved Russian forms used inside automatically generated order points.
 * These are deliberately separate from catalogue display names: a display name
 * such as "Приемное" needs its full personnel wording in a sentence.
 */
const RUSSIAN_ORDER_UNIT_FORMS: Record<string, string> = {
  "приемное": "приемное отделение",
};

function usable(value: string | null | undefined): value is string {
  const text = String(value || "").trim();
  return Boolean(text && text !== "—");
}

function lower(value: string): string {
  return value.trim().toLocaleLowerCase("ru-RU");
}

/**
 * Renders the Russian "position (unit)" construction. Unknown units are not
 * declined or invented; their normalized catalogue value remains visible for
 * later dictionary review.
 */
export function russianOrderAssignment(position: string | null | undefined, unit: string | null | undefined): string {
  const positionText = usable(position) ? lower(position) : "—";
  if (!usable(unit)) return positionText;
  const normalizedUnit = lower(unit);
  const orderUnit = RUSSIAN_ORDER_UNIT_FORMS[normalizedUnit] || normalizedUnit;
  return `${positionText} (${orderUnit})`;
}

/** Source FIO must remain untouched. Do not apply the new grammar to an unresolved person. */
export function russianEmployeeForOrder(name: string): string | null {
  return usable(name) ? name : null;
}

export const RUSSIAN_ORDER_UNIT_TEXT_DICTIONARY = RUSSIAN_ORDER_UNIT_FORMS;

function text(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

/** The existing document_forms_ru contract wins over any calculated suggestion. */
export function savedRussianEmployeeNameForm(employee: unknown, form: "dative" | "genitive"): string {
  if (!employee || typeof employee !== "object") return "";
  const row = employee as Record<string, unknown>;
  const key = `employee_full_name_${form}_ru`;
  const forms = row.document_forms_ru;
  const name = row.name;
  return text(forms && typeof forms === "object" ? (forms as Record<string, unknown>)[key] : null)
    || text(row[key])
    || text(name && typeof name === "object" ? (name as Record<string, unknown>)[`full_name_${form}_ru`] : null);
}

/** Dative calculated from source nominative parts, never from an already saved case. */
export function russianEmployeeDativeForOrder(employee: unknown): string {
  const saved=savedRussianEmployeeNameForm(employee,"dative");if(saved)return saved;
  if(!employee || typeof employee!=="object")return "";
  const row=employee as Record<string,unknown>;const fallback=text(row.fio??row.full_name).split(/\s+/);
  const [last,first,middle]=text(row.last_name)&&text(row.first_name)?[text(row.last_name),text(row.first_name),text(row.middle_name)]:fallback;
  if(![last,first,middle].every(p=>p&&/^[А-ЯЁа-яё]{2,}$/u.test(p)))return "";
  const female=/(овна|евна|ична)$/iu.test(middle),male=/ич$/iu.test(middle);if(!female&&!male)return "";
  const consonant=/[бвгджзклмнпрстфхцчшщ]$/iu;
  let family=last;
  if(female&&/(ова|ева|ина|ына|ая)$/iu.test(last))family=last.replace(/(а|ая)$/iu,"ой");
  else if(female&&/яя$/iu.test(last))family=last.slice(0,-2)+"ей";
  else if(male&&/(ский|цкий|ый|ой)$/iu.test(last))family=last.slice(0,-2)+"ому";
  else if(male&&consonant.test(last)&&!/(их|ых)$/iu.test(last))family=last+"у";
  else if(male&&/[йь]$/iu.test(last))family=last.slice(0,-1)+"ю";
  else if(/[ая]$/iu.test(last)&&!female)return "";
  const irregular:Record<string,string>={Павел:"Павлу",Лев:"Льву",Пётр:"Петру",Петр:"Петру",Любовь:"Любови"};
  let given=irregular[first]||"";
  if(!given){if(/ия$/iu.test(first))given=first.slice(0,-1)+"и";else if(/[ая]$/iu.test(first))given=first.slice(0,-1)+"е";else if(female&&/ь$/iu.test(first))given=first.slice(0,-1)+"и";else if(male&&/[йь]$/iu.test(first))given=first.slice(0,-1)+"ю";else if(male&&consonant.test(first))given=first+"у";else given=first;}
  return [family,given,female?middle.slice(0,-1)+"е":middle+"у"].join(" ");
}

/** Reference heads and preceding adjectives only; dependent phrases stay in their source case. */
export function russianReferenceCase(source: unknown, form:"genitive"|"dative"):string {
  const raw=text(source);if(!raw)return "";
  const value=RUSSIAN_ORDER_UNIT_FORMS[lower(raw)]||lower(raw);
  const heads:Record<string,[string,string]>={врач:["врача","врачу"],терапевт:["терапевта","терапевту"],хирург:["хирурга","хирургу"],специалист:["специалиста","специалисту"],директор:["директора","директору"],заведующий:["заведующего","заведующему"],начальник:["начальника","начальнику"],бухгалтер:["бухгалтера","бухгалтеру"],сестра:["сестры","сестре"],медсестра:["медсестры","медсестре"],санитарка:["санитарки","санитарке"],санитар:["санитара","санитару"],отделение:["отделения","отделению"],отдел:["отдела","отделу"],служба:["службы","службе"],центр:["центра","центру"],больница:["больницы","больнице"],кабинет:["кабинета","кабинету"],лаборатория:["лаборатории","лаборатории"]};
  Object.assign(heads,{
    менеджер:['менеджера','менеджеру'],
    заведующая:['заведующей','заведующей'],прачечная:['прачечной','прачечной'],
    акушер:['акушера','акушеру'],акушерка:['акушерки','акушерке'],фельдшер:['фельдшера','фельдшеру'],лаборант:['лаборанта','лаборанту'],
    фармацевт:['фармацевта','фармацевту'],провизор:['провизора','провизору'],психолог:['психолога','психологу'],регистратор:['регистратора','регистратору'],
    инженер:['инженера','инженеру'],техник:['техника','технику'],экономист:['экономиста','экономисту'],юрист:['юриста','юристу'],
    методист:['методиста','методисту'],инструктор:['инструктора','инструктору'],оператор:['оператора','оператору'],водитель:['водителя','водителю'],
    машинист:['машиниста','машинисту'],
    повар:['повара','повару'],уборщик:['уборщика','уборщику'],уборщица:['уборщицы','уборщице'],хозяйка:['хозяйки','хозяйке'],
  });
  const words=value.split(/\s+/);let found=false;
  const result=words.map(word=>{
    if(found)return word;
    const compound=word.split('-');if(compound.every(p=>heads[p])){found=true;return compound.map(p=>heads[p][form==='genitive'?0:1]).join('-');}
    if(/ая$/u.test(word))return word.slice(0,-2)+"ой";
    if(/яя$/u.test(word))return word.slice(0,-2)+"ей";
    if(/(ый|ой|ое)$/u.test(word))return word.slice(0,-2)+(form==='genitive'?"ого":"ому");
    if(/(ий|ее)$/u.test(word))return word.slice(0,-2)+(form==='genitive'?"его":"ему");
    if(/ия$/u.test(word)){found=true;return word.slice(0,-1)+'и';}
    if(/(ение|ание)$/u.test(word)){found=true;return word.slice(0,-1)+(form==='genitive'?'я':'ю');}
    if(/ство$/u.test(word)){found=true;return word.slice(0,-1)+(form==='genitive'?'а':'у');}
    return word;
  });
  return found?result.join(' '):"";
}

/**
 * A conservative RU genitive suggestion, not a confirmed reference form.
 * Use structured names or the existing employee FIO order (surname/name/patronymic).
 * Unresolved gender, initials and ambiguous surname patterns require manual input.
 * Never change employee/reference data or derive this case from the RU dative.
 */
export function russianEmployeeGenitiveForOrder(employee: unknown): string {
  const saved = savedRussianEmployeeNameForm(employee, "genitive");
  if (saved) return saved;
  if (!employee || typeof employee !== "object") return "";
  const row = employee as Record<string, unknown>;
  const fallback = text(row.fio ?? row.full_name).split(/\s+/);
  const structured = Boolean(text(row.last_name) && text(row.first_name));
  if (!structured && fallback.length !== 3) return "";
  const [last, first, middle] = structured
    ? [text(row.last_name), text(row.first_name), text(row.middle_name)] : fallback;
  if (![last, first, middle].every(part => /^[А-ЯЁа-яё]{2,}$/u.test(part))) return "";
  const female = /(?:овна|евна|ична)$/iu.test(middle);
  const male = /ич$/iu.test(middle);
  if (!female && !male) return "";
  const consonant = /[бвгджзклмнпрстфхцчшщ]$/iu;
  const aGenitive = (part: string) => part.slice(0, -1) + (/[гкхжчшщ]а$/iu.test(part) ? "и" : "ы");
  let family = "";
  if (female && /(?:ова|ева|ина|ына)$/iu.test(last)) family = last.slice(0, -1) + "ой";
  else if (female && /ая$/iu.test(last)) family = last.slice(0, -2) + "ой";
  else if (female && /яя$/iu.test(last)) family = last.slice(0, -2) + "ей";
  else if (male && /(?:ский|цкий|ый|ой)$/iu.test(last)) family = last.slice(0, -2) + "ого";
  else if (/[оеёиуыю]$/iu.test(last) || /(?:их|ых)$/iu.test(last)) family = last;
  else if (female && /[бвгджзклмнпрстфхцчшщйь]$/iu.test(last)) family = last;
  else if (male && consonant.test(last)) family = last + "а";
  else if (male && /[йь]$/iu.test(last)) family = last.slice(0, -1) + "я";
  if (!family) return "";
  // Common irregular first names cannot be handled by a final-letter rule.
  const irregular: Record<string, string> = { "Павел": "Павла", "Лев": "Льва", "Пётр": "Петра", "Петр": "Петра", "Любовь": "Любови" };
  let given = irregular[first] || "";
  if (!given && /а$/iu.test(first)) given = aGenitive(first);
  else if (!given && /я$/iu.test(first)) given = first.slice(0, -1) + "и";
  else if (!given && female && /[бвгджзклмнпрстфхцчшщйь]$/iu.test(first)) given = first;
  else if (!given && male && /[йь]$/iu.test(first)) given = first.slice(0, -1) + "я";
  else if (!given && male && consonant.test(first)) given = first + "а";
  else if (!given && /[оеёиуыю]$/iu.test(first)) given = first;
  if (!given) return "";
  return [family, given, female ? aGenitive(middle) : middle + "а"].join(" ");
}
