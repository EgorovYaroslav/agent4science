# Cross-Frequency Generalization of SRH Image Quality Classification

[![OpenCode](https://img.shields.io/badge/OpenCode-1.17.7-blue)](https://opencode.ai)

**Исследование:** Насколько хорошо модель классификации качества изображений
Сибирского радиогелиографа (СРГ), обученная на частоте 3000 МГц, обобщается на
данные 6000 МГц и 12200 МГц без дообучения.

**Результат:** Модель НЕ обобщается — согласованность 67.1% (6000 МГц) и 54.2%
(12200 МГц) при пороге 90%. Bad-изображения переносятся хорошо (80–92%), Ok —
плохо (22–56%).

## Структура проекта

```
├── experiment.py              # Скрипт эксперимента (H1–H9)
├── experiment/
│   └── plots/                 # 6 графиков результатов
├── materials/
│   ├── ftp_client.py          # Доступ к FTP СРГ
│   └── api_client.py          # Доступ к API классификации
├── logs/                      # JSONL-логи инференса (3000 записей)
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
└── literature/
    └── 2507.04211v1.pdf       # Исходная статья Egorov, 2025
```

## Быстрый старт

### 1. Клонировать репозиторий

```bash
git clone https://github.com/EgorovYaroslav/agent4science.git
cd agent4science
```

### 2. Установить opencode

Вариант 1 — curl (рекомендуется):

```bash
curl -fsSL https://opencode.ai/install | bash
```

Вариант 2 — npm:

```bash
npm install -g opencode-ai
```

Вариант 3 — brew:

```bash
brew install anomalyco/tap/opencode
```

### 3. Установить зависимости Python

```bash
pip install -r requirements.txt
```

### 4. Запустить opencode как web-клиент

```bash
# Запустить веб-сервер opencode в корне проекта
cd /path/to/agent4science
opencode web --port 4096

# Открыть в браузере: http://localhost:4096
```

Опционально — с паролем для сетевого доступа:

```bash
OPENCODE_SERVER_PASSWORD=mysecret opencode web --hostname 0.0.0.0 --port 4096
```

### 5. Запустить эксперимент

```bash
# Проверка самосогласованности (H1) + основной эксперимент (H2–H9)
python3 experiment.py --seed 42 --n-samples 1000 --max-diff-sec 180

# Пропустить H1, если уже пройден
python3 experiment.py --skip-h1 --n-samples 1000 --max-diff-sec 180
```

Эксперимент выполняет ~3000 запросов к API (1 req/s), ожидаемое время ~50 мин.

### 6. Скомпилировать статью

```bash
# Установить tectonic (standalone LaTeX)
curl -fsSL https://github.com/tectonic-typesetting/tectonic/releases/download/\
tectonic%400.15.0/tectonic-0.15.0-x86_64-unknown-linux-gnu.tar.gz \
  | tar -xz

# Скомпилировать
./tectonic -X compile notes/paper/ai4math_ysda2026_template/example_paper.tex
```

## Воспроизведение по этапам

Проект размечен git-тегами. Каждый тег — контрольная точка одного этапа:

| Тег | Этап | Что сделано |
|-----|------|-------------|
| `snapshot_20250615_100000` | 1. Литература | Прочитан PDF, создан LIT.md с gap analysis |
| `snapshot_20250615_100001` | 2. Декомпозиция | M.0–M.9 в diary.md |
| `snapshot_20250615_100002` | 3. Гипотезы | H1–H9 в HYPOTHESIS.md |
| `snapshot_20250615_100003` | 4. TЗ | TZ.md: план эксперимента |
| `experiment-v1` | 5–6. Эксперимент | experiment.py, 1000 триплетов, 6 графиков |
| `paper-v1` | 7. Статья | example_paper.tex, 17 refs, compiled PDF |

Воспроизвести конкретный этап:

```bash
git checkout <tag>
# Например:
git checkout experiment-v1
```

## Гипотезы (H1–H9)

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

## Зависимости

- Python 3.10+
- `requests`, `numpy`, `pandas`, `scipy`, `matplotlib`
- OpenCode 1.17.7+ (для воспроизведения через агента)
- Tectonic / LaTeX (для компиляции статьи)

## Данные и API

- **FTP:** https://ftp.rao.istp.ac.ru/SRH/ (данные СРГ за 2025 год)
- **API:** https://forecasting.iszf.irk.ru/api/srh/predict
- **Ограничение:** 1 запрос/с, seed=42 для воспроизводимости

## Автор

Ярослав Егоров, ИСЗФ СО РАН, Иркутск
