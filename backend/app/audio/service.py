import asyncio
import hashlib
from pathlib import Path

import edge_tts
import httpx

AUDIO_DIR = Path(__file__).resolve().parent.parent / "static" / "audio"
AUDIO_DIR.mkdir(parents=True, exist_ok=True)

VOICES = {
    "vi": "vi-VN-HoaiMyNeural",
    "en": "en-US-JennyNeural",
    "zh": "zh-CN-XiaoxiaoNeural",
    "ja": "ja-JP-NanamiNeural",
    "ko": "ko-KR-SunHiNeural",
}
_TRANSLATE_CODE = {"zh": "zh-CN"}
MAX_CONCURRENT_TTS = 3
_sem = asyncio.Semaphore(MAX_CONCURRENT_TTS)


async def _gtx_translate(text: str, target: str) -> str:
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.post(
            "https://translate.googleapis.com/translate_a/single",
            params={"client": "gtx", "sl": "vi", "tl": target, "dt": "t"},
            data={"q": text},
        )
        r.raise_for_status()
        return "".join(seg[0] for seg in r.json()[0] if seg[0])


_translate_sem = asyncio.Semaphore(2)  # giới hạn đồng thời để tránh bị Google trả 429
TRANSLATE_RETRIES = 3


def _chunks(text: str, max_bytes: int = 450) -> list[str]:
    """MyMemory giới hạn ~500 byte/yêu cầu: tách theo câu."""
    parts, cur = [], ""
    for sent in " ".join(text.splitlines()).split(". "):
        piece = sent if sent.endswith(".") else sent + "."
        if cur and len((cur + " " + piece).encode()) > max_bytes:
            parts.append(cur)
            cur = piece
        else:
            cur = f"{cur} {piece}".strip()
    if cur:
        parts.append(cur)
    return parts


async def _mymemory_translate(text: str, target: str) -> str:
    out = []
    async with httpx.AsyncClient(timeout=20) as client:
        for part in _chunks(text):
            r = await client.get("https://api.mymemory.translated.net/get", params={"q": part, "langpair": f"vi|{target}"})
            r.raise_for_status()
            data = r.json()
            if data.get("responseStatus") != 200:
                raise RuntimeError(f"mymemory {data.get('responseStatus')}")
            out.append(data["responseData"]["translatedText"])
    return " ".join(out)


_LANG_NAMES = {"en": "English", "zh-CN": "Simplified Chinese", "ja": "Japanese", "ko": "Korean"}


async def _gemini_translate(text: str, target: str) -> str:
    from ..config import settings
    if not settings.gemini_api_key:
        raise RuntimeError("no gemini key")
    prompt = (f"Translate the following Vietnamese text into {_LANG_NAMES.get(target, target)}. "
              f"Output only the translation, no notes.\n\n{text}")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{settings.gemini_model}:generateContent",
            headers={"x-goog-api-key": settings.gemini_api_key},
            json={"contents": [{"parts": [{"text": prompt}]}]})
        r.raise_for_status()
        return r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()


async def _provider_chain(text: str, target: str) -> str:
    providers = [
        _gemini_translate,
        _gtx_translate,
        _mymemory_translate,
    ]
    last: Exception | None = None
    for attempt in range(TRANSLATE_RETRIES):
        for prov in providers:
            try:
                res = await prov(text, target)
                if res and res.strip():
                    return res
            except Exception as e:
                last = e
        await asyncio.sleep(1.5 * 2 ** attempt)
    raise last or RuntimeError("translate failed")


async def translate_text(text: str, lang: str) -> str:
    """Cache DB (md5 text|lang) → chuỗi nhà cung cấp miễn phí. Chỉ cache kết quả thành công."""
    if lang == "vi":
        return text
    from ..db import get_db  # tránh import vòng khi chạy test đơn vị

    target = _TRANSLATE_CODE.get(lang, lang)
    key = hashlib.md5(f"{text}|{lang}".encode()).hexdigest()
    db = get_db()
    hit = await db.fetchone("SELECT text FROM translation_cache WHERE cache_key=%s", [key])
    if hit:
        return hit["text"]
    async with _translate_sem:
        out = await _provider_chain(text, target)
    await db.upsert("translation_cache", {"cache_key": key, "lang": lang, "text": out}, ["lang", "text"])
    return out


def cache_path(text: str, lang: str) -> Path:
    key = hashlib.md5(f"{text}:{lang}".encode()).hexdigest()
    return AUDIO_DIR / f"{key}.mp3"


async def synthesize(text: str, lang: str) -> tuple[Path, bool]:
    """Trả về (file mp3, cache_hit). Text đã ở đúng ngôn ngữ."""
    path = cache_path(text, lang)
    if path.exists():
        return path, True
    async with _sem:
        tmp = path.with_suffix(".tmp")
        await edge_tts.Communicate(text, VOICES[lang]).save(str(tmp))
        tmp.replace(path)
    return path, False


def static_url(path: Path) -> str:
    return f"/static/audio/{path.name}"
