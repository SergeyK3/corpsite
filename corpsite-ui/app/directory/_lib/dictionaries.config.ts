// FILE: corpsite-ui/app/directory/_lib/dictionaries.config.ts

export type DictionaryColumn = {
  key: string;
  title: string;
  width?: string;
  format?: "boolean";
};

export type DictionaryField = {
  key: string;
  label: string;
  type: "text" | "textarea" | "checkbox";
  required?: boolean;
  placeholder?: string;
};

export type DictionaryConfig = {
  code: string;
  title: string;
  description: string;
  apiBase: string;
  idField: string;
  searchPlaceholder: string;
  columns: DictionaryColumn[];
  formFields: DictionaryField[];
};

export const DICTIONARIES: DictionaryConfig[] = [
  {
    code: "roles",
    title: "Роли",
    description: "Роли пользователей и маршрутизация прав доступа.",
    apiBase: "/directory/roles",
    idField: "role_id",
    searchPlaceholder: "Поиск по коду и названию",
    columns: [
      { key: "role_id", title: "ID", width: "90px" },
      { key: "code", title: "Код роли", width: "180px" },
      { key: "name", title: "Название", width: "320px" },
      { key: "is_active", title: "Активна", width: "110px", format: "boolean" },
    ],
    formFields: [
      { key: "code", label: "Код роли", type: "text", required: true, placeholder: "Например: DIRECTOR" },
      { key: "name", label: "Название", type: "text", required: true, placeholder: "Например: Director" },
      { key: "name_ru", label: "Русское название", type: "text", placeholder: "Например: Директор" },
      { key: "description", label: "Описание", type: "textarea", placeholder: "Краткое описание роли" },
      { key: "is_active", label: "Активна", type: "checkbox" },
    ],
  },
  {
    code: "department-groups",
    title: "Группы отделений",
    description: "Группировка отделений по крупным категориям.",
    apiBase: "/directory/department-groups",
    idField: "group_id",
    searchPlaceholder: "Поиск по коду и наименованию",
    columns: [
      { key: "group_id", title: "ID", width: "90px" },
      { key: "code", title: "Код", width: "150px" },
      { key: "group_name", title: "Наименование", width: "320px" },
      { key: "is_active", title: "Активна", width: "110px", format: "boolean" },
    ],
    formFields: [
      { key: "code", label: "Код", type: "text", placeholder: "Например: CLINICAL" },
      { key: "group_name", label: "Наименование", type: "text", required: true, placeholder: "Например: Клинические" },
      { key: "description", label: "Описание", type: "textarea", placeholder: "Краткое описание группы" },
      { key: "is_active", label: "Активна", type: "checkbox" },
    ],
  },
  {
    code: "org-units",
    title: "Отделения",
    description: "Справочник отделений оргструктуры с возможностью CRUD.",
    apiBase: "/directory/org-units",
    idField: "unit_id",
    searchPlaceholder: "Поиск по коду и названию",
    columns: [
      { key: "unit_id", title: "ID", width: "90px" },
      { key: "code", title: "Код", width: "160px" },
      { key: "name", title: "Название", width: "320px" },
      { key: "parent_unit_id", title: "Родительское отделение", width: "190px" },
      { key: "group_id", title: "Группа", width: "120px" },
      { key: "is_active", title: "Активно", width: "110px", format: "boolean" },
    ],
    formFields: [
      { key: "code", label: "Код", type: "text", required: true, placeholder: "Например: SURG_01" },
      { key: "name", label: "Название", type: "text", required: true, placeholder: "Например: Хирургия 1" },
      { key: "name_ru", label: "Русское название", type: "text", placeholder: "Например: Хирургия 1" },
      { key: "parent_unit_id", label: "Родительское отделение", type: "text", placeholder: "Например: 41" },
      { key: "group_id", label: "Группа отделений", type: "text", placeholder: "Например: 1" },
      { key: "description", label: "Описание", type: "textarea", placeholder: "Краткое описание отделения" },
      { key: "is_active", label: "Активно", type: "checkbox" },
    ],
  },
];

export function getDictionaryConfig(code: string): DictionaryConfig | undefined {
  return DICTIONARIES.find((item) => item.code === code);
}