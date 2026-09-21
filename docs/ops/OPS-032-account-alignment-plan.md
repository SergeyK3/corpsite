# OPS-032 — план выравнивания персональных учётных записей

## Статус

Только подготовка. Никакие строки local или production этим планом не меняются.

## Будущие QM-переименования

| Текущий login | Предлагаемый login |
|---|---|
| `qm_head@corp.local` | `masimov.ab` |
| `qm_hosp@corp.local` | `seytkazina.gt` |
| `qm_amb@corp.local` | `akiltaeva.bs` |
| `qm_complaint_reg@corp.local` | `abdina.ak` |
| `qm_complaint_pat@corp.local` | `musabekov.ka` |
| `qm_intern_educat@corp.local` | `saparbaeva.zs` |

Каждая операция должна использовать уже существующий User. Создание дубля вместо
переименования запрещено. Перед commit требуется locked preflight, который
проверяет нормализованную уникальность login и единственность User ↔ Employee.

## Персональные ограничения

- Сапарбаева: только rename подтверждённого User 14 / Employee 9; не менять
  роль, grants, внешние привязки, hash или идентификаторы.
- Нурбеков: Person создаётся только через штатный workflow активной карточки
  Employee (`create_active_employee_person_card_tx`): с одной активной IIN,
  отсутствием Person-кандидатов и immutable governance-журналом. Значение
  `contacts.person_id` не является доказательством.
- Козгамбаева: seed-каталог сопоставляет её должность с
  `DEP_OUTPATIENT_AUDIT`; смена роли выполняется только отдельным явно
  утверждённым действием.
- Тулеутаев: до создания User обязателен read-only анализ всех User роли
  `DIRECTOR`, включая неактивные и несопоставимые по Ф.И.О.
- Оразбеков: Person создаётся тем же governance workflow, после чего в той же
  транзакции разрешено создать единственный User `orazbekov.bs` с `DEP_MED`.
- Курманов: исключён из плана — не создавать, не переименовывать и не
  восстанавливать.

## Исполнение после отдельного утверждения

`scripts/align_employee_accounts.py` по умолчанию выполняет только dry-run.
Запись доступна лишь через `--execute`; все governance Person-create / link /
rename / role-change / User-create проходят одной транзакцией, с audit и
security-audit. Скрипт не изменяет
`password_hash`, существующие `employee_id`, grants или Google/Telegram-привязки
при rename, link и role-change.

Перед любым запуском OPS-032 необходимо применить основную миграцию
`adm001canonicalroles`: она добавляет отсутствующие канонические роли
`DIRECTOR`, `DEP_MED`, `DEP_OUTPATIENT_AUDIT` и `DEP_STRATEGY` без grants.
Для `DEP_ADMIN` допустимы неизменяемые существующие имена «Заместитель директора
по административным вопросам» и legacy «Зам по адм вопросам»; при отсутствии
роль создаётся с полным именем.
Если миграция не применена либо каталог роли расходится с каноническим именем,
account alignment не запускается.

## Будущая единая команда dry-run

Команда ниже подготовлена, но не запускалась. Перед её применением назначенный
HR governance-оператор подставляет свой существующий User ID в `ACTOR_USER_ID`.
UUID фиксируют идемпотентность двух governance-операций и не содержат кадровых
или секретных данных.

Для production запрещено использовать менее строгий `--rename-login`: все шесть QM-операций ниже
передают одновременно ожидаемые User ID, Employee ID, текущий login и новый login через
`--checked-rename`. Несовпадение любого из этих четырёх значений завершает полный пакет до первой записи.
Смена роли Козгамбаевой использует столь же строгий `--checked-change-role`: до записи проверяются
User ID, Employee ID, текущий login, текущая роль и существование целевой роли.

```bash
ACTOR_USER_ID='<HR_GOVERNANCE_USER_ID>'
./.venv/bin/python scripts/align_employee_accounts.py --dry-run --actor-user-id "$ACTOR_USER_ID" \
  --create-person 44:7cc1bb12-3463-4fca-9e15-2a3b81e0a044 \
  --checked-rename 17:44:dep_admin@corp.local:nurbekov.bb \
  --create-person 440:7cc1bb12-3463-4fca-9e15-2a3b81e0a440 \
  --create 440:orazbekov.bs:DEP_MED \
  --create 403:tuleutaev.me:DIRECTOR \
  --checked-change-role 20:45:kozgambaeva.lt:DEP_ADMIN:DEP_OUTPATIENT_AUDIT \
  --checked-rename 2:1:qm_head@corp.local:masimov.ab \
  --checked-rename 3:2:qm_hosp@corp.local:seytkazina.gt \
  --checked-rename 4:3:qm_amb@corp.local:akiltaeva.bs \
  --checked-rename 5:4:qm_complaint_reg@corp.local:abdina.ak \
  --checked-rename 6:5:qm_complaint_pat@corp.local:musabekov.ka \
  --checked-rename 14:9:qm_intern_educat@corp.local:saparbaeva.zs
```

При переходе к apply команда должна быть заново подтверждена после успешного
dry-run и запущена с `--execute`; пароль для двух новых User вводится один раз
через `getpass`, не передаётся в аргументах и не выводится.
