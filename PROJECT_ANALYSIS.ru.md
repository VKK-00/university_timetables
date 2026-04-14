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
  - CLI-входы `doctor`, `inspect-source`, `run`, `run-batched`.
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
  - program label recovery и week inference.
- [C:/Coding projects/university_timetables/src/timetable_scraper/utils.py](C:/Coding%20projects/university_timetables/src/timetable_scraper/utils.py)
  - общие regex/эвристики;
  - детект service text, bad program labels, teacher/room/link text;
  - label normalization и filename sanitizing.
- [C:/Coding projects/university_timetables/src/timetable_scraper/qa.py](C:/Coding%20projects/university_timetables/src/timetable_scraper/qa.py)
  - row-level QA flags;
  - accepted/review partition;
  - tiny workbook demotion;
  - workbook-level QA.

### Экспорт и отчётность

- [C:/Coding projects/university_timetables/src/timetable_scraper/export.py](C:/Coding%20projects/university_timetables/src/timetable_scraper/export.py)
  - запись Excel-книг по шаблону;
  - `manifest.jsonl`, `review_queue.xlsx`, QA/autofix reports.
- [C:/Coding projects/university_timetables/src/timetable_scraper/reporting.py](C:/Coding%20projects/university_timetables/src/timetable_scraper/reporting.py)
  - `source_summary`, `review_summary`, `run_delta`.

## Как система работает end-to-end

Полный поток такой:

1. CLI читает config YAML.
2. `discovery.py` находит assets для каждого source.
3. `fetch.py` скачивает assets с retry и определяет тип.
4. `adapters/*.py` парсят каждый asset в `ParsedDocument`.
5. `normalize.py` превращает сырые записи в `NormalizedRow`.
   Для `sociology-schedule` тут же выполняется узкое склеивание разрезанных `subject`, если continuation лежит в соседней строке того же слота или через одну строку другой подгруппы.
6. `qa.py` делит строки на `accepted` и `review`, а также режет ложные tiny bucket-ы.
7. `export.py` пишет Excel-книги, manifest и review queue.
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
   Сейчас это касается `sociology-schedule`: там встречаются разрезанные uppercase-фрагменты одного предмета в рамках одного слота. Аналогичный merge не включён глобально для всех source-ов, чтобы не склеивать разные дисциплины по ошибке.

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

## Актуальное состояние на 2026-04-14

Последний подтверждённый полный запуск:

- команда: `python -m timetable_scraper run-batched --config config/knu_web_schedule.yaml --batch-size 5`
- результат:
  - `173` exported workbooks
  - `42651` accepted rows
  - `3993` review rows
  - `46554` rows with autofixes
  - `0` QA warnings
  - `0` QA failures

Последние важные правки:

- добавлен обязательный файл [C:/Coding projects/university_timetables/PROJECT_ANALYSIS.ru.md](C:/Coding%20projects/university_timetables/PROJECT_ANALYSIS.ru.md);
- в [C:/Coding projects/university_timetables/src/timetable_scraper/utils.py](C:/Coding%20projects/university_timetables/src/timetable_scraper/utils.py) усилен список forbidden/service subject placeholder-ов для `classroom`, `Google Classroom`, `Гугл клас`, `ID: ...`, одиночных bracket-date фрагментов и русских weekday labels;
- в [C:/Coding projects/university_timetables/src/timetable_scraper/normalize.py](C:/Coding%20projects/university_timetables/src/timetable_scraper/normalize.py) такие технические куски больше уходят в `notes`, а не остаются в `subject`; отдельно добавлена безопасная нормализация валидной аббревиатуры `техн.комп.бачення`;
- в [C:/Coding projects/university_timetables/src/timetable_scraper/normalize.py](C:/Coding%20projects/university_timetables/src/timetable_scraper/normalize.py) добавлен узкий merge для разрезанных `subject` в `sociology-schedule`, включая continuation через строку другой подгруппы и поглощение промежуточных дублей одного фрагмента;
- в [C:/Coding projects/university_timetables/src/timetable_scraper/qa.py](C:/Coding%20projects/university_timetables/src/timetable_scraper/qa.py) review-очередь теперь жёстче выкидывает административные и чисто технические строки без реального учебного содержимого.

Оставшиеся основные backlog-и после этого состояния:

- `phys-schedule`: `979 review`
- `sociology-schedule`: `725 review`
- `fit-schedule`: `531 review`
- `biomed-schedule`: `440 review`

Оставшиеся `tiny workbook`-и в полном baseline сейчас выглядят как спорные, но не явно ложные:

- `ГЕОГРАФІЯ ТА РЕГІОНАЛЬНІ СТУДІЇ.xlsx`
- `Природничі науки.xlsx`
- `СЕРЕДНЯ ОСВІТА.xlsx`
- `Психологія 1 курс _Магістр_.xlsx`
- `Фізика ядра та елементарних частинок.xlsx`
- `1 Архівістика та управл. док.xlsx`

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
