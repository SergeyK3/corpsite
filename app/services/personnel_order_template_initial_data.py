from __future__ import annotations

from typing import Final
from app.services.personnel_order_childcare_contract import TEXTS as CHILDCARE_TEXTS

InitialTexts = dict[str, str]
INITIAL_TEXTS_BY_TYPE: Final[dict[str, InitialTexts]] = {'HIRE': {'title_ru': 'О приёме на работу',
          'title_kk': 'Жұмысқа қабылдау туралы',
          'preamble_ru': 'В соответствии с Трудовым кодексом Республики Казахстан',
          'preamble_kk': 'Қазақстан Республикасының Еңбек кодексіне сәйкес',
          'body_template_ru': 'Принять на работу {{employee.full_name}} в подразделение «{{org_unit.title_ru}}» на '
                              'должность «{{position.title_ru}}» со ставкой {{rate}} с {{effective_date}}.',
          'body_template_kk': '{{employee.full_name}} «{{org_unit.title_kk}}» бөлімшесіне «{{position.title_kk}}» '
                              'лауазымына {{rate}} мөлшерлемесінде {{effective_date}} бастап жұмысқа қабылдансын.',
          'basis_template_ru': 'Основание: {{basis}}.',
          'basis_template_kk': 'Негіз: {{basis}}.'},
 'TRANSFER': {'title_ru': 'О переводе',
              'title_kk': 'Ауыстыру туралы',
              'preamble_ru': 'В соответствии с Трудовым кодексом Республики Казахстан',
              'preamble_kk': 'Қазақстан Республикасының Еңбек кодексіне сәйкес',
              'body_template_ru': 'Перевести {{employee.full_name}} в подразделение «{{org_unit.title_ru}}» на '
                                  'должность «{{position.title_ru}}» со ставкой {{rate}} с {{effective_date}}.',
              'body_template_kk': '{{employee.full_name}} «{{org_unit.title_kk}}» бөлімшесіне «{{position.title_kk}}» '
                                  'лауазымына {{rate}} мөлшерлемесінде {{effective_date}} бастап ауыстырылсын.',
              'basis_template_ru': 'Основание: {{basis}}.',
              'basis_template_kk': 'Негіз: {{basis}}.'},
 'TERMINATION': {'title_ru': 'Об увольнении',
                 'title_kk': 'Жұмыстан босату туралы',
                 'preamble_ru': 'В соответствии с Трудовым кодексом Республики Казахстан',
                 'preamble_kk': 'Қазақстан Республикасының Еңбек кодексіне сәйкес',
                 'body_template_ru': 'Уволить {{employee.full_name}}, {{position.title_ru}} подразделения '
                                     '«{{org_unit.title_ru}}», {{effective_date}}. Причина увольнения: '
                                     '{{termination.reason}}.\n'
                                     '\n'
                                     'Бухгалтерии произвести расчёт за {{termination.unused_leave_days}} календарных '
                                     'дней неиспользованного трудового отпуска.',
                 'body_template_kk': '{{org_unit.title_kk}} бөлімшесінің {{position.title_kk}} қызметкері '
                                     '{{employee.full_name}} еңбек шарты {{effective_date}} бастап '
                                     'бұзылсын.\n'
                                     '\n'
                                     'Бухгалтерлік есеп бөлімі пайдаланылмаған еңбек демалысының '
                                     '{{termination.unused_leave_days}} күнтізбелік күніне есеп айырысу жүргізсін.',
                 'basis_template_ru': 'Основание: {{basis}}.',
                 'basis_template_kk': 'Негіз: {{basis}}.'},
 'CONCURRENT_DUTY_START': {'title_ru': 'Об установлении совмещения',
                           'title_kk': 'Қоса атқаруды белгілеу туралы',
                           'preamble_ru': 'В соответствии с Трудовым кодексом Республики Казахстан',
                           'preamble_kk': 'Қазақстан Республикасының Еңбек кодексіне сәйкес',
                           'body_template_ru': 'Установить {{employee.full_name}} совмещение в размере '
                                               '{{concurrent.rate}} ставки с {{effective_date}}. Итоговая ставка: '
                                               '{{total.rate}}.',
                           'body_template_kk': '{{employee.full_name}} үшін қоса атқару {{concurrent.rate}} '
                                               'мөлшерлемесінде {{effective_date}} бастап белгіленсін. Жалпы '
                                               'мөлшерлеме: {{total.rate}}.',
                           'basis_template_ru': 'Основание: {{basis}}.',
                           'basis_template_kk': 'Негіз: {{basis}}.'},
 'CONCURRENT_DUTY_END': {'title_ru': 'О прекращении совмещения',
                         'title_kk': 'Қоса атқаруды тоқтату туралы',
                         'preamble_ru': 'В соответствии с Трудовым кодексом Республики Казахстан',
                         'preamble_kk': 'Қазақстан Республикасының Еңбек кодексіне сәйкес',
                         'body_template_ru': 'Прекратить совмещение для {{employee.full_name}} с {{effective_date}}. '
                                             'Остающаяся ставка: {{remaining.rate}}.',
                         'body_template_kk': '{{employee.full_name}} үшін қоса атқару {{effective_date}} бастап '
                                             'тоқтатылсын. Қалған мөлшерлеме: {{remaining.rate}}.',
                         'basis_template_ru': 'Основание: {{basis}}.',
                         'basis_template_kk': 'Негіз: {{basis}}.'},
 'LEAVE.ANNUAL.GRANT': {'title_ru': 'О предоставлении ежегодного оплачиваемого трудового отпуска',
                        'title_kk': 'Жыл сайынғы ақылы еңбек демалысын беру туралы',
                        'preamble_ru': 'В соответствии с Трудовым кодексом Республики Казахстан',
                        'preamble_kk': 'Қазақстан Республикасының Еңбек кодексіне сәйкес',
                        'body_template_ru': 'Предоставить {{employee.full_name}}, {{position.title_ru}} подразделения '
                                            '«{{org_unit.title_ru}}», ежегодный оплачиваемый отпуск с '
                                            '{{leave.start_ru}} по {{leave.end_ru}} продолжительностью {{leave.days}} '
                                            'календарных дней.',
                        'body_template_kk': '{{employee.full_name}}, «{{org_unit.title_kk}}» бөлімшесінің '
                                            '«{{position.title_kk}}» қызметкеріне {{leave.start_kk}} мен '
                                            '{{leave.end_kk}} аралығында {{leave.days}} күнтізбелік күнге жыл сайынғы '
                                            'ақылы еңбек демалысы берілсін.',
                        'basis_template_ru': 'Основание: {{basis}}.',
                        'basis_template_kk': 'Негіз: {{basis}}.'},
 'LEAVE.UNPAID.GRANT': {'title_ru': 'О предоставлении отпуска без сохранения заработной платы',
                        'title_kk': 'Жалақы сақталмайтын демалыс беру туралы',
                        'preamble_ru': 'В соответствии с Трудовым кодексом Республики Казахстан',
                        'preamble_kk': 'Қазақстан Республикасының Еңбек кодексіне сәйкес',
                        'body_template_ru': 'Предоставить работнику {{employee.full_name_dative_ru}}, '
                                            '{{position.document_nominative_ru}} подразделения '
                                            '«{{org_unit.title_ru}}», отпуск без сохранения заработной платы '
                                            '{{leave.period_clause_ru}} продолжительностью {{leave.days}} календарных дней.',
                        'body_template_kk': '{{org_unit.document_genitive_kk}} {{position.document_possessive_kk}} '
                                            '{{employee.full_name_dative_kk}} {{leave.period_clause_kk}} '
                                            'еңбекақысы сақталмайтын демалыс берілсін.',
                        'basis_template_ru': 'Основание: Личное '
                                             'заявление{{basis.application_date_ru}}{{basis.application_number_suffix}}.',
                        'basis_template_kk': 'Негіз: {{employee.full_name_genitive_kk}} жеке өтініші.'},
 'LEAVE.CHILDCARE.GRANT': dict(CHILDCARE_TEXTS),
 'SUPPLEMENTARY_PAY': {'title_ru': 'О дополнительной оплате',
                       'title_kk': 'Қосымша ақы туралы',
                       'preamble_ru': 'Условия дополнительной оплаты уточняются после сверки с DOCX.',
                       'preamble_kk': 'Қосымша ақының шарттары DOCX-пен салыстырылғаннан кейін нақтыланады.',
                       'body_template_ru': 'Дополнительная оплата для {{employee.full_name}}: размер, период, '
                                           'основание и условия требуют сверки с DOCX.',
                       'body_template_kk': '{{employee.full_name}} үшін қосымша ақы: мөлшері, кезеңі, негізі және '
                                           'шарттары DOCX-пен салыстыруды талап етеді.',
                       'basis_template_ru': 'Основание: {{basis}}.',
                       'basis_template_kk': 'Негіз: {{basis}}.'},
 'RETURN_FROM_CHILDCARE_LEAVE': {'title_ru': 'О выходе на работу из отпуска по уходу за ребёнком',
                                 'title_kk': 'Бала күтіміне байланысты демалыстан жұмысқа шығу туралы',
                                 'preamble_ru': 'В соответствии с Трудовым кодексом Республики Казахстан',
                                 'preamble_kk': 'Қазақстан Республикасының Еңбек кодексіне сәйкес',
                                 'body_template_ru': '{{employee.full_name}}, {{position.title_ru}} подразделения '
                                                     '«{{org_unit.title_ru}}», приступить к работе с '
                                                     '{{effective_date}} с оплатой {{rate}} ставки.',
                                 'body_template_kk': '{{employee.full_name}}, «{{org_unit.title_kk}}» бөлімшесінің '
                                                     '{{position.title_kk}} қызметкері, {{effective_date}} бастап '
                                                     '{{rate}} ставкамен жұмысқа шықсын.',
                                 'basis_template_ru': 'Основание: {{basis}}.',
                                 'basis_template_kk': 'Негіз: {{basis}}.'}}
