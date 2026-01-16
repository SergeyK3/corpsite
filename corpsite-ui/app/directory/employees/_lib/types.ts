// corpsite-ui/app/directory/employees/_lib/types.ts

export type Department = {
  id: number;
  name: string;
};

export type Position = {
  id: number;
  name: string;
};

// То, что реально приходит с backend (/directory/employees)
export type EmployeeDTO = {
  id: string;
  full_name: string;
  department: Department;
  position: Position;
  date_from: string | null;
  date_to: string | null;
  employment_rate: number | null;
  is_active: boolean; // важно: именно is_active
};

export type EmployeesResponse = {
  items: EmployeeDTO[];
  total: number;
};

// То, что использует UI внутри таблицы/компонентов (нормализованный формат)
export type Employee = {
  id: string; // таб.№
  fullName: string;
  departmentId: number;
  departmentName: string;
  positionId: number;
  positionName: string;
  rate: number | null;
  dateFrom: string | null;
  dateTo: string | null;
  isActive: boolean;
};

export function mapEmployee(dto: EmployeeDTO): Employee {
  return {
    id: dto.id,
    fullName: dto.full_name,
    departmentId: dto.department.id,
    departmentName: dto.department.name,
    positionId: dto.position.id,
    positionName: dto.position.name,
    rate: dto.employment_rate,
    dateFrom: dto.date_from,
    dateTo: dto.date_to,
    isActive: dto.is_active,
  };
}
