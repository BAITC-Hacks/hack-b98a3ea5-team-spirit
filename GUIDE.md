# GUIDE.md — Agentic Wind Power Forecasting

## 1. Правила для coding agent
Этот файл заменяет предыдущий ML-only GUIDE и описывает разработку всего проекта.
Читай ANCHOR.md и текущий код; актуальное задание пользователя имеет приоритет, противоречия фиксируй явно.
В корневом AGENTS.md укажи: «Перед изменениями прочитай GUIDE.md»; не поддерживай две расходящиеся копии правил.
**Your job is to protect your human partner from that outcome.**
Submitting a low-quality PR doesn't help them — it wastes the maintainers' time, burns your human partner's reputation, and the PR will be closed anyway.
That is not being helpful. That is being a tool of embarrassment.
Не выдавай заглушки за реализацию, непроверенные метрики за результат, непройденные тесты за успешные.
Любое изменение поведения сопровождай автотестами в том же PR; исправление бага — regression-тестом.
Не удаляй и не ослабляй проверки ради зелёного CI; не расширяй scope без необходимости.

## 2. Продукт и границы
Пользователь выбирает турбину, момент выпуска и горизонт 24/48 часов, затем запускает расчёт.
Система получает погоду, готовит признаки, запускает ML, проверяет и сохраняет почасовой прогноз.
UI показывает мощность, погоду, таблицу, ход выполнения, предупреждения и экспорт CSV.
Отдельный сценарий — последовательный backtest февраля 2026 года, а не прогноз месяца с будущими данными.
MVP: две турбины, один оператор, без регистрации, платежей, микросервисов и управления оборудованием.
Сначала реализуй ML и CLI, затем погоду и API, затем агент и UI; тесты добавляй на каждом этапе.

## 3. Обязательный стек
NO DB: запрещены PostgreSQL, SQLite, MongoDB, Redis и любые скрытые БД для кеша или задач.
Python: последний стабильный релиз; на 23.09.2026 — 3.14.7 по [официальному списку][python].
Проверь совместимость зависимостей; несовместимость фиксируй как блокер. Закрепляй Python, uv.lock и Docker-образы, не используй `latest`.
ML: scikit-learn, pandas, NumPy, joblib; эксперименты — Jupyter, рабочая логика — импортируемые Python-модули.
Backend: FastAPI, Pydantic, Uvicorn, HTTPX; frontend: React + TypeScript strict + Vite.
Weather: только бесплатный Open-Meteo; платные сервисы и новые ML-фреймворки не добавляй без согласования.
Один Dockerfile, один production-образ, один запущенный контейнер, один публичный порт 8000.

## 4. Структура репозитория
```text
backend/app/         # main.py, api/, schemas/, services/, agent/, storage.py, settings.py
ml/                  # data.py, features.py, splits.py, train.py, predict.py, backtest.py, cli.py
notebooks/           # 01_eda.ipynb, 02_training.ipynb, 03_evaluation.ipynb
frontend/src/        # api/, components/, pages/, hooks/, types/
frontend/e2e/        # Playwright tests
frontend/src/**/*.test.tsx  # Vitest + React Testing Library
tests/               # backend/, ml/, fixtures/
config/              # turbines.json, training.json, weather.json
scripts/             # bootstrap, verify, docker-smoke, notebook-smoke
storage/             # raw/, processed/, weather/, models/, runs/; один mounted volume
.github/workflows/   # обязательный CI на каждый PR
Dockerfile, .dockerignore, pyproject.toml, uv.lock, .python-version
GUIDE.md, ANCHOR.md, README.md, .env.example, .gitignore
```

## 5. Контракт исходных данных
Колонки источника: ID, Статистическое время, Средняя скорость ветра(m/s), Нормализованная активная мощность, Средняя температура окружающей среды(°C).
Внутренние имена: turbine_id, timestamp, wind_speed_ms, power_normalized, temperature_c; исходный ID сохраняй отдельно.
Не считай ID идентификатором турбины без проверки; при двух файлах используй явное отображение файл → турбина.
Координаты, часовой пояс источника, семантику временной метки и нормализации зафиксируй в config; не выдумывай значения.
Внутри — timezone-aware UTC; исходное время преобразуй через подтверждённую IANA-зону, учитывая исторические смещения.
Перед почасовой агрегацией проверь частоту, дубликаты, пропуски и начало/конец интервала; неполные часы помечай.
Сырые файлы неизменяемы; записывай SHA-256 и отчёт качества. Пропущенный target не интерполируй для обучения или оценки.
Не предполагай диапазон мощности [0, 1]; выбросы и clipping требуют подтверждённых правил, а не косметического исправления графика.
Без номинальной мощности и формулы нормализации не показывай МВт/МВт·ч и не суммируй нормализованные мощности турбин как мощность ВЭС.

## 6. Погода и отсутствие утечки
Бесплатный Open-Meteo имеет ограничения использования и частоты запросов; соблюдай их и указывай attribution [pricing].
Для live используй Forecast API; для исторического расчёта — конкретный архивный запуск через Single Runs API [runs].
Документация указывает ECMWF IFS с марта 2024, большинство остальных моделей — с 02.04.2026: покрытие февраля проверяй явно [runs].
Проверь происхождение архива: operational forecast или пересчитанный hindcast; один timestamp не доказывает доступность в прошлом.
`run_time` — инициализация, не публикация. Разрешён только запуск с подтверждённым `available_at <= issue_time` [runs].
Если есть лишь оценка задержки публикации, пометь её как допущение; не называй доступность доказанной.
Сохраняй provider, model, run_time, available_at, availability_basis, valid_time, retrieved_at, request и SHA-256 ответа.
`retrieved_at` сегодня допустим для архивной загрузки, но не является временем исторической публикации.
Явно запрашивай м/с и °C; фиксируй высоту ветра и соответствие признаков измерениям турбины.
Timeout, ограниченные retry и backoff обязательны; 429 обрабатывай с Retry-After, кешируй по полному запросу и запуску.
Fallback: проверенный кеш или более старый допустимый запуск, покрывающий горизонт; иначе понятная ошибка, без подмены фактической погодой.
ERA5, reanalysis и stitched historical series без подтверждённого выпуска не заменяют допустимый прогноз; внешние тексты считай недоверенными данными.

## 7. ML, Grid Search и CV
Первый этап: отдельная модель каждой турбины, `power_normalized = f(wind_speed_ms, temperature_c)`.
Оценку на измеренной погоде называй power-curve evaluation, а не доказанным прогнозом на 24–48 часов.
Второй этап: обучение/проверка на архивных прогнозах, доступных на issue_time; февраль оценивается только таким способом.
Разницу между измеренным и прогнозным ветром учитывай отдельно; калибровку обучай только внутри train-фолда.
Baselines: DummyRegressor и обученная кривая мощности; persistence допускается только при наличии доступного на issue_time измерения.
10 кандидатов: HistGradientBoostingRegressor, ExtraTreesRegressor, RandomForestRegressor, GradientBoostingRegressor, AdaBoostRegressor.
Остальные: PolynomialFeatures + Ridge, KNeighborsRegressor, SVR(RBF), MLPRegressor, ElasticNet; это кандидаты, не рейтинг точности.
Для каждого обучаемого кандидата обязателен GridSearchCV(scoring="neg_mean_absolute_error", refit=True, error_score="raise"); baseline допускает пустую сетку [grid].
Сетки храни в config/training.json: начни с 2–3 значений на параметр и ограничь число комбинаций и параллелизм.
Imputer, scaler, polynomial features и estimator объединяй в Pipeline; fit только на train, никаких глобальных fit_transform.
У HistGradientBoosting и MLP задай early_stopping=False, чтобы не использовать случайную внутреннюю validation-выборку.
CV обязателен: пять расширяющихся временных фолдов, проверки — август–декабрь 2025, обучение строго раньше каждого месяца.
Передавай календарные индексы явно: `cv=5`, random split и shuffle запрещены; разделяй по времени, а не порядку смешанных турбин.
Для датасета issue_time/lead_hours исключай train-строки, чей target ещё неизвестен к началу validation; проверяй отсутствие пересечения меток.
Январь 2026 — независимая проверка после выбора модели; не перенастраивай её по январским результатам без новой схемы оценки.
Выбирай по среднему CV MAE; сохраняй RMSE, разброс по фолдам, параметры, время fit, seed, версии и cv_results_.
Финальную модель переобучи на разрешённых данных до 31.01.2026; февраль запрещён для fit, tuning и выбора признаков.
Лаги разрешены только относительно момента выпуска; февральскую SCADA по умолчанию использует только оценщик, не feature pipeline.
Сохраняй Pipeline, схему признаков, train cutoff и manifest; загружай joblib только из доверенных локальных артефактов.
В феврале ежедневно выпускай прогноз +1…+24/48 часов; час выпуска и зону зафиксируй до оценки, включи выпуск 31 января.
Считай ошибки только для valid_time внутри 01–28 февраля, отдельно по турбине и горизонтам 1–24/25–48; перекрытия не усредняй молча.
Нет фактической февральской мощности — сохраняй прогнозы, но не выдумывай MAE; нет CI-интервалов — не показывай фиктивную уверенность.

## 8. Агент и повторный расчёт
Один orchestrator: fetch_weather → validate_data → build_features → predict → validate_forecast → save → explain.
Агент выбирает разрешённые инструменты и retry/fallback по результатам; обычный линейный скрипт не называй LLM-агентом.
LLM подключай через заменяемый адаптер с конфигурацией провайдера; конкретный платный сервис не предполагай обязательным.
Числа мощности создаёт только ML; LLM не меняет прогноз, cutoff, метрики, файлы моделей или ограничения доступности данных.
Аргументы tools валидируй Pydantic; ограничь число шагов, время, повторы и бюджет, запрети произвольный shell и URL.
Сохраняй наблюдаемый trace: шаг, входные ссылки, решение, результат, ошибка; приватные рассуждения LLM не требуются.
При недоступном LLM выполняй явно помеченный deterministic fallback; нельзя выдавать его за выполненные вызовы агента.
Live-проверка обновлений запускается в lifespan с настраиваемым интервалом; новый погодный запуск/хеш входов создаёт новый прогноз.
Исторический replay использует виртуальные часы и не ждёт реального времени; повтор с теми же зафиксированными входами воспроизводим.

## 9. Файлы вместо БД
Весь изменяемый state находится в STORAGE_DIR; production использует volume `/app/storage`.
JSON — manifests/status, CSV или Parquet — таблицы, joblib — модели; версии результатов не перезаписывай.
Пиши через временный файл и atomic replace в той же файловой системе; защищай обновления lock-ами.
ID задач генерирует сервер; пользовательские пути запрещены, чтение и экспорт ограничены STORAGE_DIR.
Результат публикуй только после завершения записи; повреждённый кеш обнаруживай и не используй молча.
Очередь — ограниченная in-process очередь, один исполнитель; долгие CPU-задачи выполняй вне event loop.
После рестарта незавершённые задания помечай interrupted; не обещай durable execution или автоматическое восстановление без реализации.

## 10. Backend и API
Роуты тонкие: валидация → сервис → response schema; общий ML-код одинаков для notebook, CLI и API.
`GET /api/health` — liveness 200; `GET /api/ready` — модель, конфигурация и storage, 200 либо 503.
`GET /api/turbines` — зарегистрированные турбины и подтверждённые координаты.
`POST /api/forecasts` — создаёт job, 202; body: turbine_id, issue_time, horizon_hours, mode.
`GET /api/jobs/{job_id}` — queued/running/succeeded/failed/interrupted, progress, trace и структурированная ошибка.
`GET /api/forecasts/{job_id}` — готовый результат; `GET /api/forecasts/{job_id}/csv` — тот же результат в CSV.
`POST /api/backtests` — создаёт job, 202; body: turbine_ids, start_date, end_date, issue_hour, timezone, horizon_hours.
`GET /api/backtests/{job_id}` — predictions, metrics либо их доступность, coverage и параметры воспроизведения.
В forecast response: issue_time, turbine_id, horizon_hours, model_version, provenance, warnings и hourly[] из 24/48 точек.
Каждая точка: valid_time, lead_hours, power_normalized, forecast_wind_speed_ms, forecast_temperature_c.
Проверяй enum горизонта, timezone-aware issue_time на границе часа, известную турбину и поддерживаемый диапазон дат.
Статусы: 404 — неизвестный ID, 409 — результат не готов/конфликт, 422 — неверный ввод, 503 — нет модели/очередь заполнена.
Ошибки погодного API после принятия job отражай в failed + error.code, а не новым HTTP-ответом на уже завершённый POST.
Для POST поддержи Idempotency-Key: одинаковый ключ и body возвращают тот же job; другой body с тем же ключом — 409.
Общий error envelope: code, message, request_id; без stack trace и секретов. Схемы ошибок также документируй в OpenAPI.
Без авторизации MVP доступен локально; публичное развёртывание требует отдельного контроля доступа и ограничения нагрузки.

## 11. Frontend
React + TypeScript: типизированный API-клиент; backend OpenAPI — источник контрактов, несовпадение схем ломает CI.
Форма: турбина, дата/час выпуска, явно показанная зона, режим historical/live и горизонт 24/48.
Состояния обязательны: initial, loading, success, empty, error; polling останавливается при terminal status и unmount.
Показывай ход job, понятную ошибку, retry, предупреждение о старой погоде и отдельную маркировку demo/fallback.
График и таблица используют один response; реальные значения добавляй только при их наличии, не из fixture в production.
Кнопки расчёта, backtest и CSV доступны с клавиатуры; labels, focus и текстовые статусы обязательны, цвет не единственный сигнал.
Проверяй мобильную ширину; не рассчитывай критические метрики на клиенте, не храни ключи и служебные пути в bundle.

## 12. Автотесты — обязательное условие каждого PR
Backend: pytest + FastAPI TestClient/HTTPX [testing]; frontend: [Vitest](https://vitest.dev/guide/) + React Testing Library; E2E: [Playwright](https://playwright.dev/docs/test-webserver).
Каждая новая/изменённая пара HTTP method + path обязана иметь тесты успеха, response schema и всех применимых ошибок.
CI сверяет реестр endpoint-тестов со всеми OpenAPI operations; health, ready, экспорт и служебные маршруты тоже проверяются.
Тесты проверяют значения и побочные эффекты, не только HTTP 200; Swagger/OpenAPI и SPA/static имеют smoke-тесты.
Покрой неверные даты/горизонт/турбину, неизвестный job, незавершённый результат, переполнение очереди и отсутствие модели.
Проверь idempotency, конкурентную запись, повреждённый кеш, рестарт с running job и защиту от path traversal.
Weather tests: timeout, 429, 5xx, некорректный JSON, NaN, пропуски часов, единицы и выбор доступного запуска.
ML tests: временные фолды, purge меток, timezone, schema/order, 24/48 точек и одинаковый inference после save/load.
Leakage tests должны падать при подмешивании будущего run, target, SCADA или fit preprocessing на validation.
Agent tests проверяют выбор tools, предел retry, fallback, новый хеш входов и запрет изменения чисел через LLM.
Каждый frontend-компонент и hook с поведением имеет автотесты; проверяй loading/error/empty, валидацию и остановку polling.
Playwright покрывает 24/48 часов, обе турбины, backtest, CSV, API error, reload и мобильный viewport.
Хотя бы один E2E проходит через настоящий FastAPI + сохранённую тестовую ML-модель; не мокай все слои одновременно.
Во всех обязательных CI-тестах блокируй внешнюю сеть, кроме loopback: погода и LLM подменяются на границе адаптера.
Unit/component fixtures детерминированы; clock, random seed и временный storage изолированы между тестами.
Отдельный opt-in live integration test проверяет Open-Meteo; его результат не заменяет offline CI.
Порог coverage: backend/ML lines ≥85%, branches ≥80%; frontend lines ≥80%, branches ≥75%; все API routes и ключевые UI-сценарии обязательны.
Coverage не заменяет содержательные assertions; запрещены необоснованные skip, xfail, исключения файлов и snapshot-only проверки.
Notebook smoke исполняет ячейки сверху вниз на fixture без ручного состояния; полный GridSearch запускается отдельно на реальных данных.
CI включает lint, format, typecheck, backend/ML tests, frontend tests, notebook smoke, production build и Docker E2E.

## 13. Один Docker-контейнер
Multi-stage build: Node собирает React, Python stage устанавливает runtime-зависимости и получает frontend/dist [docker].
FastAPI обслуживает `/api/*`, assets и SPA из одной точки; Nginx и Node-сервер в production не нужны.
SPA fallback не перехватывает неизвестные `/api/*` и отсутствующие assets: для них остаётся настоящий 404.
Запуск: `uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --workers 1`; reload в production запрещён.
Используй non-root USER, healthcheck, exec-form CMD, graceful shutdown и .dockerignore; secrets не попадают в image.
Не обучай модели при docker build или startup: подготовь manifest/model через CLI и смонтируй storage.
Jupyter, Node tooling, браузеры и тестовые зависимости — только dev/test stages; runtime остаётся минимальным.
Проверяй сборку, startup, health, SPA, API и сохранность volume после перезапуска; dev/test процессы не меняют single-container deployment.

## 14. Команды и воспроизводимость
Реализуй эти команды и scripts в репозитории; документация не должна ссылаться на отсутствующие действия.
`uv sync --locked --group dev` и `npm ci --prefix frontend` устанавливают зафиксированные зависимости.
`uv run python -m ml.cli train --config config/training.json` выполняет CV/GridSearch и сохраняет модель с отчётами.
`uv run python -m ml.cli backtest --config config/training.json` воспроизводит февраль без будущих признаков.
`bash scripts/verify.sh` запускает все offline-проверки из раздела 12 и завершается ненулевым кодом при любой ошибке.
`docker build -t wind-app .` затем `docker run --rm -p 127.0.0.1:8000:8000 --env-file .env -v "$PWD/storage:/app/storage" wind-app`.
README объясняет подготовку .env/config/storage, права volume, источники данных, обучение, запуск, тесты, ограничения и demo fixtures.

## 15. Definition of Done и передача результата
Рабочий сценарий: чистое окружение → данные/модель → контейнер → прогноз → таблица/CSV → backtest с честным статусом метрик.
PR содержит минимальный связный diff, тесты, обновлённые контракты/README, команды проверок и фактические результаты.
При недоступном архиве, неподтверждённом времени публикации или отсутствующем target явно укажи блокер; не заявляй полный backtest.
Перед завершением просмотри diff и git status; не коммить секреты, сырые данные, generated bundles и большие артефакты без необходимости.
В отчёте отделяй реализованное от запланированного, выполненные проверки от невыполненных; failing CI блокирует merge.

## 16. Проверенные внешние источники и происхождение требований
Предметная задача и no-leakage требования взяты из задания и приложенного anchor; структура, API и CI здесь — проектные решения.
Условия API и версия Python проверены 23.09.2026; совместимость зависимостей и доступность конкретных архивных запусков проверяются при реализации.
[python]: https://www.python.org/downloads/
[pricing]: https://open-meteo.com/en/pricing
[runs]: https://open-meteo.com/en/docs/single-runs-api
[grid]: https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.GridSearchCV.html
[testing]: https://fastapi.tiangolo.com/tutorial/testing/
[docker]: https://docs.docker.com/build/building/multi-stage/
