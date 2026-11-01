# 🤖 Telegram AI Assistant

Личный ИИ-ассистент для Telegram: помнит контекст разговора, понимает скриншоты, голосовые сообщения и файлы, подсказывает погоду, рисует картинки и отдаёт сгенерированный код готовыми файлами.

Написан на **aiogram 3** + **ProxyAPI** (OpenAI-совместимый API, работает из России). Провайдер задаётся переменными окружения, поэтому бот не привязан к одному сервису: подойдёт любой OpenAI-совместимый API.

---

## Возможности

| Возможность | Как работает |
| --- | --- |
| 💬 **Чат с ИИ** | `CHAT_MODEL`, по умолчанию `gpt-4o-mini` |
| 🧠 **Память диалога** | Последние 20 сообщений хранятся в SQLite |
| 📸 **Анализ скриншотов** | Отправь фото с подписью-вопросом → ответ от `VISION_MODEL` |
| 🎤 **Голосовые сообщения** | Распознавание речи через `TRANSCRIBE_MODEL` (Whisper) |
| 📄 **Файлы и PDF** | Код читается как текст, PDF разбирается через `pypdf` (до 8000 символов) |
| 💻 **Код файлами** | Блоки кода из ответа приходят как `.py`, `.js`, `.html` и т.д., несколько — одним `.zip` |
| 🌤 **Погода** | WeatherAPI, понимает падежи: «погода в Казани», «а в Воронеже?» |
| 🎨 **Генерация картинок** | «Нарисуй кота» → промпт переводится на английский → `IMAGE_MODEL` |
| 🛟 **DoH-фолбэк** | Если DNS блокирует хост, резолв идёт через Cloudflare `1.1.1.1` |
| 🗑 **Очистка контекста** | Удаляет сообщения бота из чата и историю из базы |

---

## Команды и кнопки

| Команда | Кнопка | Действие |
| --- | --- | --- |
| `/start` | — | Приветствие, список возможностей, главная клавиатура |
| `/history` | 📜 История чата | Присылает полный лог диалога файлом `chat_history.txt` |
| `/clear` | 🗑 Очистить контекст | Удаляет историю сообщений и записи из БД |

Погода вызывается обычным текстом: `погода в Москве`, `какая погода в Питере`.

---

## Структура проекта

```
telegram-bot/
├── bot.py            # весь бот: хендлеры, работа с ИИ, БД
├── check_keys.py     # проверка ключей и моделей из .env
├── chat_history.db   # создаётся автоматически при первом запуске
└── .env              # секреты — в репозиторий не попадает
```

Внутри `bot.py`:

- `get_weather()` / `normalize_city()` — погода и нормализация падежей городов;
- `generate_image()` / `translate_to_english()` — генерация изображений;
- `call_ai_with_history()` / `call_ai_with_image()` — запросы к моделям;
- `save_message()` / `get_history_for_ai()` — история в SQLite;
- `handle_code_blocks()` — превращение блоков кода в файлы и архивы;
- `resolve_via_doh()` — резолв доменов через DNS-over-HTTPS.

---

## Установка

Требуется **Python 3.10+**.

```bash
git clone https://github.com/turygin0812a-arch/telegram-bot.git
cd telegram-bot

python -m venv venv
# Windows
venv\Scripts\activate
# Linux / macOS
source venv/bin/activate

pip install aiogram openai python-dotenv pypdf
```

### Настройка `.env`

Создай файл `.env` рядом с `bot.py`:

```env
# Обязательные
TELEGRAM_TOKEN=123456:ABC-DEF...          # токен от @BotFather
AI_API_KEY=sk-...                         # ключ ProxyAPI (proxyapi.ru)

# Адрес API и модели (необязательные — ниже значения по умолчанию)
AI_BASE_URL=https://api.proxyapi.ru/openai/v1
CHAT_MODEL=gpt-4o-mini
VISION_MODEL=gpt-4o-mini
TRANSCRIBE_MODEL=whisper-1

# Картинки
IMAGE_API=images
IMAGE_MODEL=dall-e-3
IMAGE_SIZE=1024x1024

# Погода
WEATHER_API_KEY=...                       # ключ с weatherapi.com
```

| Переменная | Обязательна | По умолчанию | Назначение |
| --- | --- | --- | --- |
| `TELEGRAM_TOKEN` | ✅ | — | Токен бота от [@BotFather](https://t.me/BotFather) |
| `AI_API_KEY` | ✅ | — | Ключ провайдера моделей (ProxyAPI). Также принимаются `PROXYAPI_KEY` и старый `OPENROUTER_KEY` |
| `AI_BASE_URL` | ❌ | `https://api.proxyapi.ru/openai/v1` | Адрес OpenAI-совместимого API |
| `CHAT_MODEL` | ❌ | `gpt-4o-mini` | Модель для чата и перевода промптов |
| `VISION_MODEL` | ❌ | `gpt-4o-mini` | Модель для анализа изображений |
| `TRANSCRIBE_MODEL` | ❌ | `whisper-1` | Модель распознавания речи |
| `IMAGE_API` | ❌ | `images` | `images` — эндпоинт `/images/generations`; `chat` — старый режим OpenRouter |
| `IMAGE_MODEL` | ❌ | `dall-e-3` | Модель генерации картинок |
| `IMAGE_SIZE` | ❌ | `1024x1024` | Размер картинки |
| `WEATHER_API_KEY` | ❌ | — | [WeatherAPI](https://www.weatherapi.com/) — без него погода отключена |

> ⚠️ `.env` содержит секреты. Не коммить его: добавь в `.gitignore` строку `.env`.

### Проверка ключей

```bash
python check_keys.py
```

Скрипт проверит ключ провайдера, выведет доступные модели, прогонит чат, vision и генерацию картинки, а также погоду. Если модель из `.env` недоступна, он напечатает подходящие варианты из каталога провайдера. Генерацию картинки можно пропустить (она платная): `python check_keys.py --skip-image`.

---

## Запуск

```bash
python bot.py
```

При старте бот печатает сводку: адрес API, модели чата, vision и картинок, статус контекста, голоса, PDF и погоды.

---

## Как это устроено

- **Транспорт** — long polling aiogram 3, `MemoryStorage`.
- **Модели** — один клиент `OpenAI(base_url=AI_BASE_URL, api_key=AI_API_KEY)`, модели переключаются переменными окружения.
- **История** — SQLite-файл `chat_history.db`, таблица `history(user_id, role, text, timestamp, message_id)`. Хранится последние 20 сообщений на пользователя.
- **Длинные ответы** — режутся на части по 4000 символов (лимит Telegram).
- **Картинки** — «нарисуй …» → промпт переводится на английский → при `IMAGE_API=images` запрос идёт в `/images/generations`, при `IMAGE_API=chat` — в чат с `modalities: ["image", "text"]`. Байты картинки уходят в `answer_photo`. Таймаут 180 секунд, ошибки 402/404 подсказывают причину.
- **Сеть** — `socket.getaddrinfo` патчится: при ошибке DNS запрос уходит на Cloudflare DoH.

---

## Смена провайдера

Бот работает с любым OpenAI-совместимым API: ProxyAPI, OpenRouter, Cloud.ru, VseGPT и т.п. Достаточно поменять `.env`, код править не нужно.

**Возврат на OpenRouter:**

```env
AI_BASE_URL=https://openrouter.ai/api/v1
AI_API_KEY=sk-or-v1-...
CHAT_MODEL=openrouter/free
VISION_MODEL=google/gemma-3-12b-it:free
TRANSCRIBE_MODEL=openai/whisper-1
IMAGE_API=chat
IMAGE_MODEL=google/gemini-2.5-flash-preview
```

После смены провайдера запусти `python check_keys.py` — он покажет, какие модели реально доступны по твоему ключу.

---

## Ограничения

- Состояние диалога в памяти процесса: после перезапуска контекст модели начинается заново (история в БД остаётся).
- Лимит PDF-текста — 8000 символов, файлы читаются как UTF-8.
- Таймаут запроса к ИИ — 120 секунд.
- Названия моделей должны совпадать с каталогом провайдера: при смене провайдера проверь их через `check_keys.py` или в документации.
- Распознавание речи проверяется только реальным голосовым сообщением — в `check_keys.py` этот пункт пропускается.

---

## Лицензия

Не указана. По вопросам использования — к автору репозитория.
