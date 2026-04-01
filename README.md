# Звіт до практичної роботи

## Тема
Використання інструментів для аналізу та оптимізації коду.

## Мета
Покращити якість і продуктивність Telegram-бота через аналіз коду, виправлення помилок, оптимізацію та профілювання.

## 1) Вибір інструментів аналізу коду
Використані інструменти:
- `python -m py_compile` і `python -m compileall` для статичного виявлення синтаксичних проблем.
- `unittest` для перевірки стабільності після правок.
- `cProfile` для пошуку вузьких місць CPU.
- `tracemalloc` для контролю використання пам'яті.
- Smoke-тести імпортів модулів і ініціалізації БД.

## 2) Аналіз коду і знайдені проблеми
Під час аналізу були знайдені критичні помилки:
- Невірний імпорт у `services/scraper.py`: `from db import ...` (модуль не існує).
- У `handlers/bot.py` були відсутні імпорти `Update`, `ReplyKeyboardMarkup`, `KeyboardButton`.
- Поламані виклики БД:
  - `get_schedule_for_date(date, queue)` замість `get_schedule_for_date(today)`.
  - виклик неіснуючої функції `get_schedule_for(...)` у `my_queue_schedule`.
- Невідповідність сигнатур: `set_user_address(...)` викликався з `subqueue`, але функція БД це не підтримувала.
- Невірний шлях до БД і PDF (залежав від поточної директорії).
- Небезпечний хардкод `BOT_TOKEN` у `config.py`.
- `handlers/bot.py` мав некоректний сценарій запуску (`asyncio` + `run_polling`) з ризиком runtime-помилки.

## 3) Оптимізація коду
Застосовані оптимізації:
- У `services/address_lookup.py`:
  - regex винесені в скомпільовані константи.
  - нормалізований текст адреси кешується (`norm_text`).
  - додано кешування `numbers/ranges` для кожного рядка під час завантаження PDF.
- У `services/scraper.py`:
  - нормалізація коду черги (`2,1` -> `2.1`).
  - парсинг часових інтервалів через regex.
  - дедуплікація інтервалів перед збереженням у БД.
- У `database/db.py`:
  - контекстні менеджери для підключень до SQLite.
  - безпечні міграції колонок.
  - додано `subqueue` в `users`.

## 4) Перевірка використання ресурсів
Виконано через `analysis/perf_profile.py` (`tracemalloc`):
- `load_time_sec=11.9059`
- `rows_city=82`, `rows_region=33`
- `memory_current_kb=3876.4`
- `memory_peak_kb=4481.5`

Висновок: основне ресурсомістке місце — початкове читання PDF, а не запити користувача після завантаження.

## 5) Використання профайлера
Профілювання (`cProfile`) до/після оптимізації гарячої ділянки `find_queue`:
- До: `lookup_iterations=5000 elapsed_sec=3.0647`
- Після: `lookup_iterations=5000 elapsed_sec=0.3890`

Прискорення приблизно у **7.9x** для серії пошуків.

## 6) Тестування оптимізацій
Додано тести:
- `tests/test_db.py`
  - перевірка збереження/читання адреси користувача.
  - перевірка агрегування графіків по даті/черзі.
- `tests/test_address_lookup.py`
  - пошук у діапазоні будинків.
  - пошук по населеному пункту без номера будинку.
  - сценарій `NOT_FOUND`.

Результат запуску:
- `Ran 5 tests in 0.061s`
- `OK`

## 7) Документація змін
Оновлено файли:
- `config.py`
- `database/db.py`
- `services/scraper.py`
- `services/address_lookup.py`
- `handlers/bot.py`
- `requirements.txt`
- `analysis/perf_profile.py`
- `tests/test_db.py`
- `tests/test_address_lookup.py`

## Як запустити перевірки
```bash
./venv/bin/python -m compileall config.py handlers services database tests analysis
./venv/bin/python -m unittest discover -s tests -v
./venv/bin/python analysis/perf_profile.py
```

## Як запустити бота
1. Встановити токен в змінну середовища:
```bash
export BOT_TOKEN="YOUR_TELEGRAM_BOT_TOKEN"
```
2. Запуск:
```bash
./venv/bin/python handlers/bot.py
```

## Підсумок
Виправлені критичні runtime-помилки, узгоджена модель даних черг, додано тести і профілювання. Проєкт переведений у стабільний стан для демонстрації практичної роботи з аналізом і оптимізацією коду.

## Обмеження середовища
- У поточному середовищі недоступний DNS/мережа до `www.roe.vsei.ua`, тому live-оновлення графіків зі сайту не виконувалось (локальна перевірка `scrape_and_store()` повернула `ConnectionError`).
