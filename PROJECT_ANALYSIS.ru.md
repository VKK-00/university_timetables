# PROJECT_ANALYSIS.ru.md

## Цель проекта

`university_timetables` собирает университетские расписания, в первую очередь для КНУ, из разных источников и приводит их к одному формату Excel. Цель не в том, чтобы «скачать всё подряд», а в том, чтобы получить нормализованные книги расписания, где строки разложены по понятным колонкам и сомнительные данные не попадают в финальный экспорт.

## Что проект делает

Проект:

- находит источники расписаний на страницах факультетов, в публичных Google Sheets, на Google Drive, по прямым ссылкам на файлы и в локальных архивах;
- скачивает найденные файлы;
- парсит Excel, HTML и PDF, при необходимости с OCR;
- нормализует строки в поля `week_type`, `day`, `start_time`, `end_time`, `subject`, `teacher`, `lesson_type`, `room`, `groups`, `course`, `notes`;
- прогоняет row-level QA, чтобы не пускать в экспорт мусор, служебный текст и неоднозначные строки;
- экспортирует результат в Excel-книги по шаблону;
- строит post-run отчёты по quality, review backlog и source-level status.

## Структура репозитория

Основные пути:

- [C:/Coding projects/university_timetables/src/timetable_scraper](C:/Coding%20projects/university_timetables/src/timetable_scraper) — основной код пайплайна;
- [C:/Coding projects/university_timetables/src/timetable_scraper/adapters](C:/Coding%20projects/university_timetables/src/timetable_scraper/adapters) — парсеры конкретных форматов: Excel, HTML, PDF;
- [C:/Coding projects/university_timetables/tests](C:/Coding%20projects/university_timetables/tests) — регрессионные и unit-тесты;
- [C:/Coding projects/university_timetables/config](C:/Coding%20projects/university_timetables/config) — конфиги запусков и ручных direct assets;
- [C:/Coding projects/university_timetables/out_knu_web](C:/Coding%20projects/university_timetables/out_knu_web) — артефакты последнего полного KNU web run;
- [C:/Coding projects/university_timetables/README.md](C:/Coding%20projects/university_timetables/README.md) — пользовательская документация;
- [C:/Coding projects/university_timetables/Plan.md](C:/Coding%20projects/university_timetables/Plan.md) — история выполненных milestone-ов.

## Ключевые модули и роли

### Оркестрация

- [C:/Coding projects/university_timetables/src/timetable_scraper/cli.py](C:/Coding%20projects/university_timetables/src/timetable_scraper/cli.py)
  - CLI-входы `doctor`, `inspect-source`, `audit-reference`, `run`, `run-batched`.
- [C:/Coding projects/university_timetables/src/timetable_scraper/pipeline.py](C:/Coding%20projects/university_timetables/src/timetable_scraper/pipeline.py)
  - orchestration полного запуска;
  - segmented `run-batched`, чтобы не упираться в длинный single-pass run.

### Конфиг и модели

- [C:/Coding projects/university_timetables/src/timetable_scraper/config.py](C:/Coding%20projects/university_timetables/src/timetable_scraper/config.py)
  - чтение config YAML;
  - фильтрация источников для smoke/batched run.
- [C:/Coding projects/university_timetables/src/timetable_scraper/models.py](C:/Coding%20projects/university_timetables/src/timetable_scraper/models.py)
  - dataclass-модели `DiscoveredAsset`, `FetchedAsset`, `ParsedDocument`, `NormalizedRow`, `SourceRunSummary`, `PipelineOutput`.

### Discovery / Fetch

- [C:/Coding projects/university_timetables/src/timetable_scraper/discovery.py](C:/Coding%20projects/university_timetables/src/timetable_scraper/discovery.py)
  - поиск assets на web pages, Google Drive, direct file links;
  - учёт `manual_assets.yaml`.
- [C:/Coding projects/university_timetables/src/timetable_scraper/fetch.py](C:/Coding%20projects/university_timetables/src/timetable_scraper/fetch.py)
  - скачивание файлов;
  - HTTP session с retry/backoff;
  - content-type resolution и OneDrive/GDrive особенности.

### Парсинг

- [C:/Coding projects/university_timetables/src/timetable_scraper/adapters/excel.py](C:/Coding%20projects/university_timetables/src/timetable_scraper/adapters/excel.py)
  - разбор `.xlsx/.xls/.csv`;
  - special-case логика для FIT grid sheets;
  - узкая parser-level очистка merged subject-cell в `fit-schedule`: split по date-boundary, перенос inline date-list в `notes`, room tail в `room`, teacher tail в `teacher`;
  - generic grid parsing.
- [C:/Coding projects/university_timetables/src/timetable_scraper/adapters/html.py](C:/Coding%20projects/university_timetables/src/timetable_scraper/adapters/html.py)
  - разбор HTML-таблиц и schedule-like блоков.
- [C:/Coding projects/university_timetables/src/timetable_scraper/adapters/pdf.py](C:/Coding%20projects/university_timetables/src/timetable_scraper/adapters/pdf.py)
  - text extraction из PDF;
  - OCR fallback и PDF-specific cleanup.
- [C:/Coding projects/university_timetables/src/timetable_scraper/ocr.py](C:/Coding%20projects/university_timetables/src/timetable_scraper/ocr.py)
  - обвязка вокруг Tesseract.

### Нормализация и QA

- [C:/Coding projects/university_timetables/src/timetable_scraper/normalize.py](C:/Coding%20projects/university_timetables/src/timetable_scraper/normalize.py)
  - перевод сырых `RawRecord` в `NormalizedRow`;
  - cleanup `subject/teacher/room/groups/notes`;
  - merge metadata-only rows и subject continuation rows;
  - узкий source-specific merge для `sociology-schedule`, когда название предмета разрезано на несколько строк одного слота;
  - разбор `sociology` room payload вида `ауд. проф. ... ауд.312` в `teacher + room`;
  - перенос sociology hour-tail фрагментов вроде `Л-2год./ПР-4год.` из `subject` в `lesson_type/notes`;
  - program label recovery и week inference.
- [C:/Coding projects/university_timetables/src/timetable_scraper/utils.py](C:/Coding%20projects/university_timetables/src/timetable_scraper/utils.py)
  - общие regex/эвристики;
  - детект service text, bad program labels, teacher/room/link text;
  - разбор `week_type`, включая `Верхній`, `Нижній`, `Обидва`, диапазоны недель и типичные опечатки;
  - label normalization и filename sanitizing.
- [C:/Coding projects/university_timetables/src/timetable_scraper/qa.py](C:/Coding%20projects/university_timetables/src/timetable_scraper/qa.py)
  - row-level QA flags;
  - accepted/review partition;
  - safe-drop явного неучебного review-мусора вроде weekday-only строк, `ТИЖНІ САМОСТІЙНОЇ РОБОТИ`, `ПОСВЯТА В ПЕРШОКУРСНИКИ`;
  - tiny workbook demotion;
  - workbook-level QA.

### Экспорт и отчётность

- [C:/Coding projects/university_timetables/src/timetable_scraper/export.py](C:/Coding%20projects/university_timetables/src/timetable_scraper/export.py)
  - запись Excel-книг по шаблону;
  - группировка экспорта по нормализованным `faculty + program`;
  - выбор листа сначала по нормальному `course`, затем по валидному `sheet_name`;
  - `manifest.jsonl`, `review_queue.xlsx`, QA/autofix reports.
- [C:/Coding projects/university_timetables/src/timetable_scraper/reporting.py](C:/Coding%20projects/university_timetables/src/timetable_scraper/reporting.py)
  - `source_summary`, `review_summary`, `run_delta`.
- [C:/Coding projects/university_timetables/src/timetable_scraper/manual_reference.py](C:/Coding%20projects/university_timetables/src/timetable_scraper/manual_reference.py)
  - локальный audit ручного reference ZIP;
  - читает `.xlsx` внутри ZIP и считает словари `title`, `sheet`, `week_type`, `lesson_type`, `groups`, `course`;
  - не пишет output и не превращает ручной ZIP в production input.

## Как система работает end-to-end

Полный поток такой:

1. CLI читает config YAML.
2. `discovery.py` находит assets для каждого source.
3. `fetch.py` скачивает assets с retry и определяет тип.
4. `adapters/*.py` парсят каждый asset в `ParsedDocument`.
5. `normalize.py` превращает сырые записи в `NormalizedRow`.
   Для `week_type` явно распознаются `Верхній`, `Нижній`, `Обидва`, `верхній/нижній`, `Верхній (чисельник)`, `Нижній (знаменник)`, опечатки вроде `Вехній`/`Нижнй`, а диапазоны вида `1-13 верхній` дают `week_type=Верхній` и `notes=Тижні: 1-13`. Чистые номера недель без маркера не угадываются как верхняя/нижняя неделя и остаются `Обидва`.
   Для `lesson_type` используется ручной формат: `лекція`, `практичне заняття`, `семінар`, `лабораторне заняття`, плюс безопасные реальные типы вроде `практика`, `самостійна робота`, `факультатив`. Payload в ячейке типа занятия, например `IoT; лабораторна` или `1 підгрупа; лабораторна`, раскладывается в `lesson_type`, `notes` и `groups`.
   Для `sociology-schedule` тут же выполняется узкое склеивание разрезанных `subject`, если continuation лежит в соседней строке того же слота или через одну строку другой подгруппы. Там же room payload типа `ауд. проф. ... ауд.312` переводится в корректные `teacher + room`, чистые hour-tail строки не остаются в `subject`, а fallback program становится `Соціологія`.
6. `qa.py` делит строки на `accepted` и `review`, а также режет ложные tiny bucket-ы.
7. `export.py` пишет Excel-книги, manifest и review queue.
   Экспорт создаёт одну книгу на нормальный `faculty + program`. Внутри книги листы выбираются по `course` (`1 курс`, `2 курс`, `1 курс магістр`) и только потом по валидному исходному `sheet_name`; технические имена вроде `3 к 1с`, `1к 1с 25-26`, `2с 25-26`, `English 1c`, `Аркуш8`, `uploads`, а также явные ФИО преподавателей/студентов не должны становиться user-facing листами или файлами.
8. `reporting.py` и `qa.py` строят post-run артефакты:
   - `source_summary.json`
   - `review_summary.json`
   - `qa_report.json`
   - `autofix_report.json`
   - `run_delta.json`

## Данные и потоки данных

Основные типы данных:

- исходные web/file assets;
- промежуточные parsed records;
- нормализованные строки `NormalizedRow`;
- финальные Excel-книги и machine-readable отчёты.

Поток данных:

- источник -> discovery -> fetched asset -> parsed document -> normalized rows -> QA split -> export/reporting.

Что важно:

- `review_queue.xlsx` содержит строки, которые не прошли строгую проверку;
- `manifest.jsonl` хранит построчную provenance-информацию и trace autofix/QA;
- `source_summary.json` — главный источник правды по coverage и blocker-статусам.

## Внешние интеграции и зависимости

Внешние зависимости:

- `requests` для HTTP;
- `openpyxl`, `xlrd` для Excel;
- `BeautifulSoup`-стек для HTML;
- `pypdfium2`, `pytesseract`, локальный `tesseract` для PDF/OCR.

Внешние типы источников:

- обычные веб-страницы;
- прямые ссылки на XLSX/PDF;
- Google Sheets / Google Drive;
- OneDrive-подобные публичные file links.

## Конфигурация и runtime assumptions

Ключевые config-поля:

- `template_path`
- `output_dir`
- `cache_dir`
- `confidence_threshold`
- `ocr_enabled`
- `manual_assets_path`
- `sources[]`

Ожидания runtime:

- Tesseract должен быть установлен и доступен в `PATH`;
- для PDF OCR нужны языки `ukr` и `eng`;
- сеть может быть нестабильной, поэтому в `fetch.py` уже есть retry/backoff;
- часть источников КНУ внешне блокируется и это не всегда исправляется кодом.

Секреты:

- проект в обычном режиме не требует секретов;
- `manual_assets.yaml` должен содержать только публичные официальные URL.

## Команды запуска, проверки и отладки

Основные команды:

```powershell
pip install -e .[dev]
python -m timetable_scraper doctor
python -m timetable_scraper inspect-source --config config/knu_web_schedule.yaml
python -m timetable_scraper audit-reference --zip drive-download-20260416T062121Z-3-001.zip
python -m timetable_scraper run --config config/knu_web_schedule.yaml
python -m timetable_scraper run-batched --config config/knu_web_schedule.yaml --batch-size 5
python -m timetable_scraper run-batched --config config/knu_web_smoke.yaml --batch-size 3
python -m ruff check src tests
python -m mypy src
python -m pytest -q
python -m build
```

Отладка backlog:

- смотреть [C:/Coding projects/university_timetables/out_knu_web/review_queue.xlsx](C:/Coding%20projects/university_timetables/out_knu_web/review_queue.xlsx);
- смотреть [C:/Coding projects/university_timetables/out_knu_web/source_summary.json](C:/Coding%20projects/university_timetables/out_knu_web/source_summary.json);
- смотреть [C:/Coding projects/university_timetables/out_knu_web/review_summary.json](C:/Coding%20projects/university_timetables/out_knu_web/review_summary.json);
- смотреть [C:/Coding projects/university_timetables/out_knu_web/qa_report.json](C:/Coding%20projects/university_timetables/out_knu_web/qa_report.json).

## Важные архитектурные решения

1. **Строгий QA важнее роста `accepted`.**
   Если строка сомнительна, она должна идти в `review`, а не в экспорт.

2. **Program/workbook naming фильтруется отдельно.**
   Это нужно, чтобы не получать книги с названиями из meeting-id, room fragments или teacher titles.

3. **Есть отдельный batched run.**
   Полный KNU run слишком тяжёлый для одного длинного прохода, поэтому segmented orchestration — осознанное решение.

4. **Manual asset seeding допустим только для официальных прямых файлов.**
   Это способ обходить страницы, которые блокируют discovery, но не повод подмешивать неофициальные данные.

5. **Source-specific merge разрешён только там, где паттерн подтверждён review-данными.**
   Сейчас это касается `sociology-schedule`: там встречаются разрезанные uppercase-фрагменты одного предмета в рамках одного слота, bilingual continuation и hour-tail хвосты. Аналогичный merge не включён глобально для всех source-ов, чтобы не склеивать разные дисциплины по ошибке.

6. **FIT merged-cell cleanup делается на parser-слое, а не в позднем QA.**
   Для `fit-schedule` точное разделение `subject / teacher / room / notes` лучше делать в [C:/Coding projects/university_timetables/src/timetable_scraper/adapters/excel.py](C:/Coding%20projects/university_timetables/src/timetable_scraper/adapters/excel.py), пока ещё виден исходный merged cell. Поздний QA не должен угадывать потерянный предмет.

7. **Ручной ZIP — reference, а не tracked data.**
   Файл [C:/Coding projects/university_timetables/drive-download-20260416T062121Z-3-001.zip](C:/Coding%20projects/university_timetables/drive-download-20260416T062121Z-3-001.zip) используется только для локального сравнения формата. Он игнорируется правилом `drive-download-*.zip`, не коммитится и не становится production input.

8. **Одна программа — одна книга, курсы — листы.**
   Это ближе к ручному эталону: строка 1 содержит ОП/специальность, строка 2 содержит 12 колонок шаблона, строки 3+ содержат пары, а разные курсы одной программы живут на отдельных листах одной книги.

## Какие варианты рассматривались и почему выбрано текущее решение

- **Полностью ослабить QA**, чтобы увеличить `accepted`.
  Не выбрано, потому что это сразу засоряет финальные `.xlsx`.

- **Жёстко восстанавливать `program` по `course` или `groups`.**
  Не выбрано как дефолт, потому что это легко смешивает разные программы в одну книгу.

- **Один большой full run вместо batch orchestration.**
  Не выбрано, потому что есть реальный риск длинных сетевых таймаутов и нестабильности среды.

- **Чинить всё только regex-ами в одном месте.**
  Не выбрано, потому что часть проблем относится к parser stage, часть к normalization, часть к QA demotion logic.

## Текущие ограничения и риски

- некоторые официальные источники остаются `confirmed-blocker` из-за внешних ограничений сайта;
- часть backlog ещё остаётся в `phys`, `sociology`, `fit` и других источниках;
- tiny workbook-и ещё существуют, хотя большая часть ложных bucket-ов уже вычищена;
- `sociology-schedule` теперь лучше склеивает разрезанные названия предметов, но эта логика специально узкая и не должна автоматически распространяться на все факультеты;
- полный baseline меняется по сети, поэтому результаты надо подтверждать именно свежим `run-batched`.

## Актуальное состояние на 2026-04-16

Последний подтверждённый полный запуск:

- команда: `python -m timetable_scraper run-batched --config config/knu_web_schedule.yaml --batch-size 5`
- результат:
  - `78` exported workbooks
  - `37741` accepted rows
  - `9019` review rows
  - `46667` rows with autofixes
  - `0` workbook QA issues
  - `0` QA failures

Последние важные правки:

- добавлен обязательный файл [C:/Coding projects/university_timetables/PROJECT_ANALYSIS.ru.md](C:/Coding%20projects/university_timetables/PROJECT_ANALYSIS.ru.md);
- в [C:/Coding projects/university_timetables/src/timetable_scraper/utils.py](C:/Coding%20projects/university_timetables/src/timetable_scraper/utils.py) усилен список forbidden/service subject placeholder-ов для `classroom`, `Google Classroom`, `Гугл клас`, `ID: ...`, одиночных bracket-date фрагментов и русских weekday labels;
- в [C:/Coding projects/university_timetables/src/timetable_scraper/normalize.py](C:/Coding%20projects/university_timetables/src/timetable_scraper/normalize.py) такие технические куски больше уходят в `notes`, а не остаются в `subject`; отдельно добавлена безопасная нормализация валидной аббревиатуры `техн.комп.бачення`;
- в [C:/Coding projects/university_timetables/src/timetable_scraper/normalize.py](C:/Coding%20projects/university_timetables/src/timetable_scraper/normalize.py) добавлен узкий merge для разрезанных `subject` в `sociology-schedule`, включая continuation через строку другой подгруппы и поглощение промежуточных дублей одного фрагмента;
- в [C:/Coding projects/university_timetables/src/timetable_scraper/normalize.py](C:/Coding%20projects/university_timetables/src/timetable_scraper/normalize.py) этот `sociology` merge теперь сохраняет уже существующий `lesson_type`, выносит чистые hour-tail строки из `subject` в `lesson_type/notes` и умеет разбирать room payload вида `ауд. проф. ... ауд.312`;
- в [C:/Coding projects/university_timetables/src/timetable_scraper/adapters/excel.py](C:/Coding%20projects/university_timetables/src/timetable_scraper/adapters/excel.py) добавлен ранний safe-split merged FIT subject-cell по date-boundary и inline cleanup для `date-list / room / teacher` хвостов;
- в [C:/Coding projects/university_timetables/src/timetable_scraper/qa.py](C:/Coding%20projects/university_timetables/src/timetable_scraper/qa.py) review-очередь теперь жёстче выкидывает административные и чисто технические строки без реального учебного содержимого;
- в [C:/Coding projects/university_timetables/src/timetable_scraper/qa.py](C:/Coding%20projects/university_timetables/src/timetable_scraper/qa.py) добавлен safe-drop для weekday-only строк, `ТИЖНІ САМОСТІЙНОЇ РОБОТИ` и `ПОСВЯТА В ПЕРШОКУРСНИКИ`;
- в [C:/Coding projects/university_timetables/src/timetable_scraper/utils.py](C:/Coding%20projects/university_timetables/src/timetable_scraper/utils.py) semester/date заголовки вида `1 sem. 2025 2026 28.08.2025` теперь считаются bad `program` label;
- в [C:/Coding projects/university_timetables/src/timetable_scraper/qa.py](C:/Coding%20projects/university_timetables/src/timetable_scraper/qa.py) добавлен safe recovery `program` для `phys-schedule`, но только из простого одиночного `groups` вида `Група 1 Фізика`; агрегаты и скобочные списки сознательно не восстанавливаются автоматически;
- в [C:/Coding projects/university_timetables/src/timetable_scraper/qa.py](C:/Coding%20projects/university_timetables/src/timetable_scraper/qa.py) добавлено safe-исключение для валидных lowercase dotted subject в `fit-schedule` и drop review для pure date-placeholder строк вида `[24.11] .`, `[03.11, 10.11] (Пр)`, `[30.03 ]`, а также для строк, где в `notes` остались только списки дат без учебного содержимого.
- в [C:/Coding projects/university_timetables/src/timetable_scraper/manual_reference.py](C:/Coding%20projects/university_timetables/src/timetable_scraper/manual_reference.py) добавлен локальный audit ручного ZIP [C:/Coding projects/university_timetables/drive-download-20260416T062121Z-3-001.zip](C:/Coding%20projects/university_timetables/drive-download-20260416T062121Z-3-001.zip); ZIP игнорируется через `drive-download-*.zip` и не коммитится;
- в [C:/Coding projects/university_timetables/src/timetable_scraper/utils.py](C:/Coding%20projects/university_timetables/src/timetable_scraper/utils.py) усилен разбор недель: диапазоны с `верхній/нижній` дают соответствующий `week_type`, чистые диапазоны остаются `Обидва`, а raw range переносится в `notes` как `Тижні: ...`;
- в [C:/Coding projects/university_timetables/src/timetable_scraper/normalize.py](C:/Coding%20projects/university_timetables/src/timetable_scraper/normalize.py) `lesson_type` приведён к ручному формату, payload из `lesson_type` раскладывается в `notes/groups`, а `.0` артефакты чистятся в `groups/course`;
- в [C:/Coding projects/university_timetables/src/timetable_scraper/utils.py](C:/Coding%20projects/university_timetables/src/timetable_scraper/utils.py) date-prefixed FIT labels вида `26.01 30.01 ІПЗ, ІПЗм` и `01.09-05.09 АнД, КН, ТШІ` нормализуются до чистого названия программы, но исходная date-prefixed строка всё ещё считается плохим user-facing label;
- в [C:/Coding projects/university_timetables/src/timetable_scraper/export.py](C:/Coding%20projects/university_timetables/src/timetable_scraper/export.py) экспорт теперь предпочитает листы по `course`, умеет безопасно превращать compact source sheet `1к 1с 25-26` в `1 курс` и не использует `groups`/технический `sheet_name` как fallback для workbook filename;
- в [C:/Coding projects/university_timetables/src/timetable_scraper/utils.py](C:/Coding%20projects/university_timetables/src/timetable_scraper/utils.py) явные person-name строки вроде `Архипова Анастасія Олександрівна`, `Андрєєв Назар Едуардович`, `Вірченко В.,В` считаются плохими `program/subject` label, чтобы не создавать книги по ФИО и не принимать списки людей как дисциплины;
- в [C:/Coding projects/university_timetables/src/timetable_scraper/qa.py](C:/Coding%20projects/university_timetables/src/timetable_scraper/qa.py) общий recovery `program` из `groups` отключён; оставлен только узкий phys-specific recovery, а для `sociology-schedule` добавлен fallback `Соціологія`.
- в [C:/Coding projects/university_timetables/src/timetable_scraper/utils.py](C:/Coding%20projects/university_timetables/src/timetable_scraper/utils.py) расширен blacklist bad program labels: `Завантажити`, `Nachytka`, `рік навчання`, `1 2 курс`, `1 2маг`, transliterated law labels, химические group-grid подписи, физические подписи по ФИО и строки с незакрытыми кавычками не создают workbook-и;
- в [C:/Coding projects/university_timetables/src/timetable_scraper/utils.py](C:/Coding%20projects/university_timetables/src/timetable_scraper/utils.py) добавлены нормализации `program`: `Психологія 1 курс "Магістр"` раскладывается в `program=Психологія` и `course=1 курс магістр`; `1-4 курси (Екологія)` даёт `program=Екологія`; biomed-строки очищаются от `ДОСТАВИТИ`, `(укр)`, `ОП`, `ОС Бакалавр/Магістр`;
- в [C:/Coding projects/university_timetables/src/timetable_scraper/normalize.py](C:/Coding%20projects/university_timetables/src/timetable_scraper/normalize.py) добавлен перенос leading time из `subject` в `notes`, например `14:10 Організація...` больше не остаётся названием предмета;
- в [C:/Coding projects/university_timetables/src/timetable_scraper/normalize.py](C:/Coding%20projects/university_timetables/src/timetable_scraper/normalize.py) добавлены строгие source fallback-и `journ-schedule -> Журналістика`, `geology-schedule -> Геологія`, `law-schedule -> Право`, `philosophy-schedule -> Філософія`, а `sociology-schedule -> Соціологія` сохранён как подтверждённый fallback;
- в [C:/Coding projects/university_timetables/src/timetable_scraper/normalize.py](C:/Coding%20projects/university_timetables/src/timetable_scraper/normalize.py) service-subject строки вида `І семестр тижнів: 13` уходят из `accepted`, чтобы служебный календарный текст не становился предметом.

Актуальный полный baseline после `python -m timetable_scraper run-batched --config config/knu_web_schedule.yaml --batch-size 5`:

- exported workbooks: `78`
- accepted rows: `37741`
- review rows: `9019`
- rows with autofixes: `46667`
- QA warnings: `0`
- QA failures: `0`

Оставшиеся основные backlog-и после этого состояния:

- `phys-schedule`: `5027 review`
- `geo-schedule`: `718 review`
- `fit-schedule`: `700 review`
- `biomed-schedule`: `597 review`
- `chem-schedule`: `483 review`
- `econom-schedule`: `388 review`
- `rex-schedule`: `295 review`
- `sociology-schedule`: `285 review`
- `law-schedule`: `206 review`

Оставшиеся `tiny workbook`-и в полном baseline сейчас выглядят как спорные, но не явно ложные. Текущее количество: `4`.

- `Психологія.xlsx`
- `Фізика ядра та елементарних частинок.xlsx`
- `Архівістика та управл. док.xlsx`
- `Фінанси публічного сектору.xlsx`

## Что нужно обновлять в этом файле при изменениях

Если проект меняется, в этом файле нужно отражать:

- новые модули и файлы;
- удалённые или заменённые части пайплайна;
- изменения в data flow;
- новые CLI-команды и процедуры запуска;
- изменения в report-артефактах;
- новые known limitations и blocker-статусы;
- изменения в логике `accepted/review` и workbook QA;
- новые важные source-specific эвристики.
