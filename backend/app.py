import json
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
    """Synthesize contiguous Bangla/English spans with matching eSpeak voices."""
    tokens = re.findall(r"[\u0980-\u09FF]{3,}|[A-Za-z]{3,}", script[:900])
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
                chunks.append((current_language, current_text))
            current_text = ""
        current_language = language
        current_text += token
    if current_text.strip():
        chunks.append((current_language or "bn", current_text))
    if not chunks:
        raise RuntimeError("পড়ার মতো লেখা পাওয়া যায়নি।")

    audio_parts = []
    for index, (language, text) in enumerate(chunks):
        part = folder / f"speech-{index:04d}.wav"
        try:
            run(["espeak-ng", "-v", language, "-s", "145", "-w", str(part), text], 120)
        except Exception as exc:
            raise RuntimeError(f"{'বাংলা' if language == 'bn' else 'ইংরেজি'} কণ্ঠ তৈরি করা যায়নি।") from exc
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


def _image_keywords(script: str):
    stopwords = set("""
    the and for with this that from your you are was were have has had will would can could
    about into over under then than when where what why how not but or as is am be
    আমি তুমি তিনি তারা আমরা আপনার আমাদের তাদের এটা এটি এই সেই যে কী কেন কিভাবে এবং অথবা
    থেকে জন্য নিয়ে করা হবে হয় আছে ছিল একটি একজন আজকে যেন কিন্তু
    """.split())
    tokens = re.findall(r"[\u0980-\u09FF]{3,}|[A-Za-z]{3,}", script[:900])
    keywords, seen = [], set()
    for token in tokens:
        key = token.lower()
        if key not in stopwords and key not in seen:
            seen.add(key)
            keywords.append(token)
        if len(keywords) >= 5:
            break
    return keywords


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
            credit = f"{title[:55]} | {artist[:45]} | {license_name[:20]} https://commons.wikimedia.org/wiki/{urllib.parse.quote(str(page.get('title', '')))}"
            if not is_reusable:
                continue
            image, attribution = _download_checked_image(image_url, folder, "commons-context-image", credit)
            if image:
                return image, attribution
    except Exception:
        pass
    return None, ""

def make_background(script: str, folder: Path):
    # Small canvas is intentional: keep peak memory below Render Free's 512 MiB limit.
    width, height = 360, 640
    # Use small Wikimedia Commons thumbnails with a strict pixel limit; fall back to graphics if unavailable.
    source_image, credit = find_contextual_image(script, folder)
    if source_image:
        try:
            with Image.open(source_image) as source:
                image = ImageOps.fit(source.convert("RGB"), (width, height), method=Image.Resampling.BILINEAR)
            overlay = Image.new("RGBA", (width, height), (3, 13, 28, 145))
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

def make_scene_backgrounds(script: str, folder: Path):
    """Create up to six scene backgrounds from separate sentences; later sentences reuse the last scene."""
    sentences = [x.strip() for x in re.split(r"(?<=[.!?।])\s+|\n+", script) if x.strip()]
    if not sentences:
        sentences = [script.strip() or "বাংলা ভিডিও"]
    selected = sentences[:6]
    backgrounds = []
    for index, sentence in enumerate(selected):
        scene_dir = folder / f"scene-{index:02d}"
        scene_dir.mkdir(parents=True, exist_ok=True)
        backgrounds.append(make_background(sentence, scene_dir))
    return backgrounds

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



def make_caption_frames(script: str, duration: float, background: Path, folder: Path, caption_offset: float = 0.0):
    """Render small Pillow caption cards with per-word highlighting, avoiding FFmpeg's memory-heavy libass filter."""
    frame_dir = folder / "caption-frames"
    frame_dir.mkdir(parents=True, exist_ok=True)
    background_paths = background if isinstance(background, (list, tuple)) else [background]
    bases = []
    for background_path in background_paths:
        with Image.open(background_path) as source:
            bases.append(source.convert("RGB").resize((180, 320), Image.Resampling.BILINEAR))

    sentences = [x.strip() for x in re.split(r"(?<=[.!?।])\s+|\n+", script) if x.strip()]
    if not sentences:
        sentences = [script.strip()] if script.strip() else ["ভিডিও"]
    sentence_words = [re.findall(r"\S+", sentence) for sentence in sentences]
    sentence_weights = [max(1, len(words)) for words in sentence_words]
    total_weight = sum(sentence_weights)
    safe_offset = max(-max(0.0, duration - 0.1), min(max(0.0, duration - 0.1), caption_offset))
    cursor = max(0.0, safe_offset)
    usable_duration = max(0.1, duration - safe_offset) if safe_offset >= 0 else max(0.1, duration + safe_offset)
    font = load_font(13, True)
    entries = []
    image_index = 0
    blank_path = frame_dir / "timing-gap.png"
    bases[0].save(blank_path, optimize=True)
    if safe_offset > 0:
        entries.append((blank_path, safe_offset))

    for sentence_index, (sentence, words, weight) in enumerate(zip(sentences, sentence_words, sentence_weights)):
        if not words:
            continue
        base = bases[min(sentence_index, len(bases) - 1)]
        sentence_duration = max(0.05, usable_duration * weight / total_weight)
        word_weights = [max(1, len(word)) for word in words]
        word_total = sum(word_weights)
        for word_index, (word, word_weight) in enumerate(zip(words, word_weights)):
            start = cursor
            word_duration = sentence_duration * word_weight / word_total
            end = cursor + word_duration
            # Gentle zoom in/out across caption cards; Pillow keeps this low-memory on Render Free.
            phase = (image_index % 16) / 15.0
            zoom = 1.0 + 0.04 * (1.0 - abs(phase * 2.0 - 1.0))
            crop_width = max(1, int(base.width / zoom))
            crop_height = max(1, int(base.height / zoom))
            left_crop = (base.width - crop_width) // 2
            top_crop = (base.height - crop_height) // 2
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
            frame.convert("RGB").save(path, optimize=True)
            entries.append((path, max(0.05, end - start)))
            image_index += 1
            cursor = end

    if safe_offset < 0:
        entries.append((blank_path, abs(safe_offset)))
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

def render(job_id: str, script: str, mode: str, audio_path: Optional[Path], caption_offset: float = 0.0):
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
        backgrounds = make_scene_backgrounds(script, folder)
        print(f"VIDEO_STAGE job={job_id} stage=background_done scenes={len(backgrounds)} providers=openverse,wikimedia,graphic_fallback", flush=True)
        with LOCK:
            JOBS[job_id]["progress"] = 40
            JOBS[job_id]["message"] = "বাক্যভিত্তিক দৃশ্য ও পটভূমি তৈরি হয়েছে"
        print(f"VIDEO_STAGE job={job_id} stage=subtitles_start", flush=True)
        frame_list, frame_count = make_caption_frames(script, duration, backgrounds, folder, caption_offset)
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
    return {"status": "ok" if all(tools.values()) else "degraded", "tools": tools, "version": "0.2.0"}


@app.post("/api/jobs", status_code=202)
async def create_job(script: str = Form(...), mode: str = Form("auto"), audio: Optional[UploadFile] = File(None), voice_clone_consent: bool = Form(False), caption_offset: float = Form(0.0)):
    script = script.strip()
    if not script:
        raise HTTPException(400, "আগে বাংলা বা ইংরেজি লেখা যোগ করুন।")
    if len(script) > MAX_SCRIPT_CHARS:
        raise HTTPException(413, f"লেখা সর্বোচ্চ {MAX_SCRIPT_CHARS} অক্ষরের হতে পারবে।")
    if mode not in ("auto", "audio", "clone"):
        raise HTTPException(400, "ভিডিও তৈরির পদ্ধতি সঠিক নয়।")
    if not -1.5 <= caption_offset <= 1.5:
        raise HTTPException(400, "সাবটাইটেলের সময় -১.৫ থেকে +১.৫ সেকেন্ডের মধ্যে দিন।")
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
    threading.Thread(target=render, args=(job_id, script, mode, audio_path, caption_offset), daemon=True).start()
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
