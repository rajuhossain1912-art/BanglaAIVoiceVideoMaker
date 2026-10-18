import json
import math
import os
import re
import shutil
import subprocess
import threading
import time
import uuid
import tempfile
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from PIL import Image, ImageDraw, ImageFont, ImageOps

APP_DIR = Path(__file__).resolve().parent
VOICE_CLONE_SPACE = os.getenv("VOICE_CLONE_SPACE", "kawshikbuet17/bengali-cosyvoice3-tts-demo")
VOICE_CLONE_EN_SPACE = os.getenv("VOICE_CLONE_EN_SPACE", "ResembleAI/Chatterbox")
VOICE_CLONE_ENABLED = os.getenv("VOICE_CLONE_ENABLED", "true").lower() in ("1", "true", "yes")
AI_IMAGE_GENERATION_ENABLED = os.getenv("AI_IMAGE_GENERATION_ENABLED", "true").lower() in ("1", "true", "yes")
AI_IMAGE_PROVIDER_ORDER = [x.strip().lower() for x in os.getenv("AI_IMAGE_PROVIDER_ORDER", "pollinations,flux,zimage").split(",") if x.strip()]
AI_IMAGE_PROVIDER_TIMEOUT = max(12, min(45, int(os.getenv("AI_IMAGE_PROVIDER_TIMEOUT", "28"))))
ALLOW_LICENSED_IMAGE_FALLBACK = os.getenv("ALLOW_LICENSED_IMAGE_FALLBACK", "true").lower() in ("1", "true", "yes")
WORK_DIR = Path(os.getenv("WORK_DIR", "/tmp/bangla-video-jobs"))
WORK_DIR.mkdir(parents=True, exist_ok=True)
MAX_SCRIPT_CHARS = int(os.getenv("MAX_SCRIPT_CHARS", "12000"))
MAX_AUDIO_MB = int(os.getenv("MAX_AUDIO_MB", "40"))
JOBS = {}
LOCK = threading.Lock()
app = FastAPI(title="Bangla AI Voice Video Maker API", version="0.2.0")


def run(cmd, timeout=240):
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout, check=False)
    if result.returncode:
        raise RuntimeError(result.stderr.decode("utf-8", "replace")[-1800:] or "Media command failed")
    return result.stdout


def duration_of(path: Path) -> float:
    data = run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(path)], 30)
    try:
        return max(1.0, float(data.decode().strip()))
    except Exception as exc:
        raise RuntimeError("অডিওর দৈর্ঘ্য নির্ণয় করা যায়নি") from exc


def synthesize_mixed_speech(script: str, folder: Path) -> Path:
    """Prefer clearer online Google Translate TTS for Bangla/English; fall back to local eSpeak."""
    tokens = re.findall(r"[\u0980-\u09FF]+|[A-Za-z0-9]+|[^A-Za-z0-9\u0980-\u09FF]+", script[:MAX_SCRIPT_CHARS])
    chunks = []
    current_language = None
    current_text = ""
    for token in tokens:
        if re.search(r"[\u0980-\u09FF]", token):
            language = "bn"
        elif re.search(r"[A-Za-z0-9]", token):
            language = "en"
        else:
            language = current_language or "bn"
        if current_language is not None and language != current_language:
            if current_text.strip():
                chunks.append((current_language, current_text.strip()))
            current_text = ""
        current_language = language
        current_text += token
    if current_text.strip():
        chunks.append((current_language or "bn", current_text.strip()))
    if not chunks:
        raise RuntimeError("পড়ার মতো লেখা পাওয়া যায়নি।")

    # Use free online TTS first; the local fallback is more robotic but works without network.
    audio_parts = []
    provider = "Google TTS"
    try:
        from gtts import gTTS
        for index, (language, text) in enumerate(chunks):
            mp3_part = folder / f"speech-{index:04d}.mp3"
            wav_part = folder / f"speech-{index:04d}.wav"
            gTTS(text=text, lang=language, slow=False, timeout=(5, 18)).save(str(mp3_part))
            run(["ffmpeg", "-y", "-i", str(mp3_part), "-ac", "1", "-ar", "24000", "-c:a", "pcm_s16le", str(wav_part)], 45)
            if not wav_part.exists() or wav_part.stat().st_size < 100:
                raise RuntimeError("Online speech returned an empty audio file")
            audio_parts.append(wav_part)
        print("VOICE_PROVIDER selected=Google TTS", flush=True)
    except Exception as exc:
        print(f"VOICE_PROVIDER fallback=eSpeak-NG error={type(exc).__name__}: {str(exc)[:160]}", flush=True)
        audio_parts = []
        provider = "eSpeak NG"
        for index, (language, text) in enumerate(chunks):
            part = folder / f"speech-{index:04d}.wav"
            try:
                run(["espeak-ng", "-v", language, "-s", "140", "-w", str(part), text], 120)
            except Exception as fallback_exc:
                raise RuntimeError(f"{'বাংলা' if language == 'bn' else 'ইংরেজি'} কণ্ঠ তৈরি করা যায়নি।") from fallback_exc
            if not part.exists() or part.stat().st_size < 100:
                raise RuntimeError("কণ্ঠের অডিও তৈরি হয়নি।")
            audio_parts.append(part)

    if len(audio_parts) == 1:
        return audio_parts[0]
    listing = folder / "audio-parts.txt"
    listing.write_text("".join(f"file '{part.as_posix()}'\n" for part in audio_parts), encoding="utf-8")
    combined = folder / "voice.wav"
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(listing), "-c:a", "pcm_s16le", str(combined)], 120)
    return combined


def _write_gradio_audio_result(audio_result, folder: Path, stem: str):
    """Convert Gradio filepath/URL or (sample_rate, numpy audio) results into a local WAV."""
    if isinstance(audio_result, dict):
        audio_result = audio_result.get("path") or audio_result.get("url") or audio_result.get("audio")
    if isinstance(audio_result, (tuple, list)) and len(audio_result) == 2 and isinstance(audio_result[0], (int, float)):
        try:
            import numpy as np
            import wave
            sample_rate = int(audio_result[0])
            samples = np.asarray(audio_result[1])
            if samples.size == 0 or sample_rate < 8000 or sample_rate > 192000:
                raise ValueError("Invalid remote audio result")
            samples = samples.reshape(-1)
            if np.issubdtype(samples.dtype, np.floating):
                samples = (np.clip(samples, -1.0, 1.0) * 32767.0).astype(np.int16)
            else:
                samples = samples.astype(np.int16)
            wav_path = folder / f"{stem}-raw.wav"
            with wave.open(str(wav_path), "wb") as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(sample_rate)
                wav.writeframes(samples.tobytes())
            return wav_path
        except Exception:
            return None
    if isinstance(audio_result, str) and Path(audio_result).is_file():
        return Path(audio_result)
    if isinstance(audio_result, str) and audio_result.startswith("https://"):
        remote_audio = folder / f"{stem}-remote"
        try:
            with urllib.request.urlopen(urllib.request.Request(audio_result, headers={"User-Agent": "BanglaAIVoiceVideoMaker/0.4"}), timeout=30) as response:
                data = response.read(50 * 1024 * 1024 + 1)
            if 100 < len(data) <= 50 * 1024 * 1024:
                remote_audio.write_bytes(data)
                return remote_audio
        except Exception:
            return None
    return None


def _clone_with_cosyvoice(script: str, normalized: Path):
    from gradio_client import Client, handle_file
    client = Client(VOICE_CLONE_SPACE, verbose=False)
    result = client.predict(
        script,
        handle_file(str(normalized)),
        0,
        1.0,
        api_name="/generate_cross_lingual_audio",
    )
    return result[0] if isinstance(result, (list, tuple)) else result


def _clone_with_chatterbox(script: str, normalized: Path):
    from gradio_client import Client, handle_file
    client = Client(VOICE_CLONE_EN_SPACE, verbose=False)
    # Chatterbox's public demo is English-oriented; do not route Bangla/mixed scripts here.
    result = client.predict(
        script,
        handle_file(str(normalized)),
        0.5,
        0.8,
        0,
        0.5,
        api_name="/generate_tts_audio",
    )
    return result


def synthesize_cloned_voice(script: str, reference_audio: Path, folder: Path) -> Path:
    """Route pure English to Chatterbox and Bangla/mixed scripts to Bengali CosyVoice3."""
    if not VOICE_CLONE_ENABLED:
        raise RuntimeError("নিজের কণ্ঠের পরীক্ষামূলক সুবিধা বর্তমানে বন্ধ আছে।")
    if len(script) > 500:
        raise RuntimeError("পরীক্ষামূলক নিজের কণ্ঠে একবারে সর্বোচ্চ ৫০০ অক্ষর ব্যবহার করুন।")
    normalized = folder / "voice_reference.wav"
    pure_english = bool(re.search(r"[A-Za-z]", script)) and not bool(re.search(r"[\u0980-\u09FF]", script))
    try:
        from gradio_client import handle_file
        run(["ffmpeg", "-y", "-i", str(reference_audio), "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(normalized)], 120)
        if pure_english:
            provider = "Chatterbox"
            try:
                audio_result = _clone_with_chatterbox(script, normalized)
            except Exception as primary_error:
                # One alternate free demo is tried if the English-specific demo is unavailable.
                provider = "CosyVoice3 fallback"
                try:
                    audio_result = _clone_with_cosyvoice(script, normalized)
                except Exception:
                    raise primary_error
        else:
            provider = "Bengali CosyVoice3"
            audio_result = _clone_with_cosyvoice(script, normalized)
        candidate = _write_gradio_audio_result(audio_result, folder, "clone-output")
        if candidate is None:
            raise RuntimeError("The voice service returned no usable audio file")
        output = folder / "cloned_voice.wav"
        run(["ffmpeg", "-y", "-i", str(candidate), "-ac", "1", "-ar", "24000", "-c:a", "pcm_s16le", str(output)], 120)
        if output.exists() and output.stat().st_size > 100:
            print(f"VOICE_PROVIDER selected={provider} language={'en' if pure_english else 'bn_or_mixed'}", flush=True)
            return output
        raise RuntimeError("The voice service returned an empty audio file")
    except Exception as exc:
        print(f"VOICE_PROVIDER failed language={'en' if pure_english else 'bn_or_mixed'} error={type(exc).__name__}: {str(exc)[:250]}", flush=True)
        raise RuntimeError("নিজের কণ্ঠে অডিও তৈরি করা যায়নি। ফ্রি কণ্ঠ-সেবা ব্যস্ত বা পরিবর্তিত হতে পারে। কিছুক্ষণ পর চেষ্টা করুন, অথবা সাধারণ স্বয়ংক্রিয় ভয়েস বেছে নিন।") from exc
    finally:
        normalized.unlink(missing_ok=True)

def load_font(size: int, bold=False):
    candidates = [
        "/usr/share/fonts/truetype/noto/NotoSansBengali-Bold.ttf" if bold else "/usr/share/fonts/truetype/noto/NotoSansBengali-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for candidate in candidates:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size)
    return ImageFont.load_default()


def wrap_text(draw, text, font, max_width):
    words = text.split()
    lines, current = [], ""
    for word in words:
        candidate = word if not current else current + " " + word
        if draw.textbbox((0, 0), candidate, font=font)[2] <= max_width or not current:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


VISUAL_CONCEPTS = [
    (("সাদাছড়ি", "সাদাছড়ি", "দৃষ্টিপ্রতিবন্ধী", "প্রতিবন্ধী", "অন্ধ", "দৃষ্টিহীন"), "a visually impaired person using a white cane in an accessible Bangladeshi setting"),
    (("কর্মসংস্থান", "চাকরি", "নিয়োগ", "নিয়োগ", "কর্মী", "কারখানা", "অফিস"), "Bangladeshi people working in a workplace or factory"),
    (("ব্রেইল", "শিক্ষার্থী", "শিক্ষা", "স্কুল", "কলেজ", "বিশ্ববিদ্যালয়", "বিশ্ববিদ্যালয়", "শিক্ষক", "পড়াশোনা", "পড়াশোনা"), "Bangladeshi students learning in an accessible classroom"),
    (("হাসপাতাল", "চিকিৎসা", "ডাক্তার", "রোগী", "ওষুধ", "স্বাস্থ্য", "ক্লিনিক"), "a doctor consulting a patient in a clean clinic"),
    (("মোবাইল", "ফোন", "ইন্টারনেট", "প্রযুক্তি", "কম্পিউটার", "অ্যাপ", "স্ক্রিন রিডার"), "a person using a smartphone and accessible digital technology"),
    (("পরিবার", "মা", "বাবা", "সন্তান", "সংসার", "বিবাহ", "স্বামী", "স্ত্রী"), "a Bangladeshi family spending time together at home"),
    (("মসজিদ", "নামাজ", "কোরআন", "কুরআন", "রমজান", "ইসলাম"), "a peaceful mosque courtyard in Bangladesh"),
    (("দারিদ্র্য", "গরিব", "দাম", "দ্রব্যমূল্য", "বাজার", "খরচ", "অর্থ"), "a Bangladeshi family budgeting household expenses"),
    (("বাংলাদেশ", "সরকার", "নীতি", "আইন", "নাগরিক", "অধিকার"), "Bangladeshi community and civic life"),
    (("বন্যা", "ঘূর্ণিঝড়", "ঘূর্ণিঝড়", "দুর্যোগ", "জলোচ্ছ্বাস"), "a Bangladeshi village responding to monsoon flooding"),
    (("রাস্তা", "গাড়ি", "গাড়ি", "বাস", "পরিবহন", "চালক", "যাত্রী", "পথচারী"), "a realistic Bangladeshi street with safe public transport"),
    (("শিশু", "বাচ্চা", "ছেলে", "মেয়ে", "মেয়ে", "খেলাধুলা"), "children learning or playing safely outdoors"),
    (("পরিশ্রম", "চেষ্টা", "সাফল্য", "কাজ", "দক্ষতা"), "a person working diligently toward a goal"),
    (("স্বপ্ন", "আশা", "সাহস", "ভবিষ্যৎ", "ভবিষ্যত"), "an inspiring hopeful sunrise over Bangladesh"),
    (("সকাল", "ভোর", "সূর্যোদয়", "সূর্যোদয়"), "sunrise over a peaceful green landscape"),
    (("গাছপালা", "গাছ", "সবুজ", "বন", "প্রকৃতি"), "lush green trees and natural scenery"),
    (("আকাশ", "মেঘ", "নীল আকাশ"), "blue sky with soft white clouds"),
    (("পাখি", "পাখির", "কাক", "চড়ুই", "চড়ুই"), "birds flying among tree branches"),
    (("নদী", "পুকুর", "পানি", "জল"), "a peaceful river and reflective water"),
    (("গ্রাম", "কৃষক", "ধান", "মাঠ"), "a rural Bangladeshi village with green fields"),
    (("বৃষ্টি", "বর্ষা"), "a realistic rainy landscape"),
    (("ফুল", "ফুলের"), "a colorful flower garden"),
    (("সমুদ্র", "সাগর", "সমুদ্রসৈকত"), "ocean waves on a beach"),
]

def _matched_visual_concepts(script: str, limit: int = 2):
    """Choose only the strongest topics present in this scene, avoiding unrelated mixed prompts."""
    text = re.sub(r"\s+", " ", script or "").strip().lower()
    ranked = []
    for order, (terms, prompt) in enumerate(VISUAL_CONCEPTS):
        hits = sum(text.count(term.lower()) for term in terms if term.lower() in text)
        if hits:
            # Specific terms win ties over broad concepts; original order is a stable final tie-breaker.
            specificity = max(len(term) for term in terms if term.lower() in text)
            ranked.append((hits * 10 + min(specificity, 20) / 100 - order / 10000, order, prompt))
    ranked.sort(reverse=True)
    selected = []
    for _, _, prompt in ranked:
        if prompt not in selected:
            selected.append(prompt)
        if len(selected) >= limit:
            break
    return selected

def _image_keywords(script: str):
    """Create a focused image-search query from the dominant topic(s) of one scene."""
    concepts = _matched_visual_concepts(script, limit=2)
    if concepts:
        phrase = " ".join(concepts)
        tokens = re.findall(r"[A-Za-z]{3,}", phrase.lower())
        return list(dict.fromkeys(tokens))[:8]
    # For text without a known Bangla topic, use a few meaningful Latin words if present.
    tokens = re.findall(r"[A-Za-z]{3,}", (script or "")[:500].lower())
    stopwords = {"the", "and", "for", "with", "this", "that", "from", "your", "you", "are", "was", "were", "have", "has", "had", "will", "would", "can", "could", "about", "into", "over", "under", "then", "than", "when", "where", "what", "why", "how", "not", "but", "or", "as", "is", "am", "be"}
    return [word for word in dict.fromkeys(tokens) if word not in stopwords][:8]


def _download_checked_image(image_url: str, folder: Path, filename: str, credit: str):
    if not image_url or not image_url.startswith("https://"):
        return None, ""
    try:
        request = urllib.request.Request(
            image_url,
            headers={"User-Agent": "BanglaAIVoiceVideoMaker/0.4 (free educational video maker)"}
        )
        with urllib.request.urlopen(request, timeout=10) as response:
            content = response.read(8 * 1024 * 1024 + 1)
        if len(content) > 8 * 1024 * 1024:
            return None, ""
        target = folder / filename
        target.write_bytes(content)
        with Image.open(target) as check:
            if check.width < 80 or check.height < 80 or check.width * check.height > 4_000_000:
                raise ValueError("Image dimensions outside safe limits")
            check.verify()
        return target, credit[:180]
    except Exception:
        try:
            (folder / filename).unlink(missing_ok=True)
        except Exception:
            pass
        return None, ""


def find_openverse_image(script: str, folder: Path):
    """Try Openverse's anonymous endpoint; only use CC0, public-domain, CC BY or CC BY-SA results."""
    keywords = _image_keywords(script)
    if not keywords:
        return None, ""
    params = urllib.parse.urlencode({
        "q": " ".join(keywords),
        "license": "cc0,pdm,by,by-sa",
        "page_size": "8",
        "mature": "false",
    })
    try:
        request = urllib.request.Request(
            "https://api.openverse.org/v1/images/?" + params,
            headers={"User-Agent": "BanglaAIVoiceVideoMaker/0.4 (free educational video maker)"}
        )
        with urllib.request.urlopen(request, timeout=6) as response:
            data = json.loads(response.read(1_500_000).decode("utf-8"))
        for item in data.get("results", []):
            license_code = str(item.get("license", "")).lower()
            if license_code not in {"cc0", "pdm", "by", "by-sa"}:
                continue
            image_url = item.get("thumbnail") or item.get("url")
            title = re.sub(r"\s+", " ", str(item.get("title") or "Openverse image")).strip()
            creator = re.sub(r"\s+", " ", str(item.get("creator") or "Unknown creator")).strip()
            if _is_unrelated_map_image(script, title):
                print(f"IMAGE_FILTER rejected=unrelated_map source=openverse title={title[:90]}", flush=True)
                continue
            landing = str(item.get("foreign_landing_url") or "")
            license_url = str(item.get("license_url") or "")
            credit = f"{title[:55]} | {creator[:45]} | {license_code.upper()} {landing[:65]} {license_url[:55]}"
            image, attribution = _download_checked_image(image_url, folder, "openverse-context-image", credit)
            if image:
                return image, attribution
    except Exception:
        pass
    return None, ""


def find_contextual_image(script: str, folder: Path):
    """Try Openverse then Wikimedia Commons; use licensed reusable thumbnails only."""
    image, credit = find_openverse_image(script, folder)
    if image:
        return image, credit
    keywords = _image_keywords(script)
    if not keywords:
        return None, ""
    params = urllib.parse.urlencode({
        "action": "query", "generator": "search",
        "gsrsearch": "filetype:bitmap " + " ".join(keywords),
        "gsrnamespace": "6", "gsrlimit": "8",
        "prop": "imageinfo", "iiprop": "url|extmetadata",
        "iiurlwidth": "900", "format": "json"
    })
    request = urllib.request.Request(
        "https://commons.wikimedia.org/w/api.php?" + params,
        headers={"User-Agent": "BanglaAIVoiceVideoMaker/0.4 (free educational video maker)"}
    )
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            data = json.loads(response.read(2_000_000).decode("utf-8"))
        pages = list((data.get("query", {}).get("pages") or {}).values())
        for page in pages:
            info = (page.get("imageinfo") or [{}])[0]
            metadata = info.get("extmetadata") or {}
            license_name = str((metadata.get("LicenseShortName") or {}).get("value", "")).strip()
            license_upper = license_name.upper().replace("-", " ")
            is_reusable = (
                "PUBLIC DOMAIN" in license_upper or "CC0" in license_upper
                or (license_upper.startswith("CC BY") and "NC" not in license_upper and "ND" not in license_upper)
            )
            image_url = info.get("thumburl") or info.get("url")
            title = str(page.get("title", "Wikimedia Commons image")).replace("File:", "")
            artist = re.sub(r"<[^>]+>", "", str((metadata.get("Artist") or {}).get("value", "")).strip())
            if _is_unrelated_map_image(script, title):
                print(f"IMAGE_FILTER rejected=unrelated_map source=wikimedia title={title[:90]}", flush=True)
                continue
            credit = f"{title[:55]} | {artist[:45]} | {license_name[:20]} https://commons.wikimedia.org/wiki/{urllib.parse.quote(str(page.get('title', '')))}"
            if not is_reusable:
                continue
            image, attribution = _download_checked_image(image_url, folder, "commons-context-image", credit)
            if image:
                return image, attribution
    except Exception:
        pass
    return None, ""


def _compatible_gradio_client():
    """Work around public Spaces exposing valid boolean JSON-schema nodes."""
    from gradio_client import Client, utils
    if not getattr(utils, "_bangla_bool_schema_compat", False):
        original_get_type = utils.get_type
        original_json_schema = utils._json_schema_to_python_type

        def safe_get_type(schema):
            if isinstance(schema, bool) or not isinstance(schema, dict):
                return "Any"
            return original_get_type(schema)

        def safe_json_schema_to_python_type(schema, defs=None):
            if isinstance(schema, bool):
                return "Any" if schema else "None"
            if not isinstance(schema, dict):
                return "Any"
            return original_json_schema(schema, defs)

        utils.get_type = safe_get_type
        utils._json_schema_to_python_type = safe_json_schema_to_python_type
        utils._bangla_bool_schema_compat = True
    return Client


def _extract_generated_image(result):
    if isinstance(result, (list, tuple)) and result:
        result = result[0]
    if isinstance(result, (list, tuple)) and result:
        result = result[0]
    if isinstance(result, dict):
        result = result.get("path") or result.get("url") or result.get("image")
        if isinstance(result, dict):
            result = result.get("path") or result.get("url")
    if isinstance(result, (list, tuple)) and result:
        result = result[0]
    if isinstance(result, dict):
        result = result.get("path") or result.get("url")
    return result


def _is_unrelated_map_image(script: str, image_title: str) -> bool:
    """Reject map/globe search results for technology scenes unless geography is actually discussed."""
    text = re.sub(r"\s+", " ", (script or "").lower())
    title = re.sub(r"\s+", " ", (image_title or "").lower())
    map_terms = ("মানচিত্র", "বিশ্ব মানচিত্র", "ভূগোল", "পৃথিবীর মানচিত্র", "world map", "map of the world", "globe", "atlas", "geographic map", "geography")
    tech_terms = ("মোবাইল", "ফোন", "ইন্টারনেট", "প্রযুক্তি", "কম্পিউটার", "অ্যাপ", "স্ক্রিন রিডার", "টকব্যাক", "smartphone", "screen reader", "talkback", "accessibility", "digital technology", "mobile app")
    explicit_map_context = any(term in text for term in map_terms)
    technology_context = any(term in text for term in tech_terms)
    return technology_context and not explicit_map_context and any(term in title for term in map_terms)


def _english_visual_prompt(script: str):
    """Create a focused prompt and explicitly suppress common off-topic map/globe imagery."""
    concepts = _matched_visual_concepts(script, limit=2)
    if not concepts:
        english_words = re.findall(r"[A-Za-z]{3,}", (script or "")[:500])
        subject = "a realistic educational scene in Bangladesh"
        if english_words:
            subject += " related to " + " ".join(english_words[:8])
        concepts = [subject]
    subject = " and ".join(concepts)
    text = (script or "").lower()
    technology_context = any(term in text for term in (
        "মোবাইল", "ফোন", "ইন্টারনেট", "প্রযুক্তি", "কম্পিউটার", "অ্যাপ", "স্ক্রিন রিডার",
        "টকব্যাক", "smartphone", "screen reader", "talkback", "accessibility", "mobile app"
    ))
    geography_context = any(term in text for term in (
        "মানচিত্র", "বিশ্ব মানচিত্র", "ভূগোল", "পৃথিবীর মানচিত্র", "world map", "globe", "atlas", "geography"
    ))
    if technology_context and not geography_context:
        exclusions = (
            " For a technology or screen-reader scene, show a real person using a smartphone "
            "with an accessibility feature; absolutely do not show a world map, globe, atlas, "
            "geographic map, planet Earth, or abstract global-network visualization."
        )
    else:
        exclusions = (
            " Do not show maps, globes, atlases, or geographic diagrams unless the scene explicitly discusses geography or maps."
        )
    return (
        "One coherent photorealistic vertical 9:16 scene for a Bangladeshi educational video. "
        "Show the main subject clearly: " + subject + ". "
        "Use one central visual idea that matches this scene's message, realistic local details, "
        "natural lighting, clear composition and an uncluttered background. "
        "Do not combine unrelated topics." + exclusions +
        " No text, no captions, no letters, no logos, no watermark."
    )[:1100]


def find_pollinations_image(script: str, folder: Path):
    """Try Pollinations' free no-account classic image endpoint before quota-limited Spaces."""
    prompt = (
        "Create an original photorealistic vertical 9:16 video scene. Subject: "
        + _english_visual_prompt(script)
        + ". Natural realistic lighting, clear subject, no text, no captions, no logos, no watermark."
    )
    params = urllib.parse.urlencode({
        "model": "flux",
        "width": "512",
        "height": "768",
        "seed": str(int(uuid.uuid4().hex[:8], 16)),
        "nologo": "true",
        "private": "true",
        "safe": "true",
    })
    url = "https://image.pollinations.ai/prompt/" + urllib.parse.quote(prompt, safe="") + "?" + params
    target = folder / "pollinations-generated.jpg"
    try:
        request = urllib.request.Request(
            url,
            headers={"User-Agent": "BanglaAIVoiceVideoMaker/0.5 (free educational video maker)"}
        )
        with urllib.request.urlopen(request, timeout=18) as response:
            content = response.read(8 * 1024 * 1024 + 1)
        if not 100 < len(content) <= 8 * 1024 * 1024:
            raise ValueError("Pollinations returned an empty or oversized image")
        target.write_bytes(content)
        with Image.open(target) as check:
            if check.width < 80 or check.height < 80 or check.width * check.height > 4_000_000:
                raise ValueError("Pollinations image dimensions outside safe limits")
            check.verify()
        print("IMAGE_PROVIDER selected=Pollinations-Flux", flush=True)
        return target, "AI-generated with Pollinations | https://pollinations.ai"
    except Exception as exc:
        target.unlink(missing_ok=True)
        print(f"IMAGE_PROVIDER failed provider=Pollinations-Flux error={type(exc).__name__}: {str(exc)[:140]}", flush=True)
        return None, ""


def find_generated_image(script: str, folder: Path):
    """Try free public image-generation Spaces; licensed image search remains a fallback."""
    if not AI_IMAGE_GENERATION_ENABLED:
        return None, ""
    pollinations_image, pollinations_credit = find_pollinations_image(script, folder)
    if pollinations_image:
        return pollinations_image, pollinations_credit
    from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
    prompt = (
        "Create an original, photorealistic vertical 9:16 image for a short educational video. "
        "Scene: " + _english_visual_prompt(script) + ". "
        "Natural realistic lighting, clear subject, visually rich, suitable as a video background. "
        "No text, no captions, no letters, no logos, no watermark, no recognizable copyrighted characters."
    )
    providers = [
        (
            "FLUX.1-schnell",
            "black-forest-labs/FLUX.1-schnell",
            lambda client: client.predict(
                prompt=prompt, seed=42, randomize_seed=False,
                width=512, height=768, num_inference_steps=4, api_name="/infer"
            ),
        ),
        (
            "Z-Image-Turbo",
            "Tongyi-MAI/Z-Image-Turbo",
            lambda client: client.predict(
                prompt, "720x1280 ( 9:16 )", 42, 7, 3.0, False, None,
                api_name="/generate"
            ),
        ),
    ]
    provider_aliases = {
        "flux": "FLUX.1-schnell",
        "zimage": "Z-Image-Turbo",
    }
    configured_names = [provider_aliases.get(alias, alias) for alias in AI_IMAGE_PROVIDER_ORDER]
    ordered_providers = []
    for wanted in configured_names:
        for provider in providers:
            if provider[0].lower() == wanted.lower() and provider not in ordered_providers:
                ordered_providers.append(provider)
    for provider in providers:
        if provider not in ordered_providers:
            ordered_providers.append(provider)
    for provider_name, space_id, call in ordered_providers:
        executor = ThreadPoolExecutor(max_workers=1)
        try:
            print(f"IMAGE_PROVIDER trying={provider_name} timeout={AI_IMAGE_PROVIDER_TIMEOUT}s", flush=True)
            future = executor.submit(lambda sid=space_id, fn=call: fn(_compatible_gradio_client()(sid, verbose=False)))
            result = future.result(timeout=AI_IMAGE_PROVIDER_TIMEOUT)
            image_result = _extract_generated_image(result)
            if isinstance(image_result, str) and Path(image_result).is_file():
                target = folder / f"generated-{provider_name.lower().replace('.', '').replace('-', '-')}.png"
                shutil.copyfile(image_result, target)
                with Image.open(target) as check:
                    if check.width < 80 or check.height < 80 or check.width * check.height > 4_000_000:
                        raise ValueError("Generated image dimensions outside safe limits")
                    check.verify()
                print(f"IMAGE_PROVIDER selected={provider_name}", flush=True)
                return target, f"AI-generated with {provider_name} | https://huggingface.co/spaces/{space_id}"
            if isinstance(image_result, str) and image_result.startswith("https://"):
                target, credit = _download_checked_image(
                    image_result, folder, f"generated-{provider_name.lower().replace('.', '')}.png",
                    f"AI-generated with {provider_name} | https://huggingface.co/spaces/{space_id}"
                )
                if target:
                    print(f"IMAGE_PROVIDER selected={provider_name}", flush=True)
                    return target, credit
            print(f"IMAGE_PROVIDER no_image provider={provider_name}", flush=True)
        except FutureTimeout:
            print(f"IMAGE_PROVIDER timeout provider={provider_name}", flush=True)
        except Exception as exc:
            print(f"IMAGE_PROVIDER failed provider={provider_name} error={type(exc).__name__}: {str(exc)[:180]}", flush=True)
        finally:
            executor.shutdown(wait=False, cancel_futures=True)
    return None, ""

def make_background(script: str, folder: Path):
    # Small canvas is intentional: keep peak memory below Render Free's 512 MiB limit.
    width, height = 360, 640
    # Use small Wikimedia Commons thumbnails with a strict pixel limit; fall back to graphics if unavailable.
    # Prefer a scene-matched AI image; use licensed image search only if generation is unavailable.
    source_image, credit = find_generated_image(script, folder)
    if not source_image and ALLOW_LICENSED_IMAGE_FALLBACK:
        source_image, credit = find_contextual_image(script, folder)
    elif not source_image:
        print("IMAGE_PROVIDER all_ai_models_failed licensed_fallback=disabled", flush=True)
    if source_image:
        try:
            with Image.open(source_image) as source:
                image = ImageOps.fit(source.convert("RGB"), (width, height), method=Image.Resampling.BILINEAR)
            # Keep real photos bright enough to recognize behind captions.
            overlay = Image.new("RGBA", (width, height), (3, 13, 28, 72))
            image = Image.alpha_composite(image.convert("RGBA"), overlay).convert("RGB")
        except Exception:
            source_image = None
    if not source_image:
        image = Image.new("RGB", (width, height))
        draw = ImageDraw.Draw(image)
        # Draw horizontal bands instead of allocating a Python tuple for every pixel.
        for y in range(0, height, 8):
            ratio = y / height
            color = (int(13 + 22 * ratio), int(29 + 18 * ratio), int(63 + 42 * ratio))
            draw.rectangle((0, y, width, min(height, y + 7)), fill=color)
        draw.ellipse((235, -65, 450, 150), fill=(30, 69, 113))
        draw.ellipse((-100, 440, 165, 705), fill=(23, 57, 91))
    draw = ImageDraw.Draw(image)
    title_font = load_font(24, True)
    body_font = load_font(17)
    title = "বাংলা AI ভিডিও"
    title_lines = wrap_text(draw, title, title_font, 300)
    y = 75
    for line in title_lines:
        box = draw.textbbox((0, 0), line, font=title_font)
        draw.text(((width - (box[2] - box[0])) / 2, y), line, font=title_font, fill=(255, 255, 255), stroke_width=1, stroke_fill=(0, 0, 0))
        y += 33
    draw.rounded_rectangle((30, 150, 330, 153), radius=2, fill=(83, 177, 244))
    excerpt = re.sub(r"\s+", " ", script).strip()
    if not source_image:
        lines = wrap_text(draw, excerpt[:300], body_font, 295)
        y = 185
        for line in lines[:10]:
            draw.text((33, y), line, font=body_font, fill=(255, 255, 255), stroke_width=1, stroke_fill=(0, 0, 0))
            y += 27
    draw.text((33, 580), "Bangla AI Voice Video Maker", font=load_font(11), fill=(240, 245, 255), stroke_width=1, stroke_fill=(0, 0, 0))
    if credit:
        credit_font = load_font(6)
        credit_lines = wrap_text(draw, "Image credit: " + credit, credit_font, 340)
        for index, line in enumerate(credit_lines[:2]):
            draw.text((10, 605 + index * 9), line, font=credit_font, fill=(255, 255, 255), stroke_width=1, stroke_fill=(0, 0, 0))
    target = folder / "background.png"
    image.save(target, optimize=True)
    return target

def _split_script_into_scenes(script: str, max_scenes: int = 12, target_words: int = 45):
    """Plan topic-sized scenes from sentence/paragraph boundaries, capped for Render Free resources."""
    text = (script or "").strip()
    if not text:
        return ["বাংলা ভিডিও"]

    paragraphs = [part.strip() for part in re.split(r"\n\s*\n+", text) if part.strip()]
    if not paragraphs:
        paragraphs = [text]

    chunks = []
    for paragraph in paragraphs:
        sentences = [part.strip() for part in re.split(r"(?<=[.!?।;])\s+", paragraph) if part.strip()]
        if not sentences:
            sentences = [paragraph]
        current = []
        for sentence in sentences:
            words = sentence.split()
            while words:
                room = target_words - len(current)
                if room <= 0:
                    chunks.append(" ".join(current))
                    current = []
                    room = target_words
                current.extend(words[:room])
                words = words[room:]
                if len(current) >= target_words:
                    chunks.append(" ".join(current))
                    current = []
        if current:
            chunks.append(" ".join(current))

    if not chunks:
        chunks = [text]
    if len(chunks) > max_scenes:
        # Preserve scene order and neighboring context while keeping the number of expensive
        # image-generation attempts bounded on Render Free.
        all_words = [chunk.split() for chunk in chunks]
        total_words = sum(len(words) for words in all_words)
        target_size = max(1, (total_words + max_scenes - 1) // max_scenes)
        merged = []
        current = []
        remaining_scenes = max_scenes
        remaining_words = total_words
        for index, words in enumerate(all_words):
            current.extend(words)
            remaining_words -= len(words)
            should_close = (
                len(merged) < max_scenes - 1
                and len(current) >= target_size
                and (remaining_words > 0)
            )
            if should_close:
                merged.append(" ".join(current))
                current = []
                remaining_scenes -= 1
                target_size = max(1, (remaining_words + remaining_scenes - 1) // remaining_scenes)
        if current:
            merged.append(" ".join(current))
        chunks = merged[:max_scenes]
    return chunks or [text]


def make_scene_backgrounds(script: str, folder: Path):
    """Create a bounded set of semantically focused images for reuse across timed scene changes."""
    scenes = _split_script_into_scenes(script, max_scenes=12, target_words=32)
    backgrounds = []
    for index, scene_text in enumerate(scenes):
        scene_dir = folder / f"scene-{index:02d}"
        scene_dir.mkdir(parents=True, exist_ok=True)
        print(f"IMAGE_SCENE index={index + 1}/{len(scenes)} words={len(scene_text.split())}", flush=True)
        backgrounds.append(make_background(scene_text, scene_dir))
    return backgrounds, scenes

def make_srt(script: str, duration: float, path: Path):
    # Estimated sentence timing is a fallback, not forced alignment.
    sentences = [x.strip() for x in re.split(r"(?<=[.!?।])\s+|\n+", script) if x.strip()]
    if not sentences:
        sentences = [script.strip()]
    weights = [max(1, len(re.findall(r"\S+", s))) for s in sentences]
    total = sum(weights)
    cursor = 0.0

    def stamp(seconds):
        ms = max(0, int(seconds * 1000))
        h, ms = divmod(ms, 3600000)
        m, ms = divmod(ms, 60000)
        s, ms = divmod(ms, 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    lines = []
    for i, (sentence, weight) in enumerate(zip(sentences, weights), start=1):
        end = duration if i == len(sentences) else cursor + duration * weight / total
        lines += [str(i), f"{stamp(cursor)} --> {stamp(end)}", sentence, ""]
        cursor = end
    path.write_text("\n".join(lines), encoding="utf-8")


def make_ass(script: str, duration: float, path: Path, caption_offset: float = 0.0):
    """Create approximate word-by-word karaoke captions; timings are estimated."""
    sentences = [x.strip() for x in re.split(r"(?<=[.!?।])\s+|\n+", script) if x.strip()]
    if not sentences:
        sentences = [script.strip()]
    weights = [max(1, len(re.findall(r"\S+", sentence))) for sentence in sentences]
    total_weight = sum(weights)
    cursor = 0.0
    lines = [
        "[Script Info]",
        "ScriptType: v4.00+",
        "PlayResX: 360",
        "PlayResY: 640",
        "WrapStyle: 2",
        "ScaledBorderAndShadow: yes",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        "Style: Default,Noto Sans Bengali,21,&H00FFFFFF,&H0000FFFF,&H00101010,&H80000000,0,0,0,0,100,100,0,0,1,2,1,2,24,24,46,1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]

    def stamp(seconds):
        centiseconds = max(0, int(seconds * 100))
        hours, centiseconds = divmod(centiseconds, 360000)
        minutes, centiseconds = divmod(centiseconds, 6000)
        whole_seconds, centiseconds = divmod(centiseconds, 100)
        return f"{hours}:{minutes:02d}:{whole_seconds:02d}.{centiseconds:02d}"

    for index, (sentence, weight) in enumerate(zip(sentences, weights)):
        raw_start = cursor
        raw_end = duration if index == len(sentences) - 1 else cursor + duration * weight / total_weight
        start = min(duration, max(0.0, raw_start + caption_offset))
        end = min(duration, max(start + 0.05, raw_end + caption_offset))
        words = re.findall(r"\S+", sentence)
        if not words:
            cursor = raw_end
            continue
        lengths = [max(1, len(word)) for word in words]
        available_cs = max(len(words), int(max(0.01, end - start) * 100))
        length_total = sum(lengths)
        karaoke = []
        allocated = 0
        for index, (word, length) in enumerate(zip(words, lengths)):
            if index == len(words) - 1:
                cs = max(1, available_cs - allocated)
            else:
                cs = max(1, int(available_cs * length / length_total))
                allocated += cs
            safe_word = word.replace("\\", "＼").replace("{", "｛").replace("}", "｝")
            karaoke.append(f"{{\\k{cs}}}{safe_word}")
        text = " ".join(karaoke)
        lines.append(f"Dialogue: 0,{stamp(start)},{stamp(end)},Default,,0,0,0,,{text}")
        cursor = raw_end
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")



def sentence_timing_spans(audio_path: Optional[Path], sentences, duration: float):
    """Use real audio silence boundaries to improve automatic sentence timing; fall back safely."""
    weights = [max(1, len(re.findall(r"\S+", sentence))) for sentence in sentences]
    total = sum(weights) or 1
    expected = [0.0]
    running = 0
    for weight in weights[:-1]:
        running += weight
        expected.append(duration * running / total)
    expected.append(duration)
    if audio_path is None or len(sentences) < 2:
        return list(zip(expected[:-1], expected[1:]))
    try:
        result = subprocess.run(
            ["ffmpeg", "-hide_banner", "-nostats", "-i", str(audio_path),
             "-af", "silencedetect=noise=-32dB:d=0.18", "-f", "null", "-"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=20, check=False
        )
        log = result.stderr.decode("utf-8", "replace")
        silence_starts = [float(x) for x in re.findall(r"silence_start: ([0-9.]+)", log)]
        silence_ends = [float(x) for x in re.findall(r"silence_end: ([0-9.]+)", log)]
        candidates = []
        for i, start in enumerate(silence_starts):
            end = silence_ends[i] if i < len(silence_ends) else start
            if end - start >= 0.16:
                middle = (start + end) / 2.0
                if 0.08 < middle < duration - 0.08:
                    candidates.append(middle)
        chosen = [0.0]
        for target in expected[1:-1]:
            available = [x for x in candidates if x > chosen[-1] + 0.08 and x < duration - 0.08]
            if available:
                nearest = min(available, key=lambda x: abs(x - target))
                if abs(nearest - target) <= max(1.5, duration * 0.22):
                    chosen.append(nearest)
                    candidates.remove(nearest)
                    continue
            chosen.append(target)
        chosen.append(duration)
        chosen = [max(0.0, min(duration, x)) for x in chosen]
        if all(chosen[i + 1] > chosen[i] + 0.05 for i in range(len(chosen) - 1)):
            print(f"CAPTION_ALIGNMENT method=audio_silence sentences={len(sentences)}", flush=True)
            return list(zip(chosen[:-1], chosen[1:]))
    except Exception as exc:
        print(f"CAPTION_ALIGNMENT fallback=estimated error={type(exc).__name__}", flush=True)
    return list(zip(expected[:-1], expected[1:]))


def make_caption_frames(script: str, duration: float, background: Path, folder: Path, caption_offset: float = 0.0, audio_path: Optional[Path] = None, job_id: Optional[str] = None, scene_interval: int = 5, visual_scene_texts=None):
    """Render small Pillow caption cards with per-word highlighting, avoiding FFmpeg's memory-heavy libass filter."""
    frame_dir = folder / "caption-frames"
    frame_dir.mkdir(parents=True, exist_ok=True)
    background_paths = background if isinstance(background, (list, tuple)) else [background]
    bases = []
    for background_path in background_paths:
        with Image.open(background_path) as source:
            bases.append(source.convert("RGB").resize((180, 320), Image.Resampling.BILINEAR))

    sentences = _split_script_into_scenes(script)
    sentence_words = [re.findall(r"\S+", sentence) for sentence in sentences]
    total_words = max(1, sum(len(words) for words in sentence_words))
    sentence_spans = sentence_timing_spans(audio_path, sentences, duration)
    # The chosen interval controls visual changes. To stay within Render Free memory/time limits,
    # generate at most twelve unique semantic images, then choose the closest matching image for
    # each timed text segment rather than making dozens of expensive remote image requests.
    interval = scene_interval if scene_interval in (3, 5, 10, 15, 20) else 5
    slot_count = max(1, int(math.ceil(duration / interval)))
    all_words = re.findall(r"\S+", script or "")
    words_per_slot = max(1, int(math.ceil(len(all_words) / slot_count)))
    slot_texts = [" ".join(all_words[i:i + words_per_slot]) for i in range(0, len(all_words), words_per_slot)]
    scene_texts = list(visual_scene_texts or sentences)
    scene_concepts = [_matched_visual_concepts(x, limit=3) for x in scene_texts]
    slot_backgrounds = []
    for slot_index in range(slot_count):
        slot_text = slot_texts[min(slot_index, len(slot_texts) - 1)] if slot_texts else script
        concepts = _matched_visual_concepts(slot_text, limit=3)
        scores = [sum(1 for concept in concepts if concept in candidates) for candidates in scene_concepts]
        if scores and max(scores) > 0:
            best = max(scores)
            choices = [i for i, score in enumerate(scores) if score == best]
            slot_backgrounds.append(choices[slot_index % len(choices)])
        else:
            slot_backgrounds.append(slot_index % max(1, len(bases)))
    print(f"VISUAL_TIMELINE interval_seconds={interval} slots={slot_count} unique_images={len(bases)}", flush=True)
    safe_offset = max(-max(0.0, duration - 0.1), min(max(0.0, duration - 0.1), caption_offset))
    font = load_font(13, True)
    entries = []
    image_index = 0
    blank_path = frame_dir / "timing-gap.png"
    bases[0].save(blank_path, optimize=True)
    if safe_offset > 0:
        entries.append((blank_path, safe_offset))

    cursor = 0.0
    for sentence_index, (sentence, words, span) in enumerate(zip(sentences, sentence_words, sentence_spans)):
        if not words:
            continue
        raw_start, raw_end = span
        sentence_start = max(0.0, raw_start + safe_offset)
        sentence_end = max(sentence_start + 0.05, min(duration, raw_end + safe_offset))
        sentence_duration = max(0.05, sentence_end - sentence_start)
        word_weights = [max(1, len(re.sub(r"[^\w\u0980-\u09FF]", "", word))) for word in words]
        word_total = sum(word_weights) or 1
        cursor = sentence_start
        for word_index, (word, word_weight) in enumerate(zip(words, word_weights)):
            start = cursor
            word_duration = sentence_duration * word_weight / word_total
            end = sentence_end if word_index == len(words) - 1 else min(sentence_end, cursor + word_duration)
            slot_index = min(slot_count - 1, max(0, int(start / interval)))
            base = bases[slot_backgrounds[slot_index] % len(bases)]
            # Smooth Ken Burns motion: zoom in toward the sentence midpoint, then ease out.
            # Progress is sentence-local so movement remains visible even for short captions.
            phase = (word_index + 0.5) / max(1, len(words))
            zoom = 1.0 + 0.10 * (1.0 - abs(phase * 2.0 - 1.0))
            crop_width = max(1, int(base.width / zoom))
            crop_height = max(1, int(base.height / zoom))
            travel_x = max(0, base.width - crop_width)
            travel_y = max(0, base.height - crop_height)
            left_crop = int(travel_x * phase)
            top_crop = int(travel_y * (1.0 - phase))
            left_crop = min(travel_x, max(0, left_crop))
            top_crop = min(travel_y, max(0, top_crop))
            frame = base.crop((left_crop, top_crop, left_crop + crop_width, top_crop + crop_height)).resize(base.size, Image.Resampling.BILINEAR)
            overlay = Image.new("RGBA", frame.size, (0, 0, 0, 0))
            panel = ImageDraw.Draw(overlay)
            panel.rounded_rectangle((7, 220, 173, 311), radius=9, fill=(0, 0, 0, 205), outline=(95, 170, 230, 220), width=1)
            frame = Image.alpha_composite(frame.convert("RGBA"), overlay)
            draw = ImageDraw.Draw(frame)
            # Keep the current word and nearby context visible, even for long sentences.
            left = max(0, word_index - 7)
            right = min(len(words), left + 14)
            left = max(0, right - 14)
            shown = words[left:right]
            active_local = word_index - left
            lines = []
            current_line = []
            current_width = 0
            max_width = 150
            for wi, token in enumerate(shown):
                token_width = draw.textbbox((0, 0), token, font=font)[2]
                needed = token_width + (draw.textbbox((0, 0), " ", font=font)[2] if current_line else 0)
                if current_line and current_width + needed > max_width:
                    lines.append(current_line)
                    current_line = []
                    current_width = 0
                    needed = token_width
                current_line.append((token, wi == active_local))
                current_width += needed
            if current_line:
                lines.append(current_line)
            visible_lines = lines[-4:]
            y = 232 + max(0, (4 - len(visible_lines)) * 17)
            for line in visible_lines:
                x = 14
                for token, active in line:
                    color = (255, 224, 65) if active else (255, 255, 255)
                    draw.text((x, y), token, font=font, fill=color, stroke_width=1, stroke_fill=(0, 0, 0))
                    x += draw.textbbox((0, 0), token, font=font)[2] + draw.textbbox((0, 0), " ", font=font)[2]
                y += 17
            path = frame_dir / f"frame-{image_index:06d}.png"
            frame.convert("RGB").save(path, compress_level=1)
            entries.append((path, max(0.05, end - start)))
            image_index += 1
            cursor = end
            if job_id and (image_index % 20 == 0 or image_index >= total_words):
                with LOCK:
                    if job_id in JOBS and JOBS[job_id].get("status") == "processing":
                        JOBS[job_id]["progress"] = 40 + min(9, int(9 * image_index / total_words))
                        JOBS[job_id]["message"] = f"সাবটাইটেল ও শব্দের হাইলাইট তৈরি হচ্ছে: {image_index}/{total_words}"

    last_end = sum(seconds for _, seconds in entries)
    if last_end < duration:
        entries.append((blank_path, max(0.05, duration - last_end)))
    if not entries:
        path = frame_dir / "frame-000000.png"
        base.save(path, optimize=True)
        entries.append((path, max(0.1, duration)))
    listing = folder / "caption-frames.txt"
    lines = []
    for path, seconds in entries:
        lines.append(f"file '{path.as_posix()}'\n")
        lines.append(f"duration {seconds:.4f}\n")
    # concat demuxer needs the last image repeated so its final duration is honored.
    lines.append(f"file '{entries[-1][0].as_posix()}'\n")
    listing.write_text("".join(lines), encoding="utf-8")
    return listing, image_index

def render(job_id: str, script: str, mode: str, audio_path: Optional[Path], caption_offset: float = 0.0, scene_interval: int = 5):
    folder = WORK_DIR / job_id
    folder.mkdir(parents=True, exist_ok=True)
    uploaded_audio_path = audio_path
    try:
        with LOCK:
            JOBS[job_id]["status"] = "processing"
            JOBS[job_id]["progress"] = 10
            JOBS[job_id]["message"] = "ভয়েস ও দৃশ্য প্রস্তুত করা হচ্ছে"
        if mode == "clone":
            reference_audio = audio_path
            if reference_audio is None:
                raise RuntimeError("নিজের কণ্ঠের নমুনা অডিও নির্বাচন করুন।")
            try:
                audio_path = synthesize_cloned_voice(script, reference_audio, folder)
            finally:
                try:
                    reference_audio.unlink(missing_ok=True)
                except Exception:
                    pass
        elif audio_path is None:
            audio_path = synthesize_mixed_speech(script[:MAX_SCRIPT_CHARS], folder)
        duration = duration_of(audio_path)
        with LOCK:
            JOBS[job_id]["progress"] = 35
            JOBS[job_id]["message"] = "ভিডিওর পটভূমি ও সাবটাইটেল তৈরি হচ্ছে"
        print(f"VIDEO_STAGE job={job_id} stage=background_start", flush=True)
        backgrounds, visual_scene_texts = make_scene_backgrounds(script, folder)
        print(f"VIDEO_STAGE job={job_id} stage=background_done scenes={len(backgrounds)} interval={scene_interval}s providers=openverse,wikimedia,graphic_fallback", flush=True)
        with LOCK:
            JOBS[job_id]["progress"] = 40
            JOBS[job_id]["message"] = "বাক্যভিত্তিক দৃশ্য ও পটভূমি তৈরি হয়েছে"
        print(f"VIDEO_STAGE job={job_id} stage=subtitles_start", flush=True)
        frame_list, frame_count = make_caption_frames(script, duration, backgrounds, folder, caption_offset, audio_path, job_id, scene_interval, visual_scene_texts)
        print(f"VIDEO_STAGE job={job_id} stage=subtitles_done frames={frame_count} method=pillow_word_highlight", flush=True)
        with LOCK:
            JOBS[job_id]["progress"] = 45
            JOBS[job_id]["message"] = "শব্দের সঙ্গে মিলিয়ে সাবটাইটেল তৈরি হয়েছে"
        output = folder / "video.mp4"
        # Pre-rendered caption images avoid FFmpeg/libass memory spikes on Render Free.
        vf = "scale=180:320,format=yuv420p"
        print(f"VIDEO_STAGE job={job_id} stage=ffmpeg_start duration={duration:.2f} size=180x320 fps=5 subtitles=pillow_word_highlight frames={frame_count}", flush=True)
        with LOCK:
            JOBS[job_id]["progress"] = 50
            JOBS[job_id]["message"] = "সাবটাইটেলসহ ভিডিও রেন্ডার হচ্ছে"
        run([
            "ffmpeg", "-y", "-filter_threads", "1", "-filter_complex_threads", "1",
            "-f", "concat", "-safe", "0", "-i", str(frame_list), "-i", str(audio_path),
            "-map", "0:v:0", "-map", "1:a:0", "-vf", vf, "-t", str(duration), "-r", "5",
            "-c:v", "libx264", "-threads", "1", "-preset", "ultrafast", "-crf", "32",
            "-c:a", "aac", "-b:a", "48k", "-threads", "1", "-shortest", "-movflags", "+faststart", str(output)
        ], 240)
        print(f"VIDEO_STAGE job={job_id} stage=ffmpeg_done", flush=True)
        with LOCK:
            JOBS[job_id].update(status="completed", progress=100, message="ভিডিও তৈরি হয়েছে", download_url=f"/api/jobs/{job_id}/download", duration=round(duration, 2), completed_at=time.time())
    except Exception as exc:
        print(f"VIDEO_STAGE job={job_id} stage=failed error={type(exc).__name__}: {str(exc)[:500]}", flush=True)
        with LOCK:
            JOBS[job_id].update(status="failed", progress=100, message=str(exc)[:1000], completed_at=time.time())
    finally:
        # Remove uploaded reference/narration audio after rendering, including failed jobs.
        if uploaded_audio_path is not None:
            try:
                uploaded_audio_path.unlink(missing_ok=True)
            except Exception:
                pass


@app.get("/")
def root():
    return {"name": "Bangla AI Voice Video Maker API", "status": "ok", "docs": "/docs"}


@app.get("/health")
def health():
    tools = {name: shutil.which(name) is not None for name in ("ffmpeg", "ffprobe", "espeak-ng")}
    return {
        "status": "ok" if all(tools.values()) else "degraded",
        "tools": tools,
        "version": os.getenv("API_VERSION", "0.3.0"),
        "git_commit": os.getenv("RENDER_GIT_COMMIT", "unknown"),
        "git_branch": os.getenv("RENDER_GIT_BRANCH", "unknown"),
    }


@app.get("/api/version")
def api_version():
    """Expose deployed source identity so the live server can be matched to GitHub history."""
    return {
        "name": "Bangla AI Voice Video Maker API",
        "version": os.getenv("API_VERSION", "0.3.0"),
        "git_commit": os.getenv("RENDER_GIT_COMMIT", "unknown"),
        "git_branch": os.getenv("RENDER_GIT_BRANCH", "unknown"),
        "service_id": os.getenv("RENDER_SERVICE_ID", "unknown"),
        "deploy_id": os.getenv("RENDER_DEPLOY_ID", "unknown"),
        "checked_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "free_only": True,
    }


@app.get("/api/capabilities")
def capabilities():
    return {
        "language_input": ["বাংলা", "English", "Banglish"],
        "video_generation": True,
        "scene_interval_seconds": [3, 5, 10, 15, 20],
        "scene_interval_default_seconds": 5,
        "scene_images": {
            "enabled": AI_IMAGE_GENERATION_ENABLED,
            "providers": [
                {"id": "flux", "name": "FLUX.1-schnell", "license": "Apache-2.0 model license; generated output is not guaranteed copyright-free"},
                {"id": "zimage", "name": "Z-Image-Turbo", "license": "Apache-2.0 model license; generated output is not guaranteed copyright-free"},
                {"id": "pollinations_flux", "name": "Pollinations Flux (free classic endpoint)", "license": "Hosted image service; free anonymous access and rate limits may change"},
            ],
            "order": AI_IMAGE_PROVIDER_ORDER,
            "timeout_seconds": AI_IMAGE_PROVIDER_TIMEOUT,
            "automatic_fallback": True,
            "licensed_image_fallback": ALLOW_LICENSED_IMAGE_FALLBACK,
        },
        "script_generation": {"available": False, "note": "Current API creates a video from supplied script; a reliable free AI script-generation provider is not integrated yet."},
        "free_only": True,
    }


@app.post("/api/jobs", status_code=202)
async def create_job(script: str = Form(...), mode: str = Form("auto"), audio: Optional[UploadFile] = File(None), voice_clone_consent: bool = Form(False), caption_offset: float = Form(0.0), scene_interval: int = Form(5)):
    script = script.strip()
    if not script:
        raise HTTPException(400, "আগে বাংলা বা ইংরেজি লেখা যোগ করুন।")
    if len(script) > MAX_SCRIPT_CHARS:
        raise HTTPException(413, f"লেখা সর্বোচ্চ {MAX_SCRIPT_CHARS} অক্ষরের হতে পারবে।")
    if mode not in ("auto", "audio", "clone"):
        raise HTTPException(400, "ভিডিও তৈরির পদ্ধতি সঠিক নয়।")
    if not -1.5 <= caption_offset <= 1.5:
        raise HTTPException(400, "সাবটাইটেলের সময় -১.৫ থেকে +১.৫ সেকেন্ডের মধ্যে দিন।")
    if scene_interval not in (3, 5, 10, 15, 20):
        raise HTTPException(400, "ছবি পরিবর্তনের বিরতি ৩, ৫, ১০, ১৫ অথবা ২০ সেকেন্ড হতে হবে।")
    if mode in ("audio", "clone") and audio is None:
        raise HTTPException(400, "অডিও ফাইল নির্বাচন করুন।")
    if mode == "clone":
        if not VOICE_CLONE_ENABLED:
            raise HTTPException(503, "নিজের কণ্ঠের পরীক্ষামূলক সুবিধা বর্তমানে বন্ধ আছে।")
        if not voice_clone_consent:
            raise HTTPException(400, "বাহ্যিক Hugging Face ডেমোতে কণ্ঠের নমুনা পাঠানোর অনুমতি প্রয়োজন।")
        if len(script) > 500:
            raise HTTPException(413, "পরীক্ষামূলক নিজের কণ্ঠে একবারে সর্বোচ্চ ৫০০ অক্ষর ব্যবহার করুন।")
    job_id = uuid.uuid4().hex
    folder = WORK_DIR / job_id
    folder.mkdir(parents=True, exist_ok=True)
    audio_path = None
    if audio is not None:
        audio_path = folder / "input_audio"
        total = 0
        with audio.file as source, audio_path.open("wb") as target:
            while True:
                chunk = source.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_AUDIO_MB * 1024 * 1024:
                    shutil.rmtree(folder, ignore_errors=True)
                    raise HTTPException(413, f"অডিও ফাইল সর্বোচ্চ {MAX_AUDIO_MB} MB হতে পারবে।")
                target.write(chunk)
    with LOCK:
        JOBS[job_id] = {"id": job_id, "status": "queued", "progress": 0, "message": "অনুরোধ গ্রহণ করা হয়েছে", "created_at": time.time()}
    threading.Thread(target=render, args=(job_id, script, mode, audio_path, caption_offset, scene_interval), daemon=True).start()
    return {"id": job_id, "status": "queued", "status_url": f"/api/jobs/{job_id}", "download_url": f"/api/jobs/{job_id}/download"}


@app.get("/api/jobs/{job_id}")
def job_status(job_id: str):
    with LOCK:
        job = JOBS.get(job_id)
        if not job:
            raise HTTPException(404, "কাজটি পাওয়া যায়নি। সার্ভার পুনরায় চালু হলে অস্থায়ী কাজের তথ্য মুছে যেতে পারে।")
        return dict(job)


@app.get("/api/jobs/{job_id}/download")
def download_video(job_id: str):
    with LOCK:
        job = JOBS.get(job_id)
    if not job:
        raise HTTPException(404, "ভিডিওর কাজটি পাওয়া যায়নি।")
    if job["status"] != "completed":
        raise HTTPException(409, "ভিডিও এখনো তৈরি হয়নি।")
    output = WORK_DIR / job_id / "video.mp4"
    if not output.exists():
        raise HTTPException(404, "ভিডিও ফাইলটি আর পাওয়া যাচ্ছে না।")
    return FileResponse(output, media_type="video/mp4", filename="bangla-ai-video.mp4")
