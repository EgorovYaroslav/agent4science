# Cross-Frequency Generalization of SRH Image Quality Classification

[![OpenCode](https://img.shields.io/badge/OpenCode-1.17.7-blue)](https://opencode.ai)

**Исследование:** Насколько хорошо модель классификации качества изображений
Сибирского радиогелиографа (СРГ), обученная на частоте 3000 МГц, обобщается на
данные 6000 МГц и 12200 МГц без дообучения.

**Результат:** Модель НЕ обобщается — согласованность 67.1% (6000 МГц) и 54.2%
(12200 МГц) при пороге 90%. Bad-изображения переносятся хорошо (80–92%), Ok —
плохо (22–56%).

---

## Структура проекта

```
├── experiment/
│   └── plots/                 # 6 графиков результатов
├── logs/                      # JSONL-логи эксперимента (read-only)
│   ├── h1_*.jsonl             # 100 записей самосогласованности (H1)
│   └── main_*.jsonl           # 3000 записей кросс-частотного теста
├── tools/
│   └── experiment_mcp.py      # MCP-сервер с 5 инструментами
├── materials/
│   ├── ftp_client.py          # Доступ к FTP СРГ (для справки)
│   └── api_client.py          # Доступ к API классификации (для справки)
├── results/
│   └── agreement_table.csv    # Таблица метрик по гипотезам
├── statement/                 # Постановка задачи и документация
│   ├── MOTIVATION.md          # Исходный вопрос
│   ├── LIT.md                 # Литературный обзор (15+ источников)
│   ├── HYPOTHESIS.md          # Гипотезы H1–H9
│   ├── TZ.md                  # Техническое задание
│   ├── diary.md               # Журнал работ (append-only)
│   └── STATUS.md              # Текущий статус
├── notes/paper/
│   └── ai4math_ysda2026_template/
│       ├── example_paper.tex  # Статья LaTeX
│       ├── example_paper.bib  # Библиография (17 источников)
│       ├── example_paper.pdf  # Скомпилированный PDF
│       └── figures/           # Графики для статьи
├── .opencode/skills/          # Скиллы opencode (6 шт.)
└── literature/
    └── 2507.04211v1.pdf       # Исходная статья Egorov, 2025
```

---

## Быстрый старт

### Linux / macOS

```bash
# 1. Клонировать
git clone https://github.com/EgorovYaroslav/agent4science.git
cd agent4science

# 2. Установить opencode
curl -fsSL https://opencode.ai/install | bash

# 3. Установить Python-зависимости
curl -fsSL https://astral.sh/uv/install.sh | bash
uv venv && source .venv/bin/activate && uv pip install -r requirements.txt

# 4. Запустить opencode
opencode
```

### Windows (opencode Desktop)

1. **Скачать opencode Desktop** — перейти на https://opencode.ai/download, скачать установщик для Windows (.exe или .msi)
2. **Установить** — запустить установщик, следовать инструкциям
3. **Клонировать репозиторий**:
   ```powershell
   git clone https://github.com/EgorovYaroslav/agent4science.git
   cd agent4science
   ```
4. **Установить Python 3.10+** — скачать с https://www.python.org/downloads/, при установке отметить «Add Python to PATH»
5. **Создать виртуальное окружение**:
   ```powershell
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```
6. **Запустить opencode Desktop** — открыть приложение, открыть папку проекта (`agent4science`), в чате написать `следуй инструкциям из AGENT.md`

Агент прочитает `AGENT.md` и `statement/MOTIVATION.md`, затем через MCP-инструменты изучит данные, вычислит метрики H1–H9 и сгенерирует 6 графиков.

**Эксперимент не запускается заново** — данные уже собраны в `logs/`. MCP-сервер (`tools/experiment_mcp.py`) читает логи и предоставляет 5 инструментов вместо реальных API-запросов (~1 мин вместо 73 мин).

### MCP-инструменты

| Инструмент | Назначение |
|-----------|-----------|
| `explore_data()` | Структура, каналы, количество триплетов, баланс классов |
| `explore_temporal()` | Помесячное распределение триплетов |
| `compute_metrics()` | Все метрики H1–H9: согласованность, bootstrap CI, χ², стратификация, t-test, Spearman, ANOVA, baseline |
| `generate_plots(output_dir?)` | 6 графиков: agreement_bar, distribution_by_channel, confidence_boxplot, agreement_by_class, agreement_vs_deltat, agreement_by_month |
| `get_h1_summary()` | H1 самосогласованность (S_self, CI) |

---

## Этап 8. Компиляция статьи

### Linux / macOS (локально)

```bash
# Вариант A — Tectonic (самый простой, не требует LaTeX)
curl -fsSL https://github.com/tectonic-typesetting/tectonic/releases/download/\
tectonic%400.15.0/tectonic-0.15.0-x86_64-unknown-linux-gnu.tar.gz | tar -xz
./tectonic -X compile notes/paper/ai4math_ysda2026_template/example_paper.tex

# Вариант B — pdflatex
pdflatex -interaction=nonstopmode -halt-on-error example_paper.tex
```

### Windows (рекомендуется Overleaf)

На Windows **не рекомендуется** устанавливать LaTeX локально. Вместо этого:

1. Загрузить папку `notes/paper/ai4math_ysda2026_template/` в **Overleaf** (https://www.overleaf.com)
2. Overleaf автоматически распознает `ai4math_ysda2026.sty` и `example_paper.bib`
3. Нажать «Recompile» — PDF будет готов через несколько секунд
4. Все графики из `figures/` подключатся автоматически

Если нужно компилировать локально на Windows — установить MiKTeX (https://miktex.org/) или TeX Live (https://tug.org/texlive/), затем запустить `pdflatex`.

---

## Гипотезы (H1–H9) и результаты

| # | Гипотеза | Результат |
|---|----------|-----------|
| H1 | Самосогласованность ≥ 0.95 | ✅ S = 1.0000 |
| H2 | S(3000,6000) = S(3000,12200) | ❌ p = 3.5e-9 |
| H3 | S ≥ 0.90 (6000) и S ≥ 0.85 (12200) | ❌ Оба порога не пройдены |
| H4 | Асимметрия Ok vs Bad | ✅ Bad: 80–92%, Ok: 22–56% |
| H5 | Уверенность падает с частотой | ✅ p = 7.4e-12 (3000 vs 12200) |
| H6 | Корреляция с Δt < 0 | ❌ ρ ≈ 0.02–0.06 |
| H7 | Распределения меток однородны | ❌ Ok rate: 54%→40%→16%, p ≈ 0 |
| H8 | Сезонная стабильность | ❌ 37–100%, p = 3.6e-28 |
| H9 | Модель > majority baseline | ✅ p ≈ 0 для обоих каналов |

---

## Адаптация под новое исследование

Чтобы использовать этот проект для собственного исследования, выполните `python3 clear.py` (сбрасывает проект в чистое состояние), затем отредактируйте:

### 1. `AGENT.md` — контракт агента

| Что менять | Где |
|-----------|-----|
| Название проекта | строка 4 — заголовок в описании роли |
| Входные данные | секция 7 — заменить описание СРГ, частот, API/FTP на свои |
| Исследовательские вопросы | секция 7 — перечислить свои вопросы |
| Гипотезы | секция 7 — таблица H1–H9 под вашу задачу |
| Структура проекта | секция 2 — если добавляете/убираете папки |
| Критерии готовности | секция 9 — убрать лишнее, добавить своё |

### 2. `statement/MOTIVATION.md` — исследовательский вопрос

| Что менять | Где |
|-----------|-----|
| Формулировка задачи | строка 5 — основной вопрос исследования |
| Формальное определение | строки 7–13 — переменные, датасеты, условия |
| Вопросы для ответа | строки 17–22 — перечислить свои |
| Источники данных | строки 47–51 — ссылки на API, FTP, БД |
| Ограничения | строки 44–56 — критерии включения, seed, объём выборки |
| Критерии успеха | строки 67–76 — что считается выполненной работой |

### 3. Другие файлы (опционально)

| Файл | Что делать |
|------|-----------|
| `opencode.json` | Поменять путь к MCP-серверу, если ваш скрипт называется иначе |
| `literature/` | Положить свои PDF, очистить папку |
| `logs/` | Заменить на свои JSONL-логи (формат: одна запись = один инференс) |
| `tools/experiment_mcp.py` | Переписать под свою логику чтения данных и метрики |
| `notes/paper/*/example_paper.tex` | Заменить шаблон конференции или убрать |

После правок — запустить `opencode` и написать в чат: «Выполни все этапы из AGENT.md».

---

## Зависимости

- Python 3.10+, opencode 1.17.7+
- `requests`, `numpy`, `pandas`, `scipy`, `matplotlib`, `mcp`
- Tectonic / LaTeX (для компиляции статьи)

---

## Автор

Ярослав Егоров, ИСЗФ СО РАН, Иркутск
