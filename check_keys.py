"""Проверка ключей и моделей, которые использует бот.

Запуск (рядом с .env):
    python check_keys.py

Ключи не печатаются — только маскируются. Код возврата 0, если всё критичное работает.
"""

import base64
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ENV_PATH = Path(__file__).resolve().parent / ".env"

CHAT_MODEL = "openrouter/free"
VISION_MODEL = "google/gemma-3-12b-it:free"
DEFAULT_IMAGE_MODEL = "google/gemini-2.5-flash-preview"
TRANSCRIBE_MODEL = "openai/whisper-1"

ok = True


def load_env() -> None:
    if not ENV_PATH.exists():
        print(f"❌ .env не найден: {ENV_PATH}")
        sys.exit(2)
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())
    print(f"✅ .env загружен: {ENV_PATH}")


def mask(value: str | None) -> str:
    if not value:
        return "не задан"
    return f"{value[:7]}…{value[-4:]} (длина {len(value)})"


def request(url: str, key: str | None = None, payload: dict | None = None, timeout: int = 60):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, method="POST" if payload else "GET")
    req.add_header("Content-Type", "application/json")
    req.add_header("User-Agent", "telegram-ai-assistant-keycheck/1.0")
    if key:
        req.add_header("Authorization", f"Bearer {key}")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "ignore")[:300]
        raise RuntimeError(f"HTTP {e.code}: {body}") from None
    except Exception as e:  # noqa: BLE001
        raise RuntimeError(f"{type(e).__name__}: {e}") from None


def check_openrouter_key(key: str) -> None:
    global ok
    print(f"\n[1] OpenRouter ключ: {mask(key)}")
    try:
        info = request("https://openrouter.ai/api/v1/key", key)
        data = info.get("data", {})
        print(f"    ✅ ключ принят: label={data.get('label')!r}, usage=${data.get('usage', 0)}, limit={data.get('limit')}")
        if data.get("limit") is not None and data.get("usage", 0) >= data.get("limit"):
            print("    ⚠️ лимит ключа исчерпан")
            ok = False
    except RuntimeError as e:
        print(f"    ❌ {e}")
        ok = False


def check_models() -> dict[str, list[str]]:
    print("\n[2] Список моделей OpenRouter")
    try:
        models = request("https://openrouter.ai/api/v1/models")
        found = {
            m["id"]: (m.get("architecture") or {}).get("output_modalities") or []
            for m in models.get("data", [])
        }
        print(f"    ✅ доступно моделей: {len(found)}")
        return found
    except RuntimeError as e:
        print(f"    ❌ не удалось получить список: {e}")
        return {}


def check_chat(key: str, models: dict[str, list[str]]) -> None:
    global ok
    print(f"\n[3] Чат, модель {CHAT_MODEL}")
    if CHAT_MODEL not in models:
        print("    ⚠️ модели нет в публичном списке (может быть алиасом — всё равно пробуем)")
    try:
        r = request(
            "https://openrouter.ai/api/v1/chat/completions",
            key,
            {"model": CHAT_MODEL, "messages": [{"role": "user", "content": "Ответь одним словом: работает"}], "max_tokens": 20},
        )
        print(f"    ✅ ответ: {r['choices'][0]['message']['content'].strip()[:80]!r}")
    except RuntimeError as e:
        print(f"    ❌ {e}")
        ok = False


def check_image(key: str, models: dict[str, list[str]]) -> None:
    global ok
    # читаем уже после load_env(), чтобы подхватить значение из .env
    model = os.getenv("IMAGE_MODEL", DEFAULT_IMAGE_MODEL)
    print(f"\n[4] Генерация картинок, модель {model}")
    images = 0
    try:
        r = request(
            "https://openrouter.ai/api/v1/chat/completions",
            key,
            {
                "model": model,
                "messages": [{"role": "user", "content": "A red circle on white background"}],
                "modalities": ["image", "text"],
                "max_tokens": 512,
            },
            timeout=120,
        )
        for choice in r.get("choices", []):
            content = choice.get("message", {}).get("content")
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "image_url":
                        url = block["image_url"]["url"]
                        size = len(base64.b64decode(url.split(",", 1)[1])) if url.startswith("data:") else "URL"
                        images += 1
                        print(f"    ✅ картинка получена: {size} байт")
        if not images:
            print(f"    ❌ ответ без изображения. Ключи ответа: {list(r)[:6]}, finish_reason={r['choices'][0].get('finish_reason')}")
    except RuntimeError as e:
        print(f"    ❌ {e}")
        print("    💡 частая причина: у модели нет доступа к image-выходу или закончились кредиты")

    if not images:
        ok = False
        candidates = [mid for mid, outs in models.items() if "image" in outs]
        if candidates:
            print(f"    💡 модели с image-выходом ({len(candidates)}), можно указать в IMAGE_MODEL:")
            for c in candidates[:10]:
                print(f"       {c}")


def check_weather(key: str | None) -> None:
    print("\n[5] Погода (WeatherAPI)")
    if not key:
        print("    ⏭ WEATHER_API_KEY не задан — пропускаю")
        return
    try:
        q = urllib.parse.quote("Moscow")
        data = request(f"http://api.weatherapi.com/v1/current.json?key={key}&q={q}&lang=ru")
        print(f"    ✅ {data['location']['name']}: {data['current']['temp_c']}°C, {data['current']['condition']['text']}")
    except RuntimeError as e:
        print(f"    ❌ {e}")


def main() -> None:
    load_env()
    or_key = os.getenv("OPENROUTER_KEY")
    if not or_key:
        print("\n❌ OPENROUTER_KEY не задан в .env")
        sys.exit(2)
    check_openrouter_key(or_key)
    models = check_models()
    check_chat(or_key, models)
    check_image(or_key, models)
    check_weather(os.getenv("WEATHER_API_KEY"))

    print("\n" + ("=" * 50))
    print("✅ критичные проверки пройдены" if ok else "❌ есть проблемы — см. ❌ выше")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
