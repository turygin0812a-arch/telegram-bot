"""Проверка ключей и моделей, которые использует бот.

Запуск (рядом с .env):
    python check_keys.py               # полная проверка, включая генерацию картинки
    python check_keys.py --skip-image  # без генерации картинки (она платная)

Ключи не печатаются — только маскируются. Код возврата 0, если всё критичное работает.
"""

import argparse
import base64
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ENV_PATH = Path(__file__).resolve().parent / ".env"

# Чтобы эмодзи не роняли вывод при перенаправлении на Windows (cp1251 и т.п.)
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(errors="replace")
    except Exception:
        pass

# 1x1 прозрачный PNG — минимальная картинка для проверки vision
TINY_PNG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)

ok = True


def load_env() -> None:
    if not ENV_PATH.exists():
        print(f"❌ .env не найден: {ENV_PATH}")
        sys.exit(2)
    for line in ENV_PATH.read_text(encoding="utf-8-sig").splitlines():
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
    req = urllib.request.Request(url, data=data, method="POST" if payload is not None else "GET")
    req.add_header("Content-Type", "application/json")
    req.add_header("User-Agent", "telegram-ai-assistant-keycheck/2.0")
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


def api_key() -> str | None:
    return os.getenv("AI_API_KEY") or os.getenv("PROXYAPI_KEY") or os.getenv("OPENROUTER_KEY")


def base_url() -> str:
    return os.getenv("AI_BASE_URL", "https://api.proxyapi.ru/openai/v1").rstrip("/")


def check_models(key: str) -> list[str]:
    print(f"\n[1] Каталог моделей: {base_url()}/models")
    try:
        data = request(f"{base_url()}/models", key)
        ids = [m.get("id") for m in data.get("data", []) if m.get("id")]
        print(f"    ✅ доступно моделей: {len(ids)}")
        return ids
    except RuntimeError as e:
        print(f"    ❌ не удалось получить список: {e}")
        print("    💡 не все OpenAI-совместимые API поддерживают /models — это не критично")
        return []


def suggest(models: list[str], *needles: str) -> None:
    if not models:
        return
    low = [m.lower() for m in models]
    hits = [m for m, l in zip(models, low) if any(n in l for n in needles)]
    if hits:
        print(f"    💡 подходящие модели ({len(hits)}), укажи одну из них в .env:")
        for h in hits[:12]:
            print(f"       {h}")


def check_chat(key: str, models: list[str]) -> None:
    global ok
    model = os.getenv("CHAT_MODEL", "gpt-4o-mini")
    print(f"\n[2] Чат, модель {model}")
    if models and model not in models:
        print("    ⚠️ модели нет в каталоге (может быть алиасом — всё равно пробуем)")
    try:
        r = request(
            f"{base_url()}/chat/completions",
            key,
            {
                "model": model,
                "messages": [{"role": "user", "content": "Ответь одним словом: работает"}],
                "max_tokens": 20,
            },
        )
        answer = r["choices"][0]["message"]["content"]
        print(f"    ✅ ответ: {str(answer).strip()[:80]!r}")
    except RuntimeError as e:
        print(f"    ❌ {e}")
        ok = False
        suggest(models, "gpt", "claude", "gemini", "llama", "mistral", "qwen")


def check_vision(key: str, models: list[str]) -> None:
    print(f"\n[3] Vision, модель {os.getenv('VISION_MODEL', 'gpt-4o-mini')}")
    model = os.getenv("VISION_MODEL", "gpt-4o-mini")
    try:
        r = request(
            f"{base_url()}/chat/completions",
            key,
            {
                "model": model,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "Что на картинке? Ответь коротко."},
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/png;base64,{TINY_PNG_B64}"},
                            },
                        ],
                    }
                ],
                "max_tokens": 30,
            },
        )
        answer = r["choices"][0]["message"]["content"]
        print(f"    ✅ модель приняла изображение, ответ: {str(answer).strip()[:60]!r}")
    except RuntimeError as e:
        print(f"    ❌ {e}")
        ok = False
        suggest(models, "gpt-4o", "gpt-4.1", "claude", "gemini", "vision")


def check_image(key: str) -> None:
    global ok
    mode = os.getenv("IMAGE_API", "images").strip().lower()
    model = os.getenv("IMAGE_MODEL", "dall-e-3")
    size = os.getenv("IMAGE_SIZE", "1024x1024")
    print(f"\n[4] Генерация картинок: режим {mode}, модель {model}, размер {size}")

    if mode == "chat":
        try:
            r = request(
                f"{base_url()}/chat/completions",
                key,
                {
                    "model": model,
                    "messages": [{"role": "user", "content": "A red circle on white background"}],
                    "modalities": ["image", "text"],
                    "max_tokens": 512,
                },
                timeout=180,
            )
            for choice in r.get("choices", []):
                content = choice.get("message", {}).get("content")
                if isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "image_url":
                            url = block["image_url"]["url"]
                            if url.startswith("data:"):
                                print(f"    ✅ картинка получена: {len(base64.b64decode(url.split(',', 1)[1]))} байт")
                            else:
                                print("    ✅ картинка получена: ссылка на файл")
                            return
            print("    ❌ ответ без изображения")
            ok = False
        except RuntimeError as e:
            print(f"    ❌ {e}")
            ok = False
        return

    try:
        r = request(
            f"{base_url()}/images/generations",
            key,
            {"model": model, "prompt": "A red circle on white background", "size": size, "n": 1},
            timeout=180,
        )
        item = (r.get("data") or [{}])[0]
        if item.get("b64_json"):
            print(f"    ✅ картинка получена: {len(base64.b64decode(item['b64_json']))} байт")
        elif item.get("url"):
            print(f"    ✅ картинка получена: {item['url'][:80]}")
        else:
            print(f"    ❌ в ответе нет ни b64_json, ни url. Ключи ответа: {list(r)[:6]}")
            ok = False
    except RuntimeError as e:
        print(f"    ❌ {e}")
        print("    💡 частая причина: у ключа нет доступа к картинкам или закончились кредиты")
        ok = False


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
    parser = argparse.ArgumentParser(description="Проверка ключей и моделей бота")
    parser.add_argument("--skip-image", action="store_true", help="не проверять генерацию картинки (платно)")
    args = parser.parse_args()

    load_env()
    key = api_key()
    if not key:
        print("\n❌ AI_API_KEY не задан в .env")
        sys.exit(2)

    print(f"\n🔑 Ключ: {mask(key)}")
    print(f"🌐 API:  {base_url()}")
    print(
        f"🧠 Модели: чат={os.getenv('CHAT_MODEL', 'gpt-4o-mini')}, "
        f"vision={os.getenv('VISION_MODEL', 'gpt-4o-mini')}, "
        f"речь={os.getenv('TRANSCRIBE_MODEL', 'whisper-1')}"
    )
    print("🎤 Речь: проверяется только реальным голосовым сообщением боту — пропускаю")

    models = check_models(key)
    check_chat(key, models)
    check_vision(key, models)
    if args.skip_image:
        print("\n[4] Генерация картинок: пропущена (--skip-image)")
    else:
        check_image(key)
    check_weather(os.getenv("WEATHER_API_KEY"))

    print("\n" + ("=" * 50))
    print("✅ критичные проверки пройдены" if ok else "❌ есть проблемы — см. ❌ выше")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
