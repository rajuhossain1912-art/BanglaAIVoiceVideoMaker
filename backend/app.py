import base64
import json
import io
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
# Optional comma-separated public Gradio Spaces with the same API contract.
VOICE_CLONE_BN_SPACES = [x.strip() for x in os.getenv("VOICE_CLONE_BN_SPACES", VOICE_CLONE_SPACE).split(",") if x.strip()]
VOICE_CLONE_EN_SPACE = os.getenv("VOICE_CLONE_EN_SPACE", "ResembleAI/Chatterbox")
VOICE_CLONE_EN_SPACES = [x.strip() for x in os.getenv("VOICE_CLONE_EN_SPACES", VOICE_CLONE_EN_SPACE).split(",") if x.strip()]
VOICE_CLONE_ENABLED = os.getenv("VOICE_CLONE_ENABLED", "true").lower() in ("1", "true", "yes")
AI_IMAGE_GENERATION_ENABLED = os.getenv("AI_IMAGE_GENERATION_ENABLED", "true").lower() in ("1", "true", "yes")
AI_IMAGE_PROVIDER_ORDER = [x.strip().lower() for x in os.getenv("AI_IMAGE_PROVIDER_ORDER", "pollinations,flux,zimage").split(",") if x.strip()]
AI_IMAGE_PROVIDER_TIMEOUT = max(12, min(45, int(os.getenv("AI_IMAGE_PROVIDER_TIMEOUT", "28"))))
ALLOW_LICENSED_IMAGE_FALLBACK = os.getenv("ALLOW_LICENSED_IMAGE_FALLBACK", "true").lower() in ("1", "true", "yes")
WORK_DIR = Path(os.getenv("WORK_DIR", "/tmp/bangla-video-jobs"))
WORK_DIR.mkdir(parents=True, exist_ok=True)
MAX_SCRIPT_CHARS = int(os.getenv("MAX_SCRIPT_CHARS", "50000"))
MAX_AUDIO_MB = int(os.getenv("MAX_AUDIO_MB", "40"))
JOBS = {}
LOCK = threading.Lock()
try:
    JOB_RETENTION_SECONDS = max(3600, int(os.getenv("JOB_RETENTION_SECONDS", "86400")))
except (TypeError, ValueError):
    JOB_RETENTION_SECONDS = 86400
try:
    MAX_ACTIVE_JOBS = max(1, min(4, int(os.getenv("MAX_ACTIVE_JOBS", "1"))))
except (TypeError, ValueError):
    MAX_ACTIVE_JOBS = 1
app = FastAPI(title="Bangla AI Voice Video Maker API", version="0.3.0")


def _cleanup_expired_jobs(now=None):
    """Remove terminal jobs after the retention window and old orphaned job folders."""
    current_time = time.time() if now is None else float(now)
    expired_before = current_time - JOB_RETENTION_SECONDS
    expired_ids = []
    with LOCK:
        for job_id, job in list(JOBS.items()):
            if job.get("status") not in ("completed", "failed"):
                continue
            finished_at = job.get("completed_at", job.get("created_at", current_time))
            try:
                is_expired = float(finished_at) < expired_before
            except (TypeError, ValueError):
                is_expired = False
            if is_expired:
                expired_ids.append(job_id)
                JOBS.pop(job_id, None)
        active_ids = set(JOBS)
    for job_id in expired_ids:
        shutil.rmtree(WORK_DIR / job_id, ignore_errors=True)
    # A process restart clears in-memory JOBS. Remove only folders older than the
    # same retention window, never folders belonging to active in-memory jobs.
    try:
        for folder in WORK_DIR.iterdir():
            if not folder.is_dir() or folder.name in active_ids:
                continue
            try:
                if current_time - folder.stat().st_mtime > JOB_RETENTION_SECONDS:
                    shutil.rmtree(folder, ignore_errors=True)
            except OSError:
                continue
    except OSError:
        pass


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
    tokens = re.findall(r"[\u0980-\u09FF]+|[A-Za-z0-9]+|[^A-Za-z0-9\u0980-\u09FF]+", script)
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

    # Split long language runs into manageable requests for free TTS endpoints.
    tts_chunks = []
    for language, text in chunks:
        remaining = text.strip()
        while remaining:
            if len(remaining) <= 2500:
                piece, remaining = remaining, ""
            else:
                cut = remaining.rfind(" ", 0, 2501)
                if cut < 1000:
                    cut = 2500
                piece, remaining = remaining[:cut].strip(), remaining[cut:].strip()
            if piece:
                tts_chunks.append((language, piece))
    chunks = tts_chunks

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


def _write_gradio_audio_result(audio_result, folder: Path, stem: str, base_url: str = ""):
    """Normalize Gradio audio results, including FileData objects and relative URLs."""
    if audio_result is None:
        return None

    # Gradio versions may expose FileData as a mapping or a typed object.
    if not isinstance(audio_result, (dict, tuple, list, str, bytes)):
        values = {}
        for key in ("path", "url", "audio", "data", "value"):
            value = getattr(audio_result, key, None)
            if value is not None:
                values[key] = value
        if values:
            audio_result = values
        else:
            print(f"VOICE_CLONE_AUDIO_RESULT_UNSUPPORTED type={type(audio_result).__name__}", flush=True)
            return None

    if isinstance(audio_result, dict):
        path_value = audio_result.get("path")
        url_value = audio_result.get("url")
        print(
            "VOICE_CLONE_AUDIO_RESULT "
            f"type=dict keys={','.join(sorted(str(key) for key in audio_result.keys()))} "
            f"path_type={type(path_value).__name__} url_type={type(url_value).__name__}",
            flush=True,
        )
        if isinstance(path_value, str) and Path(path_value).is_file():
            return Path(path_value)
        if isinstance(url_value, str) and url_value:
            resolved_url = urllib.parse.urljoin((base_url.rstrip("/") + "/") if base_url else "", url_value)
            downloaded = _write_gradio_audio_result(resolved_url, folder, stem, base_url=base_url)
            if downloaded is not None:
                return downloaded
        for key in ("audio", "data", "value"):
            nested = audio_result.get(key)
            if nested is not None:
                downloaded = _write_gradio_audio_result(nested, folder, stem, base_url=base_url)
                if downloaded is not None:
                    return downloaded
        if isinstance(path_value, str) and path_value.startswith(("http://", "https://", "/")):
            resolved_path = urllib.parse.urljoin((base_url.rstrip("/") + "/") if base_url else "", path_value)
            if resolved_path.startswith(("http://", "https://")):
                return _write_gradio_audio_result(resolved_path, folder, stem, base_url=base_url)
        return None

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
        except Exception as exc:
            print(f"VOICE_CLONE_AUDIO_ARRAY_FAILED error={type(exc).__name__}", flush=True)
            return None

    if isinstance(audio_result, (tuple, list)):
        for index, item in enumerate(audio_result):
            candidate = _write_gradio_audio_result(item, folder, f"{stem}-{index}", base_url=base_url)
            if candidate is not None:
                return candidate
        return None

    if isinstance(audio_result, bytes):
        if len(audio_result) > 100:
            raw_audio = folder / f"{stem}-remote"
            raw_audio.write_bytes(audio_result)
            return raw_audio
        return None

    if isinstance(audio_result, str):
        if Path(audio_result).is_file():
            return Path(audio_result)
        if audio_result.startswith(("https://", "http://")) or (audio_result.startswith("/") and base_url):
            remote_url = urllib.parse.urljoin((base_url.rstrip("/") + "/") if base_url else "", audio_result)
            remote_audio = folder / f"{stem}-remote"
            try:
                request = urllib.request.Request(
                    remote_url,
                    headers={"User-Agent": "BanglaAIVoiceVideoMaker/0.4"},
                )
                with urllib.request.urlopen(request, timeout=45) as response:
                    data = response.read(50 * 1024 * 1024 + 1)
                    response_headers = getattr(response, "headers", None)
                    content_type = response_headers.get("Content-Type", "") if hasattr(response_headers, "get") else ""
                if 100 < len(data) <= 50 * 1024 * 1024 and "text/html" not in content_type.lower():
                    remote_audio.write_bytes(data)
                    print(f"VOICE_CLONE_AUDIO_DOWNLOADED bytes={len(data)} content_type={content_type[:80]}", flush=True)
                    return remote_audio
                print(f"VOICE_CLONE_AUDIO_DOWNLOAD_INVALID bytes={len(data)} content_type={content_type[:80]}", flush=True)
            except Exception as exc:
                print(f"VOICE_CLONE_AUDIO_DOWNLOAD_FAILED error={type(exc).__name__} url_host={urllib.parse.urlparse(remote_url).netloc}", flush=True)
                return None
    return None


def _clone_with_cosyvoice(script: str, normalized: Path, space: str):
    from gradio_client import Client, handle_file
    client = Client(space, verbose=False, httpx_kwargs={"timeout": 120.0})
    result = client.predict(
        script,
        handle_file(str(normalized)),
        0,
        1.0,
        api_name="/generate_cross_lingual_audio",
    )
    # Resolve relative FileData URLs against the actual Space host. Gradio
    # FileData may be returned as a dict or typed object depending on version.
    base_url = getattr(client, "src", "") or ""
    if isinstance(result, (list, tuple)):
        return (result[0], base_url) if result else (None, base_url)
    return result, base_url


def _clone_with_chatterbox(script: str, normalized: Path, space: str):
    from gradio_client import Client, handle_file
    client = Client(space, verbose=False, httpx_kwargs={"timeout": 120.0})
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


def _clone_with_provider_fallback(
    script: str, normalized: Path, spaces, clone_function, language: str,
    folder: Path, stem: str, progress_callback=None, progress_base: int = 14,
    progress_span: int = 14,
):
    """Try free Spaces in order and announce each attempt before waiting on its queue."""
    failures = []
    available_spaces = list(spaces)
    for index, space in enumerate(available_spaces):
        if progress_callback:
            percent = min(29, progress_base + int(progress_span * index / max(1, len(available_spaces))))
            progress_callback(
                percent,
                f"ফ্রি কণ্ঠসেবা {index + 1}/{len(available_spaces)} চেষ্টা করা হচ্ছে। উত্তর আসতে কিছুটা সময় লাগতে পারে।"
            )
        try:
            print(f"VOICE_CLONE_TRY language={language} space={space}", flush=True)
            result = clone_function(script, normalized, space)
            base_url = ""
            if isinstance(result, tuple) and len(result) == 2 and isinstance(result[1], str):
                result, base_url = result
            candidate = _write_gradio_audio_result(result, folder, stem, base_url=base_url)
            if candidate is None or not candidate.exists() or candidate.stat().st_size < 100:
                raise RuntimeError("Space returned no usable audio file")
            print(f"VOICE_CLONE_OK language={language} space={space}", flush=True)
            return candidate, space
        except Exception as exc:
            failures.append(f"{space}: {type(exc).__name__}: {str(exc)[:120]}")
            print(f"VOICE_CLONE_FAILED language={language} space={space} error={type(exc).__name__}", flush=True)
    raise RuntimeError("All configured free voice-clone Spaces failed. " + " | ".join(failures))


def _split_voice_clone_text(script: str, max_chars: int = 450):
    """Split narration at sentence boundaries into provider-sized chunks."""
    sentences = re.split(r"(?<=[।.!?])\s+|\n+", script.strip())
    chunks = []
    current = ""
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        while len(sentence) > max_chars:
            cut = sentence.rfind(" ", 0, max_chars + 1)
            if cut < max_chars // 2:
                cut = max_chars
            piece, sentence = sentence[:cut].strip(), sentence[cut:].strip()
            if piece:
                if current:
                    chunks.append(current)
                    current = ""
                chunks.append(piece)
        candidate = sentence if not current else current + " " + sentence
        if len(candidate) <= max_chars:
            current = candidate
        else:
            if current:
                chunks.append(current)
            current = sentence
    if current:
        chunks.append(current)
    return chunks


def synthesize_cloned_voice(script: str, reference_audio: Path, folder: Path, progress_callback=None) -> Path:
    """Clone narration in short chunks, with free-provider failover for each chunk."""
    if not VOICE_CLONE_ENABLED:
        raise RuntimeError("নিজের কণ্ঠের পরীক্ষামূলক সুবিধা বর্তমানে বন্ধ আছে।")
    if len(script) > 3000:
        raise RuntimeError("নিজের কণ্ঠে একবারে সর্বোচ্চ ৩০০০ অক্ষর ব্যবহার করুন।")
    normalized = folder / "voice_reference.wav"
    pure_english = bool(re.search(r"[A-Za-z]", script)) and not bool(re.search(r"[\u0980-\u09FF]", script))
    try:
        if progress_callback:
            progress_callback(12, "নিজের কণ্ঠের নমুনা অডিও প্রস্তুত করা হচ্ছে।")
        run(["ffmpeg", "-y", "-i", str(reference_audio), "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(normalized)], 120)
        if progress_callback:
            progress_callback(13, "ফ্রি কণ্ঠসেবার সঙ্গে সংযোগ করা হচ্ছে।")
        output = folder / "cloned_voice.wav"
        chunks = _split_voice_clone_text(script, max_chars=250)
        print(f"VOICE_CLONE_PLAN chunks={len(chunks)} characters={len(script)}", flush=True)
        audio_parts = []
        selected_providers = []
        for index, text_chunk in enumerate(chunks):
            chunk_start_progress = 14 + int(16 * index / max(1, len(chunks)))
            chunk_end_progress = 14 + int(16 * (index + 1) / max(1, len(chunks)))
            provider_progress_base = min(chunk_end_progress - 1, chunk_start_progress + 1)
            provider_progress_span = max(1, chunk_end_progress - provider_progress_base)
            print(f"VOICE_CLONE_CHUNK_START part={index + 1}/{len(chunks)} characters={len(text_chunk)}", flush=True)
            if progress_callback:
                progress_callback(chunk_start_progress, f"নিজের কণ্ঠ তৈরি হচ্ছে: অংশ {index + 1}/{len(chunks)}।")
            if pure_english:
                try:
                    candidate, provider = _clone_with_provider_fallback(
                        text_chunk, normalized, VOICE_CLONE_EN_SPACES, _clone_with_chatterbox,
                        "en", folder, f"clone-part-{index:03d}",
                        progress_callback=progress_callback, progress_base=provider_progress_base, progress_span=max(1, provider_progress_span // 2)
                    )
                except Exception as english_error:
                    try:
                        candidate, provider = _clone_with_provider_fallback(
                            text_chunk, normalized, VOICE_CLONE_BN_SPACES, _clone_with_cosyvoice,
                            "en_fallback", folder, f"clone-part-{index:03d}",
                            progress_callback=progress_callback, progress_base=min(chunk_end_progress - 1, provider_progress_base + max(1, provider_progress_span // 2)), progress_span=max(1, provider_progress_span // 2)
                        )
                    except Exception:
                        raise english_error
            else:
                candidate, provider = _clone_with_provider_fallback(
                    text_chunk, normalized, VOICE_CLONE_BN_SPACES, _clone_with_cosyvoice,
                    "bn_or_mixed", folder, f"clone-part-{index:03d}",
                    progress_callback=progress_callback, progress_base=provider_progress_base, progress_span=provider_progress_span
                )
            selected_providers.append(provider)
            print(f"VOICE_CLONE_CHUNK_OK part={index + 1}/{len(chunks)}", flush=True)
            if progress_callback:
                progress_callback(chunk_end_progress, f"নিজের কণ্ঠ তৈরি হচ্ছে: {index + 1}/{len(chunks)} অংশ সম্পন্ন হয়েছে।")
            part_wav = folder / f"clone-part-{index:03d}.wav"
            run(["ffmpeg", "-y", "-i", str(candidate), "-ac", "1", "-ar", "24000", "-c:a", "pcm_s16le", str(part_wav)], 120)
            if not part_wav.exists() or part_wav.stat().st_size < 100:
                raise RuntimeError(f"Voice service returned empty audio for part {index + 1}")
            audio_parts.append(part_wav)
        if len(audio_parts) == 1:
            shutil.copyfile(audio_parts[0], output)
        else:
            listing = folder / "clone-parts.txt"
            listing.write_text("".join(f"file '{part.as_posix()}'\n" for part in audio_parts), encoding="utf-8")
            run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(listing), "-c:a", "pcm_s16le", str(output)], 180)
        if output.exists() and output.stat().st_size > 100:
            provider_summary = ",".join(dict.fromkeys(selected_providers))
            print(f"VOICE_PROVIDER selected={provider_summary} language={'en' if pure_english else 'bn_or_mixed'} chunks={len(chunks)}", flush=True)
            return output
        raise RuntimeError("The voice service returned an empty audio file")
    except Exception as exc:
        print(f"VOICE_PROVIDER failed language={'en' if pure_english else 'bn_or_mixed'} error={type(exc).__name__}: {str(exc)[:250]}", flush=True)
        raise RuntimeError("নিজের কণ্ঠে অডিও তৈরি করা যায়নি। ফ্রি কণ্ঠ-সেবা ব্যস্ত বা পরিবর্তিত হতে পারে। কিছুক্ষণ পর চেষ্টা করুন, অথবা সাধারণ স্বয়ংক্রিয় ভয়েস বেছে নিন।") from exc
    finally:
        normalized.unlink(missing_ok=True)

def load_font(size: int, bold=False):
    # Debian's Noto package may install variable-font filenames rather than
    # the older NotoSansBengali-Regular/Bold names. Search Bengali-capable
    # fonts before falling back to DejaVu/default, which may render tofu boxes.
    preferred = [
        "/usr/share/fonts/truetype/noto/NotoSansBengali-Bold.ttf" if bold else "/usr/share/fonts/truetype/noto/NotoSansBengali-Regular.ttf",
        "/usr/share/fonts/truetype/noto/NotoSansBengaliUI-Bold.ttf" if bold else "/usr/share/fonts/truetype/noto/NotoSansBengaliUI-Regular.ttf",
    ]
    candidates = [p for p in preferred if Path(p).exists()]
    for pattern in (
        "/usr/share/fonts/**/*Bengali*Bold*.ttf" if bold else "/usr/share/fonts/**/*Bengali*Regular*.ttf",
        "/usr/share/fonts/**/*Bengali*.ttf",
    ):
        candidates.extend(sorted(Path("/").glob(pattern.lstrip("/"))))
    candidates.extend([
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ])
    seen = set()
    for candidate in candidates:
        candidate = str(candidate)
        if candidate in seen or not Path(candidate).exists():
            continue
        seen.add(candidate)
        try:
            return ImageFont.truetype(candidate, size)
        except Exception:
            continue
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
    (("ট্রেন", "রেল", "রেলগাড়ি", "রেলগাড়ি", "রেলওয়ে", "রেলওয়ে", "স্টেশন", "train", "railway", "rail station"), "a real passenger train at a Bangladeshi railway station, with the train and railway tracks clearly visible"),
    (("বাসস্ট্যান্ড", "বাসস্টপ", "বাস", "যাত্রীবাহী বাস", "bus stop", "city bus"), "a real Bangladeshi passenger bus at a roadside bus stop, bus clearly visible"),
    (("কৃষক", "ধানচাষ", "ধানক্ষেত", "চাষাবাদ", "কৃষিকাজ", "farmer", "rice field"), "a Bangladeshi farmer working in a green rice field, showing the farmer and crops clearly"),
    (("সাদাছড়ি", "সাদাছড়ি", "দৃষ্টিপ্রতিবন্ধী", "প্রতিবন্ধী", "অন্ধ", "দৃষ্টিহীন"), "a visually impaired person using a white cane in an accessible Bangladeshi setting"),
    (("কর্মসংস্থান", "চাকরি", "নিয়োগ", "নিয়োগ", "কর্মী", "কারখানা", "অফিস"), "Bangladeshi people working in a workplace or factory"),
    (("ব্রেইল", "braille", "ব্রেইল বই", "ব্রেইল লেখা"), "a visually impaired Bangladeshi student reading a Braille book with fingertips clearly touching the raised Braille dots, close-up in an accessible classroom"),
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
    (("পরিশ্রম", "পরিশ্রমের", "চেষ্টা", "চেষ্টা চালিয়ে", "সাফল্য", "সফল", "দক্ষতা", "লক্ষ্য", "লক্ষ্যে", "লক্ষ্যের", "বাধা", "ব্যর্থ", "থেমে"), "a determined Bangladeshi person doing a specific real-world task related to the surrounding sentence, documentary photography, clear subject"),
    (("স্বপ্ন",), "a realistic Bangladeshi person planning or working toward a clearly described personal goal, documentary photography"),
    (("সকাল", "ভোর", "সূর্যোদয়", "সূর্যোদয়"), "sunrise over a peaceful green landscape"),
    (("গাছপালা", "গাছ", "সবুজ", "বন", "প্রকৃতি"), "lush green trees and natural scenery"),
    (("আকাশ", "মেঘ", "নীল আকাশ"), "blue sky with soft white clouds"),
    (("পাখি", "পাখির", "কাক", "চড়ুই", "চড়ুই"), "birds flying among tree branches"),
    (("নদী", "পুকুর", "পানি", "জল"), "a peaceful river and reflective water"),
    (("গ্রাম", "কৃষক", "ধান", "মাঠ"), "a rural Bangladeshi village with green fields"),
    (("বৃষ্টি", "বর্ষা"), "a realistic rainy landscape"),
    (("ফুল", "ফুলের"), "a colorful flower garden"),
    (("সমুদ্র", "সাগর", "সমুদ্রসৈকত"), "ocean waves on a beach"),
    # Broad everyday subjects so arbitrary Bangla scripts do not default to generic graphics.
    (("ক্রিকেট", "ব্যাট", "বোলার", "উইকেট", "রান", "ক্রিকেটার"), "a realistic cricket match in Bangladesh with players on a green field"),
    (("ফুটবল", "গোল", "ফুটবলার", "মাঠে খেলা"), "a football match with players competing on a green pitch"),
    (("খেলাধুলা", "খেলা", "খেলোয়াড়", "খেলোয়াড়", "টুর্নামেন্ট", "অলিম্পিক"), "athletes competing in a sports event"),
    (("ইতিহাস", "ঐতিহাসিক", "মুক্তিযুদ্ধ", "ভাষা আন্দোলন", "১৯৭১", "একাত্তর"), "a respectful historical scene connected to Bangladesh's past"),
    (("বিজ্ঞান", "গবেষণা", "পরীক্ষাগার", "আবিষ্কার", "বিজ্ঞানী", "মহাকাশ"), "scientists conducting research in a modern laboratory"),
    (("রান্না", "খাবার", "রেসিপি", "রান্নাঘর", "পুষ্টি", "সবজি"), "fresh ingredients being prepared in a home kitchen"),
    (("ভ্রমণ", "পর্যটন", "ঘুরতে", "কক্সবাজার", "সুন্দরবন", "সেন্টমার্টিন", "পাহাড়", "পাহাড়"), "travelers exploring a beautiful destination in Bangladesh"),
    (("ব্যবসা", "বাণিজ্য", "দোকান", "উদ্যোক্তা", "ক্রেতা", "বিক্রেতা"), "a small Bangladeshi business owner serving customers"),
    (("ব্যাংক", "সঞ্চয়", "সঞ্চয়", "ঋণ", "লেনদেন", "টাকা", "মুদ্রা"), "a person managing household finances and savings"),
    (("নির্বাচন", "ভোট", "সংসদ", "রাজনীতি", "জনসভা", "প্রার্থী"), "a neutral civic scene showing people participating in a democratic election"),
    (("আবহাওয়া", "আবহাওয়া", "তাপমাত্রা", "জলবায়ু", "জলবায়ু", "গরম", "শীত", "ঝড়", "ঝড়"), "a realistic weather scene showing the relevant season and sky"),
    (("বিদ্যুৎ", "সৌরশক্তি", "জ্বালানি", "পরিবেশ", "দূষণ", "পুনর্ব্যবহার"), "renewable energy and environmental sustainability in Bangladesh"),
    (("সঙ্গীত", "গান", "গায়ক", "গায়ক", "বাদ্যযন্ত্র", "নাচ"), "musicians performing on a small stage with instruments"),
    (("বই", "লাইব্রেরি", "গ্রন্থাগার", "সাহিত্য", "কবিতা", "লেখক"), "a reader exploring books in a welcoming library"),
    (("প্রাণী", "পশু", "বিড়াল", "বিড়াল", "কুকুর", "গরু", "ছাগল", "বাঘ", "হাতি"), "animals in a natural or farm setting appropriate to the subject"),
    (("মাছ", "মাছধরা", "জেলে", "মৎস্য", "চিংড়ি", "চিংড়ি"), "Bangladeshi fishers working beside a river with fishing nets"),
    (("বিয়ে", "বিয়ে", "অনুষ্ঠান", "উৎসব", "ঈদ", "পূজা", "মেলা"), "a respectful community celebration in Bangladesh"),
    (("বাড়ি", "বাড়ি", "নির্মাণ", "স্থাপত্য", "ভবন", "বাসস্থান"), "a realistic home or building scene in Bangladesh"),
    (("যুদ্ধ", "শান্তি", "সংঘাত", "শরণার্থী"), "a humanitarian scene focused on civilian safety and peace"),
    (("মহিলা", "নারী", "মেয়ে", "মেয়ে", "নারীর অধিকার", "মাতৃত্ব"), "Bangladeshi women participating in everyday community life"),
]


def _contains_visual_term(text: str, term: str) -> bool:
    """Match subject words without accidental substring hits (e.g. বাস inside বিশ্বাস)."""
    text_tokens = re.findall(r"[A-Za-z]+|[\u0980-\u09FF]+", (text or "").lower())
    term_tokens = re.findall(r"[A-Za-z]+|[\u0980-\u09FF]+", (term or "").lower())
    if not term_tokens:
        return False
    bengali_suffixes = (
        "ের", "েরা", "র", "ে", "এ", "তে", "টি", "টা", "খানা", "খানি",
        "রা", "দের", "কে", "গুলি", "গুলো", "সমূহ", "জন", "জনের",
        "জনকে", "টির", "টার", "গুলোর", "গুলিতে",
    )
    for start in range(max(0, len(text_tokens) - len(term_tokens) + 1)):
        matched = True
        for offset, expected in enumerate(term_tokens):
            actual = text_tokens[start + offset]
            if actual == expected:
                continue
            if re.fullmatch(r"[\u0980-\u09FF]+", expected):
                # Match common Bengali inflections without broad substring hits.
                # For example, কৃষক -> কৃষকের, বাস -> বাসের, but not বাস -> বাস্তব.
                remainder = actual[len(expected):] if actual.startswith(expected) else ""
                if remainder in bengali_suffixes:
                    continue
            elif len(expected) >= 4 and actual.startswith(expected):
                continue
            matched = False
            break
        if matched:
            return True
    return False


def _matched_visual_concepts(script: str, limit: int = 2):
    """Choose only the strongest topics present in this scene, avoiding unrelated mixed prompts."""
    text = re.sub(r"\s+", " ", script or "").strip().lower()
    ranked = []
    for order, (terms, prompt) in enumerate(VISUAL_CONCEPTS):
        hits = sum(1 for term in terms if _contains_visual_term(text, term))
        if hits:
            # Specific terms win ties over broad concepts; original order is a stable final tie-breaker.
            specificity = max(len(term) for term in terms if _contains_visual_term(text, term))
            ranked.append((hits * 10 + min(specificity, 20) / 100 - order / 10000, order, prompt))
    ranked.sort(reverse=True)
    selected = []
    for _, _, prompt in ranked:
        if prompt not in selected:
            selected.append(prompt)
        if len(selected) >= limit:
            break
    return selected

def _image_keywords(script: str, model_visual_prompt: Optional[str] = None):
    """Build image-search terms from both Bangla topic matches and the AI's scene description."""
    concepts = _matched_visual_concepts(script, limit=2)
    # Bangla narration may have no local keyword match. In that case the storyboard
    # model's English description is the best available semantic search query.
    # Put concrete storyboard terms first so broad Bangla concepts cannot
    # consume the short query budget before the actual scene subject.
    phrase = re.sub(r"\s+", " ", str(model_visual_prompt or "")).strip()
    if concepts:
        phrase += " " + " ".join(concepts)
    if not phrase.strip():
        phrase = (script or "")[:500]
    tokens = re.findall(r"[A-Za-z]{3,}", phrase.lower())
    stopwords = {
        "the", "and", "for", "with", "this", "that", "from", "your", "you", "are",
        "was", "were", "have", "has", "had", "will", "would", "can", "could",
        "about", "into", "over", "under", "then", "than", "when", "where", "what",
        "why", "how", "not", "but", "or", "as", "is", "am", "be", "one", "scene",
        "show", "showing", "real", "person", "photograph", "photographic", "documentary",
        "image", "photo", "natural", "light", "clear", "focus", "vertical", "bangladeshi",
        "working", "green", "clearly", "rural", "plants", "beside", "flooded",
    }
    return list(dict.fromkeys(word for word in tokens if word not in stopwords))[:8]


def _image_title_relevance_score(title: str, keywords):
    """Rank photo titles using exact words and conservative English plural normalization."""
    def forms(word):
        value = re.sub(r"[^a-z]", "", str(word or "").lower())
        variants = {value} if len(value) >= 3 else set()
        if len(value) > 4 and value.endswith("ies"):
            variants.add(value[:-3] + "y")
        if len(value) > 4 and value.endswith(("ches", "shes", "xes", "zes", "sses")):
            variants.add(value[:-2])
        elif len(value) > 3 and value.endswith("s") and not value.endswith(("ss", "us", "is")):
            variants.add(value[:-1])
        return variants

    title_text = re.sub(r"\s+", " ", str(title or "")).lower()
    title_tokens = set(re.findall(r"[a-z]{3,}", title_text))
    normalized_title = set().union(*(forms(token) for token in title_tokens)) if title_tokens else set()
    terms = list(dict.fromkeys(
        str(word).lower() for word in (keywords or [])
        if re.fullmatch(r"[A-Za-z]{3,}", str(word))
    ))
    if not terms:
        return 0
    matched = sum(1 for word in terms if forms(word) & normalized_title)
    # A title with no concrete storyboard term is not a safe contextual-photo choice.
    return matched * 10 + (matched / len(terms))


def _licensed_photo_title_is_relevant(title: str, keywords):
    """Reject generic stock titles that share none of the requested scene subjects."""
    return _image_title_relevance_score(title, keywords) >= 10


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


def find_openverse_image(script: str, folder: Path, model_visual_prompt: Optional[str] = None):
    """Try Openverse's anonymous endpoint; only use CC0, public-domain, CC BY or CC BY-SA results."""
    keywords = _image_keywords(script, model_visual_prompt)
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
        results = data.get("results", [])
        results = sorted(
            enumerate(results),
            key=lambda pair: (_image_title_relevance_score(pair[1].get("title", ""), keywords), -pair[0]),
            reverse=True,
        )
        for _, item in results:
            if not _licensed_photo_title_is_relevant(item.get("title", ""), keywords):
                continue
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


def find_contextual_image(script: str, folder: Path, model_visual_prompt: Optional[str] = None):
    """Try Openverse then Wikimedia using the storyboard's concrete scene description."""
    image, credit = find_openverse_image(script, folder, model_visual_prompt)
    if image:
        return image, credit
    keywords = _image_keywords(script, model_visual_prompt)
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
        pages = sorted(
            enumerate(pages),
            key=lambda pair: (_image_title_relevance_score(str(pair[1].get("title", "")).replace("File:", ""), keywords), -pair[0]),
            reverse=True,
        )
        for _, page in pages:
            if not _licensed_photo_title_is_relevant(str(page.get("title", "")).replace("File:", ""), keywords):
                continue
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
    explicit_map_context = any(_contains_visual_term(text, term) for term in map_terms)
    technology_context = any(_contains_visual_term(text, term) for term in tech_terms)
    return technology_context and not explicit_map_context and any(_contains_visual_term(title, term) for term in map_terms)



LANGUAGE_MODEL_VISUAL_PLANNER_ENABLED = os.getenv("LANGUAGE_MODEL_VISUAL_PLANNER_ENABLED", "true").lower() in ("1", "true", "yes")
LANGUAGE_MODEL_VISUAL_CACHE = {}


def _parse_scene_visual_prompts(raw: str, expected_count: int, scene_offset: int = 0):
    """Accept only correctly indexed JSON objects with concise scene-matched prompts."""
    text = (raw or "").strip()
    text = re.sub(r"^\x60\x60\x60(?:json)?\s*|\s*\x60\x60\x60$", "", text, flags=re.I)
    match = re.search(r"\[.*?\]", text, flags=re.S)
    try:
        parsed = json.loads(match.group(0)) if match else None
    except Exception:
        parsed = None
    if not isinstance(parsed, list) or len(parsed) != expected_count:
        return None
    cleaned = []
    for index, item in enumerate(parsed, start=1):
        # Prevent reordered model output from assigning one scene another scene's image.
        if not isinstance(item, dict) or item.get("scene") != scene_offset + index:
            return None
        value = re.sub(r"\s+", " ", str(item.get("visual_prompt") or "")).strip().strip('"')
        if not 40 <= len(value) <= 220 or re.search(r"[\x00-\x1f]", value):
            return None
        cleaned.append(value)
    return cleaned

def _storyboard_review_payload(scenes, prompts, context_scenes=None, context_offset=0):
    """Build reviewer items with full-story neighboring context for each scene."""
    full_context = context_scenes if context_scenes is not None else scenes
    return [
        {
            "scene": context_offset + index + 1,
            "context_before": re.sub(r"\s+", " ", str(full_context[context_offset + index - 1])).strip()[:180]
                if context_offset + index > 0 else "",
            "narration": re.sub(r"\s+", " ", str(scene)).strip()[:300],
            "context_after": re.sub(r"\s+", " ", str(full_context[context_offset + index + 1])).strip()[:180]
                if context_offset + index + 1 < len(full_context) else "",
            "proposed_visual_prompt": prompt,
        }
        for index, (scene, prompt) in enumerate(zip(scenes, prompts))
    ]


def _review_scene_visual_prompts(scenes, prompts, model_names, planner_model, context_scenes=None, context_offset=0):
    """Use a second, different language model to critique scene-to-image prompt alignment."""
    account_id = os.getenv("CLOUDFLARE_ACCOUNT_ID", "").strip()
    api_token = os.getenv("CLOUDFLARE_AI_API_TOKEN", os.getenv("CLOUDFLARE_API_TOKEN", "")).strip()
    if not account_id or not api_token or not prompts:
        return prompts
    reviewer_models = [name for name in model_names if name != planner_model]
    if not reviewer_models:
        return prompts
    review_items = _storyboard_review_payload(scenes, prompts, context_scenes, context_offset)
    review_prompt = (
        "You are an independent quality reviewer for a Bangladeshi educational video storyboard. "
        "Check each proposed visual prompt against its exact narration. Use context_before and context_after only "
        "to resolve pronouns and continuity; never replace the current scene subject with a neighboring scene. "
        "Reject generic scenery, symbols, cartoons, vague silhouettes, unrelated objects, and details not supported "
        "by the narration. Keep the actual subject and action explicit. "
        "Rewrite weak prompts as concise, photorealistic documentary photography prompts. "
        "Do not invent facts, people, places, or actions. Preserve one prompt for each scene in the same order. "
        "Return ONLY a JSON array with keys scene and visual_prompt; each prompt must be 40 to 220 characters. "
        "Items: " + json.dumps(review_items, ensure_ascii=False)
    )
    for reviewer_model in reviewer_models[:2]:
        try:
            model_path = urllib.parse.quote(reviewer_model, safe="@/-")
            body = json.dumps({
                "messages": [
                    {"role": "system", "content": "Independently audit scene relevance. Return valid JSON only."},
                    {"role": "user", "content": review_prompt},
                ],
                "temperature": 0.1,
                "max_tokens": 1800,
            }).encode("utf-8")
            request = urllib.request.Request(
                f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/{model_path}",
                data=body,
                headers={
                    "Authorization": "Bearer " + api_token,
                    "Content-Type": "application/json",
                    "User-Agent": "BanglaAIVoiceVideoMaker/1.0",
                },
                method="POST",
            )
            with urllib.request.urlopen(request, timeout=9) as response:
                data = json.loads(response.read(250_000).decode("utf-8"))
            result = data.get("result") or {}
            raw = result.get("response") or result.get("choices", [{}])[0].get("message", {}).get("content", "")
            reviewed = _parse_scene_visual_prompts(raw, len(scenes), context_offset)
            if reviewed:
                print(
                    "LANGUAGE_MODEL review=passed planner=" + planner_model
                    + " reviewer=" + reviewer_model,
                    flush=True,
                )
                return reviewed
            print(
                "LANGUAGE_MODEL review=fallback reason=invalid_review_response reviewer="
                + reviewer_model,
                flush=True,
            )
        except Exception as exc:
            print(
                f"LANGUAGE_MODEL review=fallback reviewer={reviewer_model} "
                f"error={type(exc).__name__}: {str(exc)[:100]}",
                flush=True,
            )
    return prompts


def _parse_cloudflare_transcription_response(data):
    """Extract a non-empty transcript from a Workers AI Whisper response."""
    if not isinstance(data, dict) or data.get("success") is False:
        raise RuntimeError("কথার অডিও বোঝার মডেল সঠিক উত্তর দেয়নি।")
    result = data.get("result") or {}
    transcript = re.sub(r"\s+", " ", str(result.get("text") or "")).strip()
    if not transcript:
        raise RuntimeError("অডিওতে বোঝার মতো কথা পাওয়া যায়নি।")
    return transcript


def transcribe_uploaded_audio(audio_path: Path, folder: Path, progress_callback=None):
    """Transcribe audio-only uploads with Cloudflare Whisper in manageable two-minute chunks."""
    account_id = os.getenv("CLOUDFLARE_ACCOUNT_ID", "").strip()
    api_token = os.getenv("CLOUDFLARE_AI_API_TOKEN", os.getenv("CLOUDFLARE_API_TOKEN", "")).strip()
    if not account_id or not api_token:
        raise RuntimeError("অডিও থেকে লেখা বোঝার জন্য Cloudflare AI সংযোগ পাওয়া যায়নি। লেখা লিখে আবার চেষ্টা করুন।")
    chunk_dir = folder / "transcription-chunks"
    chunk_dir.mkdir(parents=True, exist_ok=True)
    pattern = chunk_dir / "speech-%04d.mp3"
    run([
        "ffmpeg", "-y", "-i", str(audio_path), "-vn", "-ac", "1", "-ar", "16000",
        "-c:a", "libmp3lame", "-b:a", "48k", "-f", "segment", "-segment_time", "120",
        "-reset_timestamps", "1", str(pattern)
    ], 180)
    chunks = sorted(chunk_dir.glob("speech-*.mp3"))
    if not chunks:
        raise RuntimeError("অডিওকে ছোট অংশে ভাগ করা যায়নি।")
    endpoint = (
        "https://api.cloudflare.com/client/v4/accounts/"
        + urllib.parse.quote(account_id, safe="")
        + "/ai/run/@cf/openai/whisper-large-v3-turbo"
    )
    transcripts = []
    for index, chunk_path in enumerate(chunks):
        if progress_callback:
            progress_callback(
                12 + int(12 * index / max(1, len(chunks))),
                f"কথা থেকে লেখা বোঝা হচ্ছে: {index + 1}/{len(chunks)}"
            )
        payload = {
            "audio": base64.b64encode(chunk_path.read_bytes()).decode("ascii"),
            "task": "transcribe",
            "vad_filter": True,
            "initial_prompt": "বাংলা ও ইংরেজি কথার সঠিক প্রতিলিপি লিখুন। নাম, স্থান ও প্রযুক্তিগত শব্দ যতটা সম্ভব ঠিক রাখুন।"
        }
        request = urllib.request.Request(
            endpoint,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": "Bearer " + api_token,
                "Content-Type": "application/json",
                "User-Agent": "BanglaAIVoiceVideoMaker/1.0"
            },
            method="POST"
        )
        try:
            with urllib.request.urlopen(request, timeout=55) as response:
                data = json.loads(response.read(2_000_000).decode("utf-8"))
            transcripts.append(_parse_cloudflare_transcription_response(data))
        except Exception as exc:
            raise RuntimeError(
                f"অডিওর {index + 1} নম্বর অংশের কথা বোঝা যায়নি: {type(exc).__name__}"
            ) from exc
    transcript = " ".join(transcripts).strip()
    if len(transcript) > MAX_SCRIPT_CHARS:
        raise RuntimeError(f"অডিওর লেখা {MAX_SCRIPT_CHARS} অক্ষরের সীমা অতিক্রম করেছে।")
    return transcript


def _storyboard_scene_payload(scenes, context_scenes=None, context_offset=0):
    """Build scene prompts with adjacent narration from the complete storyboard."""
    full_context = context_scenes if context_scenes is not None else scenes
    return [
        {
            "scene": context_offset + i + 1,
            "context_before": re.sub(r"\s+", " ", full_context[context_offset + i - 1]).strip()[:180]
                if context_offset + i > 0 else "",
            "text": re.sub(r"\s+", " ", text).strip()[:300],
            "context_after": re.sub(r"\s+", " ", full_context[context_offset + i + 1]).strip()[:180]
                if context_offset + i + 1 < len(full_context) else "",
        }
        for i, text in enumerate(scenes)
    ]


def _plan_scene_visual_prompts(scenes, context_scenes=None, context_offset=0):
    """Plan prompts in batches while preserving neighboring narration across batch edges."""
    if not LANGUAGE_MODEL_VISUAL_PLANNER_ENABLED or not scenes:
        return None
    full_context = context_scenes if context_scenes is not None else scenes
    if len(scenes) > 8:
        planned = []
        for start in range(0, len(scenes), 8):
            batch = _plan_scene_visual_prompts(
                scenes[start:start + 8], context_scenes=full_context,
                context_offset=context_offset + start
            )
            if not batch or len(batch) != len(scenes[start:start + 8]):
                return None
            planned.extend(batch)
        return planned
    scene_payload = _storyboard_scene_payload(scenes, full_context, context_offset)
    cache_key = json.dumps(scene_payload, ensure_ascii=False, sort_keys=True)
    if cache_key in LANGUAGE_MODEL_VISUAL_CACHE:
        return LANGUAGE_MODEL_VISUAL_CACHE[cache_key]
    prompt = (
        "You are a strict visual storyboard planner for a Bangladeshi educational video. "
        "For EACH input scene, create exactly one concrete, photorealistic image prompt depicting the main subject or action explicitly stated in THAT scene. "
        "Understand the narration as a connected story. Use context_before and context_after to resolve pronouns, implied subjects, people, places, and cause-and-effect, so the image fits what is being said. "
        "Depict the main action in the current scene text; neighboring context may clarify it but must not replace or blend the current scene subject. "
        "Do not use generic symbols, flags, globes, maps, abstract gradients, or unrelated stock imagery unless that exact subject is discussed. "
        "Prefer real, recognizable objects and actions: if the scene says farmer or rice field, show a farmer working in a rice field; if it says city traffic, show actual buses and street traffic; if it says students, show students learning; if it says technology or smartphones, show a person using real digital devices. "
        "Use Bangladesh-local people and places when relevant. Never replace a specific subject with a vague landscape or symbolic icon. "
        "Every image must be crisp, sharp-focused, realistic documentary photography with a clear visible subject and natural light. "
        "Avoid blur, haze, glowing silhouettes, abstract human shapes, extreme close-ups, distorted faces, and empty gradients. "
        "For a person, show a recognizable activity and relevant objects in the same frame. "
        "For smartphone, TalkBack, accessibility or screen-reader scenes show a real person using a phone, never a world map or globe unless geography is explicitly discussed. "
        "No text, subtitles, letters, logos, flags, watermarks, or decorative symbols unless the scene explicitly mentions them. "
        "Return ONLY valid JSON as an array of objects with keys scene and visual_prompt, in the same order, exactly one object per input. "
        "Keep each visual_prompt between 40 and 220 characters. Input scenes: "
        + json.dumps(scene_payload, ensure_ascii=False)
    )
    # Cloudflare Workers AI is the preferred optional external model.
    # Try a small fallback chain of models on the same configured account. This
    # uses the account's free allocation only; it does not enable paid providers.
    cf_account_id = os.getenv("CLOUDFLARE_ACCOUNT_ID", "").strip()
    cf_api_token = os.getenv("CLOUDFLARE_AI_API_TOKEN", os.getenv("CLOUDFLARE_API_TOKEN", "")).strip()
    if cf_account_id and cf_api_token:
        default_models = [
            os.getenv("CLOUDFLARE_AI_MODEL", "@cf/google/gemma-4-26b-a4b-it").strip(),
            "@cf/zai-org/glm-4.7-flash",
            "@cf/qwen/qwen3-30b-a3b-fp8",
        ]
        configured_models = os.getenv("CLOUDFLARE_AI_MODELS", "").strip()
        model_names = list(dict.fromkeys(
            x.strip() for x in (configured_models.split(",") if configured_models else default_models)
            if x.strip()
        ))
        for model in model_names:
            try:
                body = json.dumps({
                    "messages": [
                        {"role": "system", "content": "Return valid JSON only. Plan scene-matched visuals, not speech."},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.15, "max_tokens": 1800,
                    **({"chat_template_kwargs": {"enable_thinking": False}} if model == "@cf/google/gemma-4-26b-a4b-it" else {}),
                }).encode("utf-8")
                model_path = urllib.parse.quote(model, safe="@/-")
                request = urllib.request.Request(
                    f"https://api.cloudflare.com/client/v4/accounts/{cf_account_id}/ai/run/{model_path}",
                    data=body,
                    headers={"Authorization": "Bearer " + cf_api_token, "Content-Type": "application/json", "User-Agent": "BanglaAIVoiceVideoMaker/0.8"},
                    method="POST",
                )
                with urllib.request.urlopen(request, timeout=8) as response:
                    data = json.loads(response.read(250_000).decode("utf-8"))
                result = data.get("result") or {}
                raw = result.get("response") or result.get("choices", [{}])[0].get("message", {}).get("content", "")
                prompts = _parse_scene_visual_prompts(raw, len(scenes), context_offset)
                if prompts:
                    # Cross-check with a different model before accepting the storyboard.
                    prompts = _review_scene_visual_prompts(scenes, prompts, model_names, model, full_context, context_offset)
                    LANGUAGE_MODEL_VISUAL_CACHE[cache_key] = prompts
                    print("LANGUAGE_MODEL selected=Cloudflare-Workers-AI model=" + model, flush=True)
                    return prompts
                print("LANGUAGE_MODEL fallback=next_model provider=cloudflare model=" + model + " reason=invalid_model_response", flush=True)
            except Exception as exc:
                print(f"LANGUAGE_MODEL fallback=next_model provider=cloudflare model={model} error={type(exc).__name__}: {str(exc)[:120]}", flush=True)
    elif not cf_account_id or not cf_api_token:
        missing = "account_id" if not cf_account_id else "api_token"
        print(f"LANGUAGE_MODEL fallback=local reason=missing_cloudflare_{missing}", flush=True)
    # No paid or credit-based fallback is enabled; use local keyword planning if Cloudflare is absent.
    return None


def _english_visual_prompt(script: str, model_visual_prompt: Optional[str] = None):
    """Create a focused prompt and explicitly suppress common off-topic map/globe imagery."""
    concepts = _matched_visual_concepts(script, limit=2)
    if model_visual_prompt:
        concepts = [re.sub(r"\s+", " ", model_visual_prompt).strip()[:360]]
    if not concepts:
        english_words = re.findall(r"[A-Za-z]{3,}", (script or "")[:500])
        subject = "a realistic educational scene in Bangladesh"
        if english_words:
            subject += " related to " + " ".join(english_words[:8])
        concepts = [subject]
    subject = " and ".join(concepts)
    text = (script or "").lower()
    technology_context = any(_contains_visual_term(text, term) for term in (
        "মোবাইল", "ফোন", "ইন্টারনেট", "প্রযুক্তি", "কম্পিউটার", "অ্যাপ", "স্ক্রিন রিডার",
        "টকব্যাক", "smartphone", "screen reader", "talkback", "accessibility", "mobile app"
    ))
    geography_context = any(_contains_visual_term(text, term) for term in (
        "মানচিত্র", "বিশ্ব মানচিত্র", "ভূগোল", "পৃথিবীর মানচিত্র", "world map", "globe", "atlas", "geography"
    ))
    if technology_context and not geography_context:
        exclusions = (
            " For a technology or screen-reader scene, show a real person using a smartphone "
            "with an accessibility feature; absolutely do not show a world map, globe, atlas, "
            "geographic map, planet Earth, or abstract global-network visualization."
        )
    else:
        exclusions = (            " Do not show maps, globes, atlases, or geographic diagrams unless the scene explicitly discusses geography or maps."
        )
    return (
        "One coherent documentary photograph, vertical 9:16, for a Bangladeshi educational video. "
        "Depict the exact real-world subject and physical action stated in this scene: " + subject + ". "
        + exclusions +
        "The main subject must be large, recognizable, in focus, and visibly doing the described action; "
        "show the actual named object, person, place, or activity rather than a symbolic substitute. "
        "Prefer a believable real photograph with natural human proportions, authentic materials, "
        "specific environmental details, natural light, and a clear camera viewpoint. "
        "For abstract ideas, show a plausible real human situation that communicates the idea; "
        "never substitute mountains, sunrise, generic scenery, icons, stick figures, cartoons, "
        "vector art, clip art, 3D icons, diagrams, or decorative shapes for a concrete narrated subject. "
        "Use only details supported by the narration and its neighboring context. "
        "One scene, one main action, no unrelated topic collage. "
        "No text, no captions, no letters, no logos, no watermark."
    )[:1100]


def find_pollinations_image(script: str, folder: Path, model_visual_prompt: Optional[str] = None):
    """Try Pollinations' free no-account classic image endpoint before quota-limited Spaces."""
    prompt = (
        "Create an original photorealistic vertical 9:16 video scene. Subject: "
        + _english_visual_prompt(script, model_visual_prompt)
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


# Avoid repeatedly hammering public free image services after quota/payment/rate-limit
# failures. This cooldown is process-local and never stores credentials or user content.
IMAGE_PROVIDER_COOLDOWN_UNTIL = {}
IMAGE_PROVIDER_COOLDOWN_SECONDS = 900
IMAGE_PROVIDER_COOLDOWN_LOCK = threading.Lock()


def _decode_cloudflare_image_response(image_bytes: bytes, content_type: str = ""):
    """Decode either raw image bytes or Workers AI JSON containing a base64 image."""
    if "json" in (content_type or "").lower() or image_bytes.lstrip().startswith(b"{"):
        try:
            envelope = json.loads(image_bytes.decode("utf-8"))
            result = envelope.get("result") or {}
            encoded = result.get("image") or envelope.get("image")
            if not isinstance(encoded, str) or not encoded.strip():
                raise ValueError("Cloudflare JSON response has no image field")
            encoded = encoded.split(",", 1)[1] if encoded.startswith("data:") and "," in encoded else encoded
            image_bytes = base64.b64decode(encoded, validate=True)
        except (UnicodeDecodeError, ValueError, TypeError, KeyError) as exc:
            raise ValueError("Could not decode Cloudflare base64 image response") from exc
    return image_bytes


def find_cloudflare_generated_image(script: str, folder: Path, model_visual_prompt: Optional[str] = None):
    """Try Cloudflare Workers AI image models on the configured account's free allocation."""
    account_id = os.getenv("CLOUDFLARE_ACCOUNT_ID", "").strip()
    api_token = os.getenv("CLOUDFLARE_AI_API_TOKEN", os.getenv("CLOUDFLARE_API_TOKEN", "")).strip()
    if not account_id or not api_token:
        return None, ""
    prompt = _english_visual_prompt(script, model_visual_prompt)
    models = [
        item.strip() for item in os.getenv(
            "CLOUDFLARE_IMAGE_MODELS",
            "@cf/black-forest-labs/flux-1-schnell,@cf/lykon/dreamshaper-8-lcm,@cf/bytedance/stable-diffusion-xl-lightning"
        ).split(",") if item.strip()
    ]
    for model in list(dict.fromkeys(models)):
        provider_key = "Cloudflare-Image-" + model
        with IMAGE_PROVIDER_COOLDOWN_LOCK:
            cooldown_until = IMAGE_PROVIDER_COOLDOWN_UNTIL.get(provider_key, 0)
        if cooldown_until > time.time():
            print(f"IMAGE_PROVIDER skipped={provider_key} reason=cooldown remaining_seconds={int(cooldown_until - time.time())}", flush=True)
            continue
        try:
            if model == "@cf/black-forest-labs/flux-1-schnell":
                model_inputs = {"prompt": prompt, "steps": 8}
            else:
                model_inputs = {"prompt": prompt, "width": 512, "height": 768, "num_steps": 4}
            body = json.dumps(model_inputs).encode("utf-8")
            model_path = urllib.parse.quote(model, safe="@/-")
            request = urllib.request.Request(
                f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/{model_path}",
                data=body,
                headers={
                    "Authorization": "Bearer " + api_token,
                    "Content-Type": "application/json",
                    "Accept": "image/png, image/jpeg, application/octet-stream",
                    "User-Agent": "BanglaAIVoiceVideoMaker/0.8",
                },
                method="POST",
            )
            with urllib.request.urlopen(request, timeout=24) as response:
                image_bytes = response.read(8 * 1024 * 1024 + 1)
                content_type = response.headers.get("Content-Type", "").lower()
            if not 100 < len(image_bytes) <= 8 * 1024 * 1024:
                raise ValueError("Cloudflare returned an empty or oversized image")
            image_bytes = _decode_cloudflare_image_response(image_bytes, content_type)
            if not 100 < len(image_bytes) <= 8 * 1024 * 1024:
                raise ValueError("Cloudflare decoded an empty or oversized image")
            target = folder / ("cloudflare-" + re.sub(r"[^a-zA-Z0-9]+", "-", model).strip("-") + ".png")
            target.write_bytes(image_bytes)
            with Image.open(target) as check:
                if check.width < 80 or check.height < 80 or check.width * check.height > 4_000_000:
                    raise ValueError("Cloudflare image dimensions outside safe limits")
                check.verify()
            print("IMAGE_PROVIDER selected=" + provider_key, flush=True)
            return target, "AI-generated with Cloudflare Workers AI model " + model
        except Exception as exc:
            with IMAGE_PROVIDER_COOLDOWN_LOCK:
                IMAGE_PROVIDER_COOLDOWN_UNTIL[provider_key] = time.time() + IMAGE_PROVIDER_COOLDOWN_SECONDS
            print(f"IMAGE_PROVIDER failed provider={provider_key} cooldown_seconds={IMAGE_PROVIDER_COOLDOWN_SECONDS} error={type(exc).__name__}: {str(exc)[:150]}", flush=True)
    return None, ""


def find_generated_image(script: str, folder: Path, model_visual_prompt: Optional[str] = None):
    """Try free public image-generation providers in the actual production order."""
    if not AI_IMAGE_GENERATION_ENABLED:
        print("IMAGE_PROVIDER disabled=true", flush=True)
        return None, ""
    # The first two stages are intentionally fixed: Cloudflare account allocation,
    # then the no-account Pollinations endpoint. AI_IMAGE_PROVIDER_ORDER configures
    # only the subsequent Hugging Face Spaces; it does not reorder these stages.
    hf_order = ",".join(AI_IMAGE_PROVIDER_ORDER) or "default"
    print(
        "IMAGE_PROVIDER order=Cloudflare-Workers-AI-image-models>Pollinations-Flux>"
        f"Hugging-Face-Spaces[{hf_order}]",
        flush=True,
    )
    # Prefer the configured Cloudflare image models first: recent production logs
    # showed Pollinations frequently returning HTTP 400/402 or timing out. This avoids
    # wasting the job's visual-generation time on a provider that is already unreliable.
    cloudflare_image, cloudflare_credit = find_cloudflare_generated_image(script, folder, model_visual_prompt)
    if cloudflare_image:
        return cloudflare_image, cloudflare_credit
    with IMAGE_PROVIDER_COOLDOWN_LOCK:
        pollinations_cooldown_until = IMAGE_PROVIDER_COOLDOWN_UNTIL.get("Pollinations-Flux", 0)
    if pollinations_cooldown_until > time.time():
        print(f"IMAGE_PROVIDER skipped=Pollinations-Flux reason=cooldown remaining_seconds={int(pollinations_cooldown_until - time.time())}", flush=True)
        pollinations_image, pollinations_credit = None, ""
    else:
        pollinations_image, pollinations_credit = find_pollinations_image(script, folder, model_visual_prompt)
        if not pollinations_image:
            with IMAGE_PROVIDER_COOLDOWN_LOCK:
                IMAGE_PROVIDER_COOLDOWN_UNTIL["Pollinations-Flux"] = time.time() + IMAGE_PROVIDER_COOLDOWN_SECONDS
            print(f"IMAGE_PROVIDER cooldown provider=Pollinations-Flux seconds={IMAGE_PROVIDER_COOLDOWN_SECONDS}", flush=True)
    if pollinations_image:
        return pollinations_image, pollinations_credit
    from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
    prompt = (
        "Create an original, photorealistic vertical 9:16 image for a short educational video. "
        "Scene: " + _english_visual_prompt(script, model_visual_prompt) + ". "
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
        with IMAGE_PROVIDER_COOLDOWN_LOCK:
            cooldown_until = IMAGE_PROVIDER_COOLDOWN_UNTIL.get(provider_name, 0)
        if cooldown_until > time.time():
            remaining = int(cooldown_until - time.time())
            print(f"IMAGE_PROVIDER skipped={provider_name} reason=cooldown remaining_seconds={remaining}", flush=True)
            continue
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
            with IMAGE_PROVIDER_COOLDOWN_LOCK:
                IMAGE_PROVIDER_COOLDOWN_UNTIL[provider_name] = time.time() + IMAGE_PROVIDER_COOLDOWN_SECONDS
            print(f"IMAGE_PROVIDER timeout provider={provider_name} cooldown_seconds={IMAGE_PROVIDER_COOLDOWN_SECONDS}", flush=True)
        except Exception as exc:
            with IMAGE_PROVIDER_COOLDOWN_LOCK:
                IMAGE_PROVIDER_COOLDOWN_UNTIL[provider_name] = time.time() + IMAGE_PROVIDER_COOLDOWN_SECONDS
            print(f"IMAGE_PROVIDER failed provider={provider_name} cooldown_seconds={IMAGE_PROVIDER_COOLDOWN_SECONDS} error={type(exc).__name__}: {str(exc)[:180]}", flush=True)
        finally:
            executor.shutdown(wait=False, cancel_futures=True)
    return None, ""

def _vary_visual_prompt(base_prompt: Optional[str], variation_seed: int = 0):
    """Keep the scene subject fixed while varying camera composition between repeated slots."""
    prompt = (base_prompt or "").strip()
    if not prompt:
        return prompt
    compositions = (
        "Use a wide establishing documentary shot, showing the subject within its real environment.",
        "Use a medium eye-level documentary shot, showing the subject actively doing the stated task.",
        "Use an over-the-shoulder documentary angle, with the relevant object clearly visible.",
        "Use a side-angle documentary shot, capturing a different moment of the same activity.",
        "Use a detailed environmental shot, showing the subject and important surrounding objects together.",
        "Use a natural candid moment from slightly farther away, with a clear uncluttered background.",
        "Use a three-quarter camera angle and a different subject position within the frame.",
        "Use a contextual documentary photograph with foreground and background depth."
    )
    cue = compositions[max(0, int(variation_seed)) % len(compositions)]
    return (prompt[:850].rstrip() + " " + cue)[:1100]


def _distinct_scene_retry_prompt(base_prompt: Optional[str], scene_text: str):
    """Ask image providers for a fresh composition without changing the narrated subject."""
    prompt = (base_prompt or _english_visual_prompt(scene_text)).strip()
    instruction = (
        ". Create a clearly different photographic composition from previous scenes. "
        "Change camera angle, setting, subject position, lighting, and moment of action. "
        "Do not reuse the same stock-photo composition or background."
    )
    return (prompt[:850].rstrip() + instruction)[:1050]


def make_background(script: str, folder: Path, model_visual_prompt: Optional[str] = None, force_topic_graphic: bool = False, variation_seed: int = 0, scene_index: Optional[int] = None):
    # Small canvas is intentional: keep peak memory below Render Free's 512 MiB limit.
    width, height = 360, 640
    # Track the final source for this scene separately from provider-level attempt logs.
    scene_source = "topic_graphic" if force_topic_graphic else "unknown"
    scene_provider = ""
    # A forced topic graphic is the conservative fallback for a scene that has
    # already failed semantic review or repeated another image. Do not call an image
    # provider again here: that could return another unrelated photograph.
    if force_topic_graphic:
        source_image, credit = None, ""
        print("IMAGE_PROVIDER skipped=all reason=force_topic_graphic", flush=True)
    else:
        base_prompt = model_visual_prompt or _english_visual_prompt(script)
        # Every visual slot gets a distinct photographic composition, even when a long
        # sentence is intentionally repeated to fill the selected image interval.
        retry_prompt = _vary_visual_prompt(base_prompt, variation_seed)
        source_image, credit = find_generated_image(script, folder, retry_prompt)
    if source_image:
        scene_source = "ai_generated"
        match = re.search(r"AI-generated with ([A-Za-z0-9_.-]+)", str(credit or ""))
        scene_provider = match.group(1)[:48] if match else "provider_unspecified"
    if not source_image and not force_topic_graphic and ALLOW_LICENSED_IMAGE_FALLBACK:
        source_image, credit = find_contextual_image(script, folder, model_visual_prompt or base_prompt)
        if source_image:
            scene_source = "licensed_contextual"
            scene_provider = "openverse_or_wikimedia"
    elif not source_image:
        print("IMAGE_PROVIDER all_ai_models_failed licensed_fallback=disabled", flush=True)
    if source_image:
        try:
            with Image.open(source_image) as source:
                image = ImageOps.fit(source.convert("RGB"), (width, height), method=Image.Resampling.BILINEAR)
            # Reject technically valid but visually blank/near-black generated images.
            sample = image.resize((24, 42), Image.Resampling.BILINEAR)
            pixels = list(sample.getdata())
            luminance = [(r * 299 + g * 587 + b * 114) / 1000 for r, g, b in pixels]
            mean_luma = sum(luminance) / max(1, len(luminance))
            variance = sum((value - mean_luma) ** 2 for value in luminance) / max(1, len(luminance))
            if mean_luma < 18 or (mean_luma < 32 and variance < 25):
                raise ValueError("provider returned blank or near-black image")
            # Keep real photos bright enough to recognize behind captions.
            overlay = Image.new("RGBA", (width, height), (3, 13, 28, 40))
            image = Image.alpha_composite(image.convert("RGBA"), overlay).convert("RGB")
        except Exception as exc:
            print(f"IMAGE_PROVIDER rejected_scene reason={type(exc).__name__}: {str(exc)[:100]} fallback=licensed_image_then_topic_graphic", flush=True)
            source_image = None
            # If an AI image is corrupt or nearly black, try a contextual licensed photo
            # before falling back to a vector illustration. The previous flow skipped this
            # fallback because the initial provider lookup had already returned a file.
            if ALLOW_LICENSED_IMAGE_FALLBACK:
                fallback_image, fallback_credit = find_contextual_image(script, folder, model_visual_prompt or base_prompt)
                if fallback_image:
                    try:
                        with Image.open(fallback_image) as fallback_source:
                            fallback_render = ImageOps.fit(fallback_source.convert("RGB"), (width, height), method=Image.Resampling.BILINEAR)
                        fallback_sample = fallback_render.resize((24, 42), Image.Resampling.BILINEAR)
                        fallback_pixels = list(fallback_sample.getdata())
                        fallback_luminance = [(r * 299 + g * 587 + b * 114) / 1000 for r, g, b in fallback_pixels]
                        fallback_mean = sum(fallback_luminance) / max(1, len(fallback_luminance))
                        fallback_variance = sum((value - fallback_mean) ** 2 for value in fallback_luminance) / max(1, len(fallback_luminance))
                        if fallback_mean < 18 or (fallback_mean < 32 and fallback_variance < 25):
                            raise ValueError("licensed fallback image is blank or near-black")
                        fallback_overlay = Image.new("RGBA", (width, height), (3, 13, 28, 25))
                        image = Image.alpha_composite(fallback_render.convert("RGBA"), fallback_overlay).convert("RGB")
                        source_image, credit = fallback_image, fallback_credit
                        scene_source = "licensed_contextual_after_rejected_ai"
                        scene_provider = "openverse_or_wikimedia"
                        print("IMAGE_PROVIDER selected=licensed_fallback_after_rejected_ai", flush=True)
                    except Exception as fallback_exc:
                        print(f"IMAGE_PROVIDER rejected_licensed_fallback error={type(fallback_exc).__name__}: {str(fallback_exc)[:100]}", flush=True)
                        source_image = None
    if source_image:
        provider_field = f" provider={scene_provider}" if scene_provider else ""
        print(f"IMAGE_SCENE_SOURCE index={scene_index if scene_index is not None else 'unknown'} source={scene_source}{provider_field}", flush=True)
    else:
        scene_source = "topic_graphic"
        scene_provider = ""
        print(f"IMAGE_SCENE_SOURCE index={scene_index if scene_index is not None else 'unknown'} source=topic_graphic" + (" reason=duplicate_image" if force_topic_graphic else " reason=provider_unavailable"), flush=True)
    if not source_image:
        # Distinct topic-aware vector fallback: never reuse the same generic blue card
        # for every scene when free image-generation providers are unavailable.
        image = Image.new("RGB", (width, height))
        draw = ImageDraw.Draw(image)
        text = (script or "").lower()
        themes = [
            (("পরিশ্রম", "চেষ্টা", "সাফল্য", "বিশ্বাস", "স্বপ্ন", "আশা", "সাহস", "ভবিষ্যৎ", "ভবিষ্যত", "লক্ষ্য", "অধ্যবসায়", "অধ্যবসায়", "কঠিন পরিস্থিতি"), (35, 91, 75), "motivation"),
            (("ট্রেন", "রেল", "রেলগাড়ি", "রেলগাড়ি", "রেলওয়ে", "রেলওয়ে", "স্টেশন", "train", "railway", "station"), (44, 77, 110), "rail"),
            (("বাসস্ট্যান্ড", "বাসস্টপ", "যাত্রীবাহী বাস", "বাস", "বাসে", "বাসের", "bus stop", "city bus"), (45, 91, 126), "bus"),
            (("ক্রিকেট", "ব্যাটসম্যান", "বোলার", "স্টেডিয়াম", "cricket", "football", "ফুটবল"), (22, 91, 65), "sport"),
            (("রান্না", "খাবার", "রেসিপি", "খাদ্য", "cooking", "food"), (150, 76, 31), "food"),
            (("নদী", "সমুদ্র", "ভ্রমণ", "পাহাড়", "পর্যটন", "travel", "river", "sea"), (25, 95, 135), "travel"),
            (("বিজ্ঞান", "মহাকাশ", "গ্রহ", "পরমাণু", "science", "space"), (56, 47, 123), "science"),
            (("ইতিহাস", "ঐতিহাসিক", "রাজা", "যুদ্ধ", "history"), (119, 75, 42), "history"),
            (("ইসলাম", "মসজিদ", "নামাজ", "কোরআন", "আল্লাহ", "islam"), (31, 104, 81), "faith"),
            (("মোবাইল", "ফোন", "প্রযুক্তি", "কম্পিউটার", "অ্যাপ", "technology", "smartphone"), (30, 72, 125), "technology"),
            (("কৃষি", "কৃষক", "ধান", "ফসল", "agriculture", "farm"), (65, 112, 43), "farm"),
            (("বই", "শিক্ষা", "স্কুল", "শিক্ষার্থী", "education", "book"), (95, 63, 128), "education"),
            (("বাংলাদেশ", "দেশ", "জাতীয়", "বাংলা", "bangladesh"), (24, 111, 73), "bangladesh"),
        ]
        theme = next(((keywords, color, name) for keywords, color, name in themes if any(_contains_visual_term(text, k) for k in keywords)), None)
        if theme:
            base_color, theme_name = theme[1], theme[2]
        else:
            # Stable per-scene variation for topics without a recognized keyword.
            seed = sum(ord(ch) for ch in text[:180])
            base_color = (35 + seed % 75, 45 + (seed // 3) % 75, 70 + (seed // 7) % 90)
            theme_name = "general"
        # Shift the scene palette enough to remain visibly distinct while preserving
        # the recognizable subject drawing for the selected topic.
        palette_shift = max(0, int(variation_seed))
        if palette_shift:
            base_color = tuple(
                max(0, min(255, channel + ((palette_shift * 83 + axis * 71) % 201) - 100))
                for axis, channel in enumerate(base_color)
            )
        for y in range(height):
            ratio = y / max(1, height - 1)
            color = tuple(max(0, min(255, int(channel * (0.72 + ratio * 0.48)))) for channel in base_color)
            draw.line((0, y, width, y), fill=color)
        # A large, legible subject symbol gives the fallback a scene-specific composition.
        if theme_name == "motivation":
            # Use several distinct human-action illustrations so fallback scenes do
            # not become the same sun-and-mountain card throughout a narration.
            variant = max(0, int(variation_seed)) % 3
            if variant == 0:
                # A person climbing real-looking steps toward a clear destination.
                draw.ellipse((238, 82, 322, 166), fill=(255, 211, 112))
                draw.polygon([(0, 390), (95, 300), (175, 365), (260, 265), (360, 345), (360, 520), (0, 520)], fill=(53, 124, 104))
                for step in range(5):
                    y = 480 - step * 43
                    x = 24 + step * 48
                    draw.rectangle((x, y, x + 88, y + 25), fill=(220, 194, 143), outline=(245, 229, 195), width=3)
                draw.ellipse((178, 218, 218, 258), fill=(29, 35, 39))
                draw.line((198, 258, 193, 342), fill=(29, 35, 39), width=17)
                draw.line((195, 282, 158, 315), fill=(29, 35, 39), width=11)
                draw.line((196, 282, 232, 300), fill=(29, 35, 39), width=11)
                draw.line((193, 340, 164, 382), fill=(29, 35, 39), width=12)
                draw.line((194, 340, 224, 375), fill=(29, 35, 39), width=12)
            elif variant == 1:
                # A learner or worker concentrating at a desk: effort and practice.
                draw.rectangle((0, 430, 360, 640), fill=(74, 83, 104))
                draw.rectangle((38, 385, 322, 410), fill=(177, 128, 82))
                draw.rectangle((62, 410, 78, 575), fill=(113, 78, 54))
                draw.rectangle((282, 410, 298, 575), fill=(113, 78, 54))
                draw.ellipse((135, 170, 225, 260), fill=(30, 36, 43))
                draw.polygon([(124, 255), (236, 255), (270, 390), (92, 390)], fill=(38, 91, 125))
                draw.line((160, 300, 125, 378), fill=(30, 36, 43), width=16)
                draw.line((208, 300, 246, 378), fill=(30, 36, 43), width=16)
                draw.rectangle((108, 350, 250, 377), fill=(242, 229, 193), outline=(255, 255, 255), width=3)
                draw.line((145, 360, 215, 360), fill=(80, 95, 105), width=3)
                draw.rectangle((258, 280, 290, 365), fill=(24, 30, 42), outline=(235, 240, 245), width=4)
                draw.rectangle((265, 290, 283, 345), fill=(110, 184, 207))
            else:
                # A person walking forward on a road toward the morning light.
                draw.ellipse((238, 82, 322, 166), fill=(255, 211, 112))
                draw.polygon([(0, 350), (120, 290), (240, 350), (360, 290), (360, 640), (0, 640)], fill=(42, 112, 91))
                draw.polygon([(130, 640), (170, 370), (205, 370), (270, 640)], fill=(92, 96, 100))
                draw.line((187, 410, 190, 470), fill=(245, 229, 195), width=5)
                draw.line((178, 520, 170, 570), fill=(245, 229, 195), width=5)
                draw.ellipse((162, 225, 202, 265), fill=(29, 35, 39))
                draw.line((182, 265, 190, 365), fill=(29, 35, 39), width=17)
                draw.line((185, 292, 145, 335), fill=(29, 35, 39), width=11)
                draw.line((188, 292, 226, 325), fill=(29, 35, 39), width=11)
                draw.line((190, 365, 155, 420), fill=(29, 35, 39), width=12)
                draw.line((190, 365, 230, 410), fill=(29, 35, 39), width=12)
        elif theme_name == "rail":
            # Simple train body, windows, wheels and tracks; no text or map-like graphics.
            draw.rectangle((42, 260, 318, 405), fill=(214, 222, 230), outline=(255, 255, 255), width=6)
            draw.rectangle((60, 285, 112, 340), fill=(49, 108, 153))
            draw.rectangle((126, 285, 178, 340), fill=(49, 108, 153))
            draw.rectangle((192, 285, 244, 340), fill=(49, 108, 153))
            draw.rectangle((258, 285, 298, 340), fill=(49, 108, 153))
            draw.ellipse((72, 382, 112, 422), fill=(25, 30, 38), outline=(230, 230, 230), width=4)
            draw.ellipse((238, 382, 278, 422), fill=(25, 30, 38), outline=(230, 230, 230), width=4)
            draw.line((0, 470, 360, 470), fill=(235, 224, 194), width=8)
            draw.line((0, 510, 360, 510), fill=(235, 224, 194), width=8)
            for rail_x in range(10, 360, 42):
                draw.line((rail_x, 455, rail_x + 20, 525), fill=(190, 167, 132), width=5)
        elif theme_name == "bus":
            draw.rounded_rectangle((48, 245, 312, 440), radius=22, fill=(228, 181, 55), outline=(255, 255, 255), width=6)
            draw.rectangle((68, 270, 292, 340), fill=(61, 128, 164))
            for window_x in (80, 132, 184, 236):
                draw.rectangle((window_x, 282, window_x + 42, 325), fill=(181, 221, 235))
            draw.rectangle((70, 355, 290, 405), fill=(212, 67, 53))
            draw.ellipse((78, 410, 128, 460), fill=(25, 30, 38), outline=(230, 230, 230), width=5)
            draw.ellipse((232, 410, 282, 460), fill=(25, 30, 38), outline=(230, 230, 230), width=5)
        elif theme_name == "sport":
            draw.ellipse((245, 160, 315, 230), fill=(232, 105, 49), outline=(255, 255, 255), width=4)
            draw.polygon([(65, 340), (92, 320), (235, 500), (212, 520)], fill=(225, 191, 125))
            draw.line((75, 350, 220, 505), fill=(255, 255, 255), width=5)
        elif theme_name == "food":
            draw.ellipse((45, 240, 315, 510), fill=(244, 229, 194), outline=(255, 255, 255), width=10)
            draw.ellipse((85, 280, 275, 470), fill=(206, 91, 40), outline=(255, 203, 112), width=5)
            for px, py in ((135, 330), (205, 360), (160, 415), (235, 420)):
                draw.ellipse((px, py, px+20, py+20), fill=(65, 132, 60))
        elif theme_name == "travel":
            draw.polygon([(0, 430), (90, 240), (155, 360), (235, 180), (360, 430)], fill=(184, 213, 224))
            draw.polygon([(0, 510), (115, 355), (210, 480), (300, 340), (360, 470), (360, 640), (0, 640)], fill=(35, 133, 111))
            draw.ellipse((250, 90, 310, 150), fill=(255, 214, 116))
        elif theme_name == "science":
            draw.ellipse((65, 245, 295, 475), outline=(220, 228, 255), width=8)
            draw.ellipse((135, 315, 225, 405), fill=(244, 187, 91))
            draw.ellipse((170, 220, 190, 240), fill=(255, 255, 255))
        elif theme_name == "history":
            draw.polygon([(50, 390), (180, 215), (310, 390)], fill=(218, 190, 142))
            draw.rectangle((75, 390, 285, 510), fill=(228, 207, 164))
            for px in (105, 165, 225):
                draw.rectangle((px, 410, px+25, 500), fill=(123, 82, 49))
        elif theme_name == "faith":
            draw.rectangle((70, 360, 290, 505), fill=(221, 208, 169))
            draw.rectangle((95, 300, 265, 360), fill=(221, 208, 169))
            draw.arc((110, 225, 250, 365), 180, 360, fill=(255, 225, 145), width=10)
            draw.line((180, 190, 180, 225), fill=(255, 225, 145), width=7)
        elif theme_name == "technology":
            draw.rounded_rectangle((105, 190, 255, 475), radius=24, fill=(20, 25, 38), outline=(231, 240, 255), width=7)
            draw.rounded_rectangle((120, 220, 240, 430), radius=10, fill=(97, 190, 220))
            draw.ellipse((166, 445, 194, 465), fill=(231, 240, 255))
        elif theme_name == "farm":
            draw.ellipse((245, 95, 310, 160), fill=(255, 217, 114))
            for y in (380, 425, 470, 515):
                draw.arc((-50, y-50, 410, y+90), 5, 175, fill=(218, 228, 136), width=12)
            draw.line((95, 370, 135, 300, 170, 370), fill=(235, 226, 180), width=8)
        elif theme_name == "education":
            draw.polygon([(55, 300), (180, 245), (305, 300), (180, 355)], fill=(236, 214, 151))
            draw.polygon([(100, 325), (100, 420), (180, 465), (260, 420), (260, 325), (180, 370)], fill=(240, 234, 207))
            draw.line((180, 355, 180, 465), fill=(145, 106, 65), width=5)
        elif theme_name == "bangladesh":
            draw.ellipse((65, 230, 295, 460), fill=(20, 106, 73), outline=(255, 255, 255), width=5)
            draw.ellipse((135, 285, 225, 375), fill=(220, 42, 55))
        else:
            draw.ellipse((225, 95, 310, 180), fill=(255, 220, 135))
            draw.polygon([(0, 490), (95, 350), (170, 445), (265, 315), (360, 455), (360, 640), (0, 640)], fill=tuple(max(0, c-18) for c in base_color))
        # Keep fallback artwork clean; avoid floating decorative circles and lines.

    # Keep the visual background clean: narration text belongs only in the timed caption layer.
    # Do not burn the script, app title, or provider credits into every background image.
    target = folder / "background.png"
    image.save(target, optimize=True)
    try:
        (folder / "scene-source.json").write_text(
            json.dumps({"source": scene_source, "provider": scene_provider}, ensure_ascii=False),
            encoding="utf-8",
        )
    except Exception as exc:
        print(f"IMAGE_SCENE_SOURCE metadata_write_failed error={type(exc).__name__}", flush=True)
    return target

def _split_script_into_scenes(script: str, max_scenes: Optional[int] = None, target_words: int = 8):
    """Split narration into meaningful sentence-sized scenes without losing words."""
    text = (script or "").strip()
    if not text:
        return ["বাংলা ভিডিও"]

    paragraphs = [part.strip() for part in re.split(r"\n\s*\n+", text) if part.strip()]
    if not paragraphs:
        paragraphs = [text]

    chunks = []
    # Preserve sentence context: fixed eight-word cuts can separate a subject
    # from its action and leave the visual planner with incomplete information.
    max_sentence_words = max(4, target_words * 2)
    for paragraph in paragraphs:
        sentences = [part.strip() for part in re.split(r"(?<=[.!?।;])\s+", paragraph) if part.strip()]
        if not sentences:
            sentences = [paragraph]
        current_sentences = []
        current_word_count = 0

        def flush_current():
            nonlocal current_sentences, current_word_count
            if current_sentences:
                chunks.append(" ".join(current_sentences))
                current_sentences = []
                current_word_count = 0

        for sentence in sentences:
            words = sentence.split()
            if len(words) > max_sentence_words:
                flush_current()
                for offset in range(0, len(words), max_sentence_words):
                    chunks.append(" ".join(words[offset:offset + max_sentence_words]))
                continue
            if current_sentences and current_word_count + len(words) > max_sentence_words:
                flush_current()
            current_sentences.append(sentence)
            current_word_count += len(words)
        flush_current()

    if not chunks:
        chunks = [text]
    if max_scenes is not None and max_scenes > 0 and len(chunks) > max_scenes:
        # Optional compatibility path for callers that explicitly request a scene cap.
        all_words = [chunk.split() for chunk in chunks]
        total_words = sum(len(words) for words in all_words)
        target_size = max(1, (total_words + max_scenes - 1) // max_scenes)
        merged = []
        current = []
        remaining_scenes = max_scenes
        remaining_words = total_words
        for words in all_words:
            current.extend(words)
            remaining_words -= len(words)
            should_close = (
                len(merged) < max_scenes - 1
                and len(current) >= target_size
                and remaining_words > 0
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


def _scene_images_too_similar(first: Path, second: Path) -> bool:
    """Detect repeated provider photos cheaply at thumbnail size."""
    try:
        with Image.open(first) as first_image, Image.open(second) as second_image:
            a = list(first_image.convert("RGB").resize((24, 42), Image.Resampling.BILINEAR).getdata())
            b = list(second_image.convert("RGB").resize((24, 42), Image.Resampling.BILINEAR).getdata())
        if len(a) != len(b) or not a:
            return False
        difference = sum(abs(ac - bc) for ap, bp in zip(a, b) for ac, bc in zip(ap, bp)) / (len(a) * 3)
        return difference < 12.0
    except Exception as exc:
        print(f"IMAGE_SCENE compare_failed error={type(exc).__name__}", flush=True)
        return False


def _visual_scenes_for_interval(scenes, duration: float, interval: int, max_scenes: Optional[int] = None):
    """Allocate image slots from media duration; no fixed default image-count ceiling."""
    clean_scenes = [re.sub(r"\s+", " ", str(scene or "")).strip() for scene in scenes or []]
    clean_scenes = [scene for scene in clean_scenes if scene]
    if not clean_scenes:
        return ["বাংলা ভিডিও"]
    try:
        seconds = max(0.1, float(duration))
        cadence = int(interval)
        cap = max(1, int(max_scenes)) if max_scenes not in (None, 0, "0", "") else None
    except (TypeError, ValueError):
        cap = None
    if cadence not in (3, 5, 10, 15, 20):
        cadence = 5
    target_count = max(1, int(math.ceil(seconds / cadence)))
    if cap is not None:
        target_count = min(cap, target_count)
    if len(clean_scenes) >= target_count:
        if len(clean_scenes) == target_count:
            return clean_scenes
        if target_count == 1:
            return [clean_scenes[0]]
        indices = sorted({round(i * (len(clean_scenes) - 1) / (target_count - 1)) for i in range(target_count)})
        return [clean_scenes[i] for i in indices]

    # Give every sentence one slot, then distribute remaining slots by sentence
    # length. Repeating a complete sentence keeps its subject and context intact;
    # the per-slot variation seed can create a different composition for each.
    weights = [max(1, len(re.findall(r"\S+", scene))) for scene in clean_scenes]
    allocations = [1] * len(clean_scenes)
    remaining = target_count - len(clean_scenes)
    total_weight = sum(weights)
    exact = [remaining * weight / total_weight for weight in weights]
    whole = [int(value) for value in exact]
    allocations = [base + extra for base, extra in zip(allocations, whole)]
    leftover = remaining - sum(whole)
    order = sorted(range(len(clean_scenes)), key=lambda index: (exact[index] - whole[index], weights[index], -index), reverse=True)
    for index in order[:leftover]:
        allocations[index] += 1

    result = []
    for scene, count in zip(clean_scenes, allocations):
        result.extend([scene] * count)
    return result[:target_count]



def _parse_scene_match_response(raw):
    """Normalize common vision-model response shapes into a conservative match result."""
    if isinstance(raw, dict):
        candidate = raw
    else:
        text = str(raw or "").strip()
        object_match = re.search(r"\{.*?\}", text, flags=re.S)
        candidate = None
        if object_match:
            try:
                parsed = json.loads(object_match.group(0))
                if isinstance(parsed, dict):
                    candidate = parsed
            except (TypeError, ValueError):
                candidate = None
        if candidate is None:
            normalized = re.sub(r"\s+", " ", text).strip().lower()
            label = re.fullmatch(r"(match|mismatch)[.!]?", normalized)
            if label:
                return {
                    "match": label.group(1) == "match",
                    "confidence": 0.70,
                    "description": "",
                    "reason": "Vision model returned a strict scene-match label",
                }
            match_word = re.search(r"\bmatch(?:es)?\s*[:=]?\s*(true|false|yes|no)\b", normalized)
            confidence_word = re.search(r"\bconfidence\s*[:=]?\s*(0(?:\.\d+)?|1(?:\.0+)?)", normalized)
            if match_word:
                return {
                    "match": match_word.group(1) in ("true", "yes"),
                    "confidence": float(confidence_word.group(1)) if confidence_word else 0.65,
                    "description": "",
                    "reason": text[:180],
                }
            return None
    match_value = candidate.get("match")
    if isinstance(match_value, str):
        value = match_value.strip().lower()
        if value in ("match", "true", "yes"):
            match_value = True
        elif value in ("mismatch", "false", "no"):
            match_value = False
    if not isinstance(match_value, bool):
        return None
    try:
        confidence = float(candidate.get("confidence", 0.70))
    except (TypeError, ValueError):
        confidence = 0.70
    if not 0.0 <= confidence <= 1.0:
        confidence = 0.0
    return {
        "match": match_value,
        "confidence": confidence,
        "description": str(candidate.get("description") or "")[:240],
        "reason": str(candidate.get("reason") or "")[:180],
    }


def _should_semantically_review_image_source(source: str):
    """Spend vision-review inference only on photographic AI or contextual images."""
    return str(source or "").strip() in (
        "ai_generated", "licensed_contextual", "licensed_contextual_after_rejected_ai"
    )


def _should_review_duplicate_retry(index: int, review_indices, source: str):
    """Review a replacement photo only when its scene is in the selected QA sample."""
    return index in review_indices and _should_semantically_review_image_source(source)


def _review_generated_image_against_scene(image_path: Path, narration: str, visual_prompt: Optional[str] = None):
    """Ask Moondream to inspect a generated image and judge whether it depicts this narration."""
    account_id = os.getenv("CLOUDFLARE_ACCOUNT_ID", "").strip()
    api_token = os.getenv("CLOUDFLARE_AI_API_TOKEN", os.getenv("CLOUDFLARE_API_TOKEN", "")).strip()
    if not account_id or not api_token or not image_path or not image_path.is_file():
        return None
    model = os.getenv("CLOUDFLARE_VISION_REVIEW_MODEL", "@cf/moondream/moondream3.1-9B-A2B").strip()
    try:
        with Image.open(image_path) as source:
            preview = source.convert("RGB")
            preview.thumbnail((448, 768), Image.Resampling.LANCZOS)
            buffer = io.BytesIO()
            preview.save(buffer, format="JPEG", quality=78, optimize=True)
        image_data = "data:image/jpeg;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")
        question = (
            "Compare the visible image with this exact scene. Narration: "
            + re.sub(r"\s+", " ", str(narration)).strip()[:420]
            + ". Intended visual: " + re.sub(r"\s+", " ", str(visual_prompt or "")).strip()[:300]
            + ". Reply with exactly one word: MATCH or MISMATCH. MATCH only if the main visible "
            "subject and action clearly depict the scene. Generic landscapes, icons, cartoons, "
            "abstract shapes, or unrelated objects are MISMATCH for a specific narrated subject."
        )
        model_path = urllib.parse.quote(model, safe="@/-")
        payload = {"task": "query", "image": image_data, "question": question}
        request = urllib.request.Request(
            f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/{model_path}",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": "Bearer " + api_token,
                "Content-Type": "application/json",
                "User-Agent": "BanglaAIVoiceVideoMaker/1.0",
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=18) as response:
            data = json.loads(response.read(180_000).decode("utf-8"))
        result = data.get("result") or {}
        if isinstance(result, dict):
            raw = (
                result.get("answer") or result.get("response") or result.get("description")
                or result.get("text") or result.get("output") or data.get("response") or ""
            )
        else:
            raw = result
        review = _parse_scene_match_response(raw)
        if not review:
            print("IMAGE_REVIEW unavailable reason=unstructured_vision_response", flush=True)
            return None
        confidence = review["confidence"]
        accepted = review["match"] and confidence >= 0.62
        description = re.sub(r"\s+", " ", review["description"]).strip()[:240]
        reason = re.sub(r"\s+", " ", review["reason"]).strip()[:180]
        print(
            f"IMAGE_REVIEW model={model} match={accepted} confidence={confidence:.2f} "
            f"description={description[:120]} reason={reason[:100]}",
            flush=True,
        )
        return {"match": accepted, "confidence": confidence, "description": description, "reason": reason}
    except Exception as exc:
        print(f"IMAGE_REVIEW unavailable model={model} error={type(exc).__name__}: {str(exc)[:140]}", flush=True)
        return None

def make_scene_backgrounds(script: str, folder: Path, progress_callback=None, duration: float = 0.0, scene_interval: int = 5):
    """Plan as many visual scenes as the duration and selected interval require."""
    scenes = _split_script_into_scenes(script, max_scenes=None, target_words=8)
    # Zero/unset means automatic duration-based planning with no fixed 38/48-image ceiling.
    # Operators may set a positive ceiling for constrained hosting environments.
    try:
        configured_limit = max(0, int(os.getenv("MAX_VISUAL_SCENES", "0")))
    except (TypeError, ValueError):
        configured_limit = 0
    max_visual_scenes = configured_limit or None
    visual_scenes = _visual_scenes_for_interval(scenes, duration, scene_interval, max_visual_scenes)
    # Prompts are batched in groups of eight; every narration scene is retained for subtitles/timing.
    if progress_callback:
        progress_callback(35, "ভিডিওর প্রতিটি দৃশ্যের জন্য উপযুক্ত ছবি পরিকল্পনা করা হচ্ছে।")
    visual_prompts = _plan_scene_visual_prompts(visual_scenes)
    backgrounds = []
    semantic_review = {
        "reviewed": 0, "matched": 0, "mismatched": 0,
        "retried": 0, "retry_matched": 0, "retry_mismatched": 0, "unavailable": 0,
        "duplicate_retry_reviewed": 0, "duplicate_retry_matched": 0,
        "duplicate_retry_mismatched": 0, "duplicate_retry_unavailable": 0,
        "image_sources": {"ai_generated": 0, "licensed_contextual": 0, "topic_graphic": 0, "unknown": 0},
    }
    try:
        review_limit = max(0, int(os.getenv("IMAGE_SEMANTIC_REVIEW_MAX_SCENES", "12")))
    except (TypeError, ValueError):
        review_limit = 12
    review_indices = set()
    if review_limit > 0 and len(visual_scenes) <= review_limit:
        review_indices = set(range(len(visual_scenes)))
    elif review_limit > 0 and len(visual_scenes) > review_limit:
        review_indices = {
            round(slot * (len(visual_scenes) - 1) / max(1, review_limit - 1))
            for slot in range(review_limit)
        }
    for index, scene_text in enumerate(visual_scenes):
        if progress_callback:
            percent = 36 + int(4 * index / max(1, len(visual_scenes)))
            progress_callback(percent, f"দৃশ্যের ছবি তৈরি হচ্ছে: {index + 1}/{len(visual_scenes)}। বিনামূল্যের ছবি সেবার উত্তর আসতে সময় লাগতে পারে।")
        scene_dir = folder / f"scene-{index:02d}"
        scene_dir.mkdir(parents=True, exist_ok=True)
        print(f"IMAGE_SCENE index={index + 1}/{len(scenes)} words={len(scene_text.split())}", flush=True)
        scene_visual_prompt = visual_prompts[index] if visual_prompts else None
        background = make_background(scene_text, scene_dir, scene_visual_prompt, variation_seed=index, scene_index=index + 1)
        # Inspect an evenly distributed sample only when it is a real generated or
        # contextual photograph. Local topic graphics cannot pass a vision comparison,
        # so reviewing them would waste the limited vision-model allocation.
        source_info_for_review = {}
        try:
            source_info_for_review = json.loads((scene_dir / "scene-source.json").read_text(encoding="utf-8"))
        except Exception:
            pass
        review_source = str(source_info_for_review.get("source") or "unknown")
        if index in review_indices and _should_semantically_review_image_source(review_source):
            semantic_review["reviewed"] += 1
            review = _review_generated_image_against_scene(background, scene_text, scene_visual_prompt)
            if review is None:
                semantic_review["unavailable"] += 1
            elif review["match"]:
                semantic_review["matched"] += 1
            else:
                semantic_review["mismatched"] += 1
                semantic_review["retried"] += 1
                print(f"IMAGE_REVIEW action=regenerate scene={index + 1}", flush=True)
                correction = (
                    (scene_visual_prompt or _english_visual_prompt(scene_text))
                    + " Strictly depict this exact narration: " + scene_text[:220]
                    + ". Avoid the rejected image content: " + review["description"][:140]
                    + ". Use a clearly recognizable real-life subject and action."
                )[:1050]
                retry_background = make_background(
                    scene_text, scene_dir, correction, variation_seed=index + len(visual_scenes),
                    scene_index=index + 1
                )
                retry_review = _review_generated_image_against_scene(retry_background, scene_text, correction)
                if retry_review is None:
                    semantic_review["unavailable"] += 1
                    print(f"IMAGE_REVIEW action=replace_unverified_retry scene={index + 1}", flush=True)
                    background = make_background(
                        scene_text, scene_dir, force_topic_graphic=True,
                        variation_seed=index, scene_index=index + 1
                    )
                elif retry_review["match"]:
                    semantic_review["retry_matched"] += 1
                    background = retry_background
                    print(f"IMAGE_REVIEW action=accepted_retry scene={index + 1}", flush=True)
                else:
                    semantic_review["retry_mismatched"] += 1
                    print(f"IMAGE_REVIEW action=replace_rejected_retry_with_topic_graphic scene={index + 1}", flush=True)
                    background = make_background(
                        scene_text, scene_dir, force_topic_graphic=True,
                        variation_seed=index, scene_index=index + 1
                    )
        elif index in review_indices:
            print(f"IMAGE_REVIEW skipped scene={index + 1} reason=non_photographic_source source={review_source}", flush=True)
        if any(_scene_images_too_similar(background, prior) for prior in backgrounds):
            print(f"IMAGE_SCENE repeated_image index={index + 1} action=try_new_photo_composition", flush=True)
            distinct_prompt = _distinct_scene_retry_prompt(scene_visual_prompt, scene_text)
            distinct_background = make_background(
                scene_text, scene_dir, distinct_prompt,
                variation_seed=index + len(visual_scenes) * 3 + 17,
                scene_index=index + 1
            )
            if any(_scene_images_too_similar(distinct_background, prior) for prior in backgrounds):
                print(f"IMAGE_SCENE repeated_image index={index + 1} action=use_topic_graphic_after_retry", flush=True)
                background = make_background(
                    scene_text, scene_dir, force_topic_graphic=True,
                    variation_seed=index, scene_index=index + 1
                )
            else:
                distinct_source_info = {}
                try:
                    distinct_source_info = json.loads((scene_dir / "scene-source.json").read_text(encoding="utf-8"))
                except Exception:
                    pass
                distinct_source = str(distinct_source_info.get("source") or "unknown")
                if _should_review_duplicate_retry(index, review_indices, distinct_source):
                    semantic_review["duplicate_retry_reviewed"] += 1
                    distinct_review = _review_generated_image_against_scene(
                        distinct_background, scene_text, distinct_prompt
                    )
                    if distinct_review is None:
                        semantic_review["duplicate_retry_unavailable"] += 1
                        print(f"IMAGE_REVIEW duplicate_retry=unavailable scene={index + 1} action=keep_distinct_photo", flush=True)
                        background = distinct_background
                    elif distinct_review["match"]:
                        semantic_review["duplicate_retry_matched"] += 1
                        print(f"IMAGE_REVIEW duplicate_retry=match scene={index + 1} action=accept", flush=True)
                        background = distinct_background
                    else:
                        semantic_review["duplicate_retry_mismatched"] += 1
                        print(f"IMAGE_REVIEW duplicate_retry=mismatch scene={index + 1} action=use_topic_graphic", flush=True)
                        background = make_background(
                            scene_text, scene_dir, force_topic_graphic=True,
                            variation_seed=index, scene_index=index + 1
                        )
                else:
                    background = distinct_background
                    print(f"IMAGE_SCENE repeated_image index={index + 1} action=accepted_new_composition", flush=True)
        try:
            source_info = json.loads((scene_dir / "scene-source.json").read_text(encoding="utf-8"))
            source_name = str(source_info.get("source") or "unknown")
            if source_name not in semantic_review["image_sources"]:
                source_name = "unknown"
        except Exception:
            source_name = "unknown"
        semantic_review["image_sources"][source_name] += 1
        backgrounds.append(background)
    print(f"IMAGE_SCENE unique_backgrounds={len(backgrounds)} total_narration_scenes={len(scenes)} interval={scene_interval}s duration={duration:.1f}s visual_budget={max_visual_scenes or 'duration_based'}", flush=True)
    if progress_callback:
        progress_callback(40, f"{len(backgrounds)}টি দৃশ্যের ছবি প্রস্তুত হয়েছে।")
    return backgrounds, scenes, semantic_review

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


def _scene_index_to_background_index(scene_index: int, scene_count: int, background_count: int) -> int:
    """Map a full-script scene index to its representative image without collapsing late scenes."""
    if background_count <= 1 or scene_count <= 1:
        return 0
    scene_index = max(0, min(int(scene_index), scene_count - 1))
    return min(background_count - 1, int(scene_index * background_count / scene_count))


def make_caption_frames(script: str, duration: float, background: Path, folder: Path, caption_offset: float = 0.0, audio_path: Optional[Path] = None, job_id: Optional[str] = None, scene_interval: int = 5, visual_scene_texts=None):
    """Render small Pillow caption cards with per-word highlighting, avoiding FFmpeg's memory-heavy libass filter."""
    frame_dir = folder / "caption-frames"
    frame_dir.mkdir(parents=True, exist_ok=True)
    background_paths = background if isinstance(background, (list, tuple)) else [background]
    bases = []
    for background_path in background_paths:
        with Image.open(background_path) as source:
            bases.append(source.convert("RGB").resize((360, 640), Image.Resampling.LANCZOS))

    sentences = _split_script_into_scenes(script, max_scenes=None)
    sentence_words = [re.findall(r"\S+", sentence) for sentence in sentences]
    total_words = max(1, sum(len(words) for words in sentence_words))
    sentence_spans = sentence_timing_spans(audio_path, sentences, duration)
    # The interval controls scene changes. Long scripts retain all narration segments; representative
    # backgrounds may be sampled to stay within free-tier time and memory limits.
    interval = scene_interval if scene_interval in (3, 5, 10, 15, 20) else 5
    slot_count = max(1, int(math.ceil(duration / interval)))
    all_words = re.findall(r"\S+", script or "")
    words_per_slot = max(1, int(math.ceil(len(all_words) / slot_count)))
    slot_texts = [" ".join(all_words[i:i + words_per_slot]) for i in range(0, len(all_words), words_per_slot)]
    scene_texts = list(visual_scene_texts or sentences)
    # Keep the visual sequence aligned with narration order. Keyword-score matching
    # alone can jump to a later scene when a broad word appears repeatedly.
    # Map each timed slot to the scene covering the same share of the script.
    scene_weights = [max(1, len(re.findall(r"\S+", item or ""))) for item in scene_texts]
    scene_edges = []
    cumulative = 0
    for weight in scene_weights:
        cumulative += weight
        scene_edges.append(cumulative)
    total_scene_words = max(1, cumulative)
    scene_concepts = [_matched_visual_concepts(item, limit=2) for item in scene_texts]
    slot_backgrounds = []
    for slot_index in range(slot_count):
        slot_text = slot_texts[min(slot_index, len(slot_texts) - 1)] if slot_texts else script
        if len(bases) <= 1 or not scene_edges:
            chosen = 0
        else:
            # Slot center avoids switching early at scene boundaries.
            slot_center = min(total_scene_words - 1, int((slot_index + 0.5) * total_scene_words / slot_count))
            chosen = next((i for i, edge in enumerate(scene_edges) if slot_center < edge), len(scene_edges) - 1)
        # Preserve chronology, but allow a nearby scene when it clearly matches the slot topic.
        slot_concepts = _matched_visual_concepts(slot_text, limit=2)
        if slot_concepts:
            current = scene_concepts[chosen] if chosen < len(scene_concepts) else []
            if not any(concept in current for concept in slot_concepts):
                matching = [i for i, candidates in enumerate(scene_concepts)
                            if any(concept in candidates for concept in slot_concepts)]
                if matching:
                    nearest = min(matching, key=lambda i: abs(i - chosen))
                    if abs(nearest - chosen) <= 1:
                        # Keep the full narration-scene index here. Clamping it to the
                        # sampled-image count before scaling collapses late-script matches
                        # onto early images whenever there are more scenes than images.
                        chosen = nearest
        # The chosen scene index maps to a representative image sampled across the full script.
        base_index = _scene_index_to_background_index(chosen, len(scene_texts), len(bases))
        slot_backgrounds.append(base_index)
    print(f"VISUAL_TIMELINE interval_seconds={interval} slots={slot_count} unique_images={len(bases)} narration_scenes={len(scene_texts)}", flush=True)
    safe_offset = max(-max(0.0, duration - 0.1), min(max(0.0, duration - 0.1), caption_offset))
    font = load_font(25, True)
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
            panel.rounded_rectangle((14, 440, 346, 622), radius=18, fill=(0, 0, 0, 205), outline=(95, 170, 230, 220), width=2)
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
            max_width = 300
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
            y = 464 + max(0, (4 - len(visible_lines)) * 34)
            for line in visible_lines:
                x = 14
                for token, active in line:
                    color = (255, 224, 65) if active else (255, 255, 255)
                    draw.text((x, y), token, font=font, fill=color, stroke_width=1, stroke_fill=(0, 0, 0))
                    x += draw.textbbox((0, 0), token, font=font)[2] + draw.textbbox((0, 0), " ", font=font)[2]
                y += 34
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
        if mode == "audio" and not script.strip():
            def update_transcription_progress(progress, message):
                with LOCK:
                    if job_id in JOBS and JOBS[job_id].get("status") == "processing":
                        JOBS[job_id]["progress"] = progress
                        JOBS[job_id]["message"] = message
            if audio_path is None:
                raise RuntimeError("কথার অডিও নির্বাচন করুন।")
            script = transcribe_uploaded_audio(audio_path, folder, update_transcription_progress)
            print(f"TRANSCRIPTION_PROVIDER=Cloudflare-Whisper characters={len(script)}", flush=True)
        if mode == "clone":
            reference_audio = audio_path
            if reference_audio is None:
                raise RuntimeError("নিজের কণ্ঠের নমুনা অডিও নির্বাচন করুন।")
            try:
                def update_voice_progress(progress, message):
                    with LOCK:
                        if job_id in JOBS and JOBS[job_id].get("status") == "processing":
                            JOBS[job_id]["progress"] = progress
                            JOBS[job_id]["message"] = message
                update_voice_progress(12, "নিজের কণ্ঠ তৈরি হচ্ছে। ফ্রি কণ্ঠসেবা থেকে উত্তর আসতে কিছুটা সময় লাগতে পারে।")
                audio_path = synthesize_cloned_voice(script, reference_audio, folder, update_voice_progress)
            finally:
                try:
                    reference_audio.unlink(missing_ok=True)
                except Exception:
                    pass
        elif audio_path is None:
            audio_path = synthesize_mixed_speech(script, folder)
        duration = duration_of(audio_path)
        with LOCK:
            JOBS[job_id]["progress"] = 35
            JOBS[job_id]["message"] = "ভিডিওর পটভূমি ও সাবটাইটেল তৈরি হচ্ছে"
        print(f"VIDEO_STAGE job={job_id} stage=background_start", flush=True)
        def update_visual_progress(progress, message):
            with LOCK:
                if job_id in JOBS and JOBS[job_id].get("status") == "processing":
                    JOBS[job_id]["progress"] = max(JOBS[job_id].get("progress", 0), progress)
                    JOBS[job_id]["message"] = message
        backgrounds, visual_scene_texts, semantic_review = make_scene_backgrounds(script, folder, update_visual_progress, duration=duration, scene_interval=scene_interval)
        provider_order = ",".join(AI_IMAGE_PROVIDER_ORDER) or "none"
        licensed_fallback = "enabled" if ALLOW_LICENSED_IMAGE_FALLBACK else "disabled"
        print(
            f"VIDEO_STAGE job={job_id} stage=background_done scenes={len(backgrounds)} "
            f"interval={scene_interval}s ai_providers={provider_order} "
            f"licensed_image_fallback={licensed_fallback} topic_graphic_fallback=enabled",
            flush=True,
        )
        with LOCK:
            JOBS[job_id]["progress"] = 40
            JOBS[job_id]["message"] = "বাক্যভিত্তিক দৃশ্য ও পটভূমি তৈরি হয়েছে"
        print(f"VIDEO_STAGE job={job_id} stage=subtitles_start", flush=True)
        frame_list, frame_count = make_caption_frames(script, duration, backgrounds, folder, caption_offset, audio_path, job_id, scene_interval, visual_scene_texts)
        print(f"VIDEO_STAGE job={job_id} stage=subtitles_done frames={frame_count} method=pillow_word_highlight", flush=True)
        with LOCK:
            JOBS[job_id]["progress"] = 49
            JOBS[job_id]["message"] = "শব্দের সঙ্গে মিলিয়ে সাবটাইটেল তৈরি হয়েছে"
        output = folder / "video.mp4"
        # Pre-rendered caption images avoid FFmpeg/libass memory spikes on Render Free.
        vf = "scale=360:640:flags=lanczos,format=yuv420p"
        print(f"VIDEO_STAGE job={job_id} stage=ffmpeg_start duration={duration:.2f} size=360x640 fps=15 subtitles=pillow_word_highlight frames={frame_count}", flush=True)
        with LOCK:
            JOBS[job_id]["progress"] = 50
            JOBS[job_id]["message"] = "সাবটাইটেলসহ ভিডিও রেন্ডার হচ্ছে"
        run([
            "ffmpeg", "-y", "-filter_threads", "1", "-filter_complex_threads", "1",
            "-f", "concat", "-safe", "0", "-i", str(frame_list), "-i", str(audio_path),
            "-map", "0:v:0", "-map", "1:a:0", "-vf", vf, "-t", str(duration), "-r", "15",
            "-c:v", "libx264", "-threads", "1", "-preset", "ultrafast", "-crf", "27",
            "-c:a", "aac", "-b:a", "96k", "-threads", "1", "-shortest", "-movflags", "+faststart", str(output)
        ], 240)
        print(f"VIDEO_STAGE job={job_id} stage=ffmpeg_done", flush=True)
        with LOCK:
            JOBS[job_id].update(status="completed", progress=100, message="ভিডিও তৈরি হয়েছে", download_url=f"/api/jobs/{job_id}/download", duration=round(duration, 2), scene_count=len(backgrounds), narration_scene_count=len(visual_scene_texts), scene_interval_seconds=scene_interval, caption_frame_count=frame_count, semantic_review=semantic_review, script_characters=len(script), video_mode=mode, completed_at=time.time())
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
        "language_model_visual_planner": {
            "enabled": LANGUAGE_MODEL_VISUAL_PLANNER_ENABLED,
            "providers": ["Cloudflare Workers AI Free allocation when account ID and API token are configured", "local keyword fallback"],
            "default_model": os.getenv("CLOUDFLARE_AI_MODEL", "@cf/meta/llama-3.2-3b-instruct"),
            "requires_paid_service": False,
            "fallback_enabled": True,
        },
        "free_only": True,
    }


@app.get("/api/capabilities")
def capabilities():
    return {
        "language_input": ["বাংলা", "English", "Banglish"],
        "audio_understanding": {
            "audio_only_upload": True,
            "speech_to_text_model": "@cf/openai/whisper-large-v3-turbo",
            "provider": "Cloudflare Workers AI",
            "automatic_transcription_when_script_is_blank": True,
            "chunk_seconds": 120,
        },
        "video_generation": True,
        "scene_interval_seconds": [3, 5, 10, 15, 20],
        "scene_interval_default_seconds": 3,
        "max_concurrent_jobs": MAX_ACTIVE_JOBS,
        "job_retention_hours": round(JOB_RETENTION_SECONDS / 3600, 1),
        "scene_images": {
            "enabled": AI_IMAGE_GENERATION_ENABLED,
            "providers": [
                {"id": "flux", "name": "FLUX.1-schnell", "license": "Apache-2.0 model license; generated output is not guaranteed copyright-free"},
                {"id": "zimage", "name": "Z-Image-Turbo", "license": "Apache-2.0 model license; generated output is not guaranteed copyright-free"},
                {"id": "pollinations_flux", "name": "Pollinations Flux (free classic endpoint)", "license": "Hosted image service; free anonymous access and rate limits may change"},
                {"id": "cloudflare_ai_images", "name": "Cloudflare Workers AI image-model fallback chain", "license": "Uses configured Cloudflare account free allocation; requires account ID and API token"},
            ],
            "order": AI_IMAGE_PROVIDER_ORDER,
            "timeout_seconds": AI_IMAGE_PROVIDER_TIMEOUT,
            "automatic_fallback": True,
            "licensed_image_fallback": ALLOW_LICENSED_IMAGE_FALLBACK,
        },
        "language_model_visual_planner": {
            "enabled": LANGUAGE_MODEL_VISUAL_PLANNER_ENABLED,
            "default_model": os.getenv("CLOUDFLARE_AI_MODEL", "@cf/meta/llama-3.2-3b-instruct"),
            "providers": ["Cloudflare Workers AI model fallback chain (Llama, Qwen, Gemma when available)", "local keyword fallback"],
            "note": "Only the Cloudflare daily free allocation is used. The model chain tries alternatives when one fails. If credentials are absent, the quota is exhausted, or all models fail, local planning is used. No paid or credit-based fallback is enabled.",
        },
        "script_generation": {"available": False, "note": "Video creation uses the user's supplied script; the language model plans visuals and does not invent narration."},
        "free_only": True,
    }


@app.post("/api/jobs", status_code=202)
async def create_job(script: str = Form(""), mode: str = Form("auto"), audio: Optional[UploadFile] = File(None), voice_clone_consent: bool = Form(False), caption_offset: float = Form(0.0), scene_interval: int = Form(3)):
    script = script.strip()
    if mode not in ("auto", "audio", "clone"):
        raise HTTPException(400, "ভিডিও তৈরির পদ্ধতি সঠিক নয়।")
    if not script and not (mode == "audio" and audio is not None):
        raise HTTPException(400, "লেখা দিন অথবা অডিওসহ অডিও মোড নির্বাচন করুন।")
    if len(script) > MAX_SCRIPT_CHARS:
        raise HTTPException(413, f"লেখা সর্বোচ্চ {MAX_SCRIPT_CHARS} অক্ষরের হতে পারবে।")
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
        if len(script) > 3000:
            raise HTTPException(413, "নিজের কণ্ঠে একবারে সর্বোচ্চ ৩০০০ অক্ষর ব্যবহার করুন।")
    _cleanup_expired_jobs()
    job_id = uuid.uuid4().hex
    folder = WORK_DIR / job_id
    with LOCK:
        active_count = sum(
            1 for job in JOBS.values()
            if job.get("status") in ("uploading", "queued", "processing")
        )
        if active_count >= MAX_ACTIVE_JOBS:
            raise HTTPException(
                429,
                "আগের ভিডিও তৈরির কাজ এখনো চলছে। সেটি সম্পন্ন হলে নতুন ভিডিও তৈরি করুন।"
            )
        JOBS[job_id] = {
            "id": job_id, "status": "uploading", "progress": 0,
            "message": "অডিও ফাইল গ্রহণ করা হচ্ছে", "created_at": time.time()
        }
    audio_path = None
    try:
        folder.mkdir(parents=True, exist_ok=True)
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
                        raise HTTPException(413, f"অডিও ফাইল সর্বোচ্চ {MAX_AUDIO_MB} MB হতে পারবে।")
                    target.write(chunk)
    except HTTPException:
        with LOCK:
            JOBS.pop(job_id, None)
        shutil.rmtree(folder, ignore_errors=True)
        raise
    except Exception as exc:
        with LOCK:
            JOBS.pop(job_id, None)
        shutil.rmtree(folder, ignore_errors=True)
        raise HTTPException(400, "অডিও ফাইল পড়া বা সংরক্ষণ করা যায়নি। অন্য একটি ফাইল বেছে নিন।") from exc
    with LOCK:
        JOBS[job_id].update(status="queued", progress=0, message="অনুরোধ গ্রহণ করা হয়েছে")
    threading.Thread(target=render, args=(job_id, script, mode, audio_path, caption_offset, scene_interval), daemon=True).start()
    return {"id": job_id, "status": "queued", "status_url": f"/api/jobs/{job_id}", "download_url": f"/api/jobs/{job_id}/download"}


@app.get("/api/jobs/{job_id}")
def job_status(job_id: str):
    with LOCK:
        job = JOBS.get(job_id)
        if not job:
            raise HTTPException(404, "কাজটি পাওয়া যায়নি। সার্ভার পুনরায় চালু হলে অস্থায়ী কাজের তথ্য মুছে যেতে পারে।")
        return dict(job)


def _scene_interval_diagnostics(duration: float, image_count, interval):
    """Compare generated background count with the requested maximum image-change cadence."""
    try:
        seconds = float(duration)
        cadence = int(interval)
        count = int(image_count)
    except (TypeError, ValueError):
        return {"expected_images": None, "average_seconds_per_image": None, "warning": False}
    if seconds <= 0 or cadence <= 0 or count <= 0:
        return {
            "expected_images": max(1, int(math.ceil(seconds / cadence))) if seconds > 0 and cadence > 0 else None,
            "average_seconds_per_image": None,
            "warning": bool(seconds > 0 and cadence > 0 and count <= 0),
        }
    expected = max(1, int(math.ceil(seconds / cadence)))
    average = round(seconds / count, 1)
    return {
        "expected_images": expected,
        "average_seconds_per_image": average,
        "warning": count < expected,
    }


@app.get("/api/jobs/{job_id}/report")
def video_quality_report(job_id: str):
    """Create a TalkBack-friendly, free technical report for a completed MP4."""
    with LOCK:
        job = JOBS.get(job_id)
        if not job:
            raise HTTPException(404, "ভিডিওর কাজটি পাওয়া যায়নি। সার্ভার পুনরায় চালু হলে অস্থায়ী কাজের তথ্য মুছে যেতে পারে।")
        snapshot = dict(job)
    if snapshot.get("status") != "completed":
        raise HTTPException(409, "ভিডিও তৈরি সম্পূর্ণ হলে পরীক্ষা করা যাবে।")
    video_path = WORK_DIR / job_id / "video.mp4"
    if not video_path.exists() or video_path.stat().st_size <= 0:
        raise HTTPException(404, "ভিডিও ফাইলটি পাওয়া যাচ্ছে না।")
    try:
        probe = json.loads(run([
            "ffprobe", "-v", "error", "-show_entries",
            "format=duration,size,format_name:stream=codec_type,codec_name,width,height,sample_rate,channels",
            "-of", "json", str(video_path)
        ], 30).decode("utf-8", "replace"))
    except Exception as exc:
        raise HTTPException(500, "ভিডিওর তথ্য পরীক্ষা করা যায়নি।") from exc

    streams = probe.get("streams", [])
    video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)
    try:
        duration = float(probe.get("format", {}).get("duration", 0))
    except (TypeError, ValueError):
        duration = 0.0
    size_bytes = video_path.stat().st_size
    image_count = snapshot.get("scene_count")
    scene_interval = snapshot.get("scene_interval_seconds")
    interval_diagnostics = _scene_interval_diagnostics(duration, image_count, scene_interval)

    audio_check = "অডিও ট্র্যাক পাওয়া যায়নি।"
    audio_level = None
    if audio_stream:
        try:
            audio_log = subprocess.run(
                ["ffmpeg", "-hide_banner", "-i", str(video_path), "-vn", "-af", "volumedetect", "-f", "null", "-"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=45, check=False
            ).stderr.decode("utf-8", "replace")
            match = re.search(r"mean_volume:\s*(-?inf|-?[0-9.]+) dB", audio_log)
            peak = re.search(r"max_volume:\s*(-?inf|-?[0-9.]+) dB", audio_log)
            audio_level = match.group(1) if match else None
            if peak and peak.group(1) != "-inf":
                audio_check = "অডিও ট্র্যাক আছে এবং শব্দের সংকেত পাওয়া গেছে।"
            else:
                audio_check = "অডিও ট্র্যাক আছে, কিন্তু শব্দ নীরব বা পরীক্ষা করা যায়নি।"
        except Exception:
            audio_check = "অডিও ট্র্যাক আছে; শব্দের মাত্রা পরীক্ষা সম্পূর্ণ হয়নি।"

    distinct_frames = None
    scene_check = "দৃশ্য পরিবর্তন আলাদাভাবে পরীক্ষা করা যায়নি।"
    visual_mean_luma = None
    visual_sample_count = None
    dark_sample_count = None
    if video_stream:
        try:
            frame_result = subprocess.run(
                ["ffmpeg", "-v", "error", "-i", str(video_path), "-vf",
                 "fps=1,scale=32:56:flags=fast_bilinear,format=gray",
                 "-an", "-f", "framemd5", "-"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60, check=False
            )
            if frame_result.returncode == 0:
                sampled_frames = []
                for line in frame_result.stdout.decode("utf-8", "replace").splitlines():
                    if line and not line.startswith("#") and "," in line:
                        sampled_frames.append(line.rsplit(",", 1)[-1].strip())
                # Hashes change with subtitles and motion; they are not a scene count.
                distinct_frames = len(sampled_frames)
                if not sampled_frames:
                    scene_check = "ভিডিওর দৃশ্য নমুনা পড়া যায়নি।"
                else:
                    scene_check = f"প্রতি সেকেন্ডে {len(sampled_frames)}টি নমুনা চিত্র পরীক্ষা করা হয়েছে। এটি স্বতন্ত্র দৃশ্যের সংখ্যা নিশ্চিত করে না।"
        except Exception:
            pass
        # Independently inspect actual decoded pixels. This catches black/blank videos
        # even when MP4 streams and subtitle frames exist and the technical report passes.
        try:
            pixel_result = subprocess.run(
                ["ffmpeg", "-v", "error", "-i", str(video_path), "-vf",
                 "fps=1,scale=24:42:flags=fast_bilinear,format=gray",
                 "-an", "-f", "rawvideo", "-pix_fmt", "gray", "-"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60, check=False
            )
            frame_bytes = 24 * 42
            if pixel_result.returncode == 0 and len(pixel_result.stdout) >= frame_bytes:
                raw = pixel_result.stdout
                means = [
                    sum(raw[offset:offset + frame_bytes]) / frame_bytes
                    for offset in range(0, len(raw) - frame_bytes + 1, frame_bytes)
                ]
                visual_sample_count = len(means)
                visual_mean_luma = round(sum(means) / visual_sample_count, 1) if visual_sample_count else None
                dark_sample_count = sum(value < 22 for value in means)
                if visual_sample_count and dark_sample_count / visual_sample_count >= 0.5:
                    scene_check += f" সতর্কতা: {visual_sample_count}টি নমুনা চিত্রের মধ্যে {dark_sample_count}টি খুব অন্ধকার; ভিডিওর দৃশ্য কালো বা অস্পষ্ট হতে পারে।"
                elif means:
                    scene_check += f" দৃশ্যের গড় উজ্জ্বলতা {visual_mean_luma} / 255; কালো ফ্রেমের স্বয়ংক্রিয় সতর্কতা পাওয়া যায়নি।"
        except Exception:
            pass

    semantic_review = snapshot.get("semantic_review") or {}
    semantic_review = {
        key: int(semantic_review.get(key, 0) or 0)
        for key in (
            "reviewed", "matched", "mismatched", "retried", "retry_matched", "retry_mismatched", "unavailable",
            "duplicate_retry_reviewed", "duplicate_retry_matched", "duplicate_retry_mismatched", "duplicate_retry_unavailable"
        )
    }
    raw_image_sources = snapshot.get("semantic_review") or {}
    raw_image_sources = raw_image_sources.get("image_sources") or {}
    image_source_counts = {
        key: int(raw_image_sources.get(key, 0) or 0)
        for key in ("ai_generated", "licensed_contextual", "topic_graphic", "unknown")
    }

    checks = {
        "semantic_image_review": semantic_review,
        "image_source_counts": image_source_counts,
        "file_exists": True,
        "video_track": video_stream is not None,
        "audio_track": audio_stream is not None,
        "duration_seconds": round(duration, 2),
        "width": video_stream.get("width") if video_stream else None,
        "height": video_stream.get("height") if video_stream else None,
        "video_codec": video_stream.get("codec_name") if video_stream else None,
        "audio_codec": audio_stream.get("codec_name") if audio_stream else None,
        "audio_mean_volume_db": audio_level,
        "scene_sample_count": distinct_frames,
        "visual_mean_luminance_0_255": visual_mean_luma,
        "visual_sample_count": visual_sample_count,
        "very_dark_sample_count": dark_sample_count,
        "scene_count_from_generator": snapshot.get("scene_count"),
        "narration_scene_count": snapshot.get("narration_scene_count"),
        "scene_interval_seconds": snapshot.get("scene_interval_seconds"),
        "caption_frame_count": snapshot.get("caption_frame_count"),
        "file_size_bytes": size_bytes,
        "format": probe.get("format", {}).get("format_name", "unknown"),
    }
    if not video_stream:
        summary = "পরীক্ষায় সমস্যা পাওয়া গেছে: ভিডিও ট্র্যাক নেই।"
        overall = "problem"
    elif not audio_stream:
        summary = "ভিডিও ফাইল তৈরি হয়েছে, কিন্তু অডিও ট্র্যাক নেই।"
        overall = "problem"
    elif duration <= 0:
        summary = "ভিডিওর দৈর্ঘ্য সঠিকভাবে পড়া যায়নি।"
        overall = "problem"
    elif dark_sample_count is not None and visual_sample_count and dark_sample_count / visual_sample_count >= 0.5:
        summary = "সতর্কতা: ভিডিও ও অডিও ট্র্যাক আছে, কিন্তু নমুনা চিত্রের অর্ধেক বা তার বেশি খুব অন্ধকার। ভিডিওর দৃশ্য কালো বা অস্পষ্ট হতে পারে; এই ফলাফল যাচাই না করে ভিডিওকে সম্পূর্ণ সফল বলা যাবে না।"
        overall = "visual_warning"
    elif interval_diagnostics["warning"]:
        summary = "প্রাথমিক প্রযুক্তিগত পরীক্ষা সফল, তবে নির্বাচিত ছবি পরিবর্তনের বিরতি পূরণ হয়নি। ভিডিওর দৈর্ঘ্য অনুযায়ী পর্যাপ্ত পটভূমির ছবি তৈরি হয়নি; তাই প্রতি নির্বাচিত বিরতিতে নতুন ছবি আসা নিশ্চিত নয়।"
        overall = "visual_warning"
    else:
        summary = "প্রাথমিক প্রযুক্তিগত পরীক্ষা সফল। ভিডিও ও অডিও ট্র্যাক এবং ফাইলের দৈর্ঘ্য পাওয়া গেছে। দৃশ্যের উজ্জ্বলতা পরীক্ষা করা হয়েছে; তবে দৃশ্য ও সাবটাইটেলের বিষয়বস্তু শতভাগ সঠিক কি না, এই পরীক্ষা তা নিশ্চিত করে না।"
        overall = "passed_with_limits"

    report_text = "ভিডিও পরীক্ষার প্রতিবেদন। " + summary + " "
    report_text += f"ভিডিওর দৈর্ঘ্য {round(duration, 1)} সেকেন্ড। "
    report_text += f"ফাইলের আকার {round(size_bytes / (1024 * 1024), 2)} মেগাবাইট। "
    report_text += ("ভিডিও ট্র্যাক আছে। " if video_stream else "ভিডিও ট্র্যাক নেই। ")
    report_text += audio_check + " "
    report_text += scene_check + " "
    narration_scene_count = snapshot.get("narration_scene_count")
    if isinstance(image_count, int) and image_count > 0:
        report_text += f"ভিডিওতে {image_count}টি পটভূমির ছবি ব্যবহার করা হয়েছে। "
    if sum(image_source_counts.values()) > 0:
        report_text += (
            f"ছবির উৎসের হিসাবে {image_source_counts['ai_generated']}টি AI-তৈরি ছবি, "
            f"{image_source_counts['licensed_contextual']}টি লাইসেন্সভিত্তিক প্রাসঙ্গিক ছবি এবং "
            f"{image_source_counts['topic_graphic']}টি বিষয়ভিত্তিক বিকল্প গ্রাফিক ব্যবহার হয়েছে। "
        )
    if semantic_review["reviewed"] > 0:
        report_text += (
            f"ছবির বিষয়বস্তু যাচাইয়ে {semantic_review['reviewed']}টি নির্বাচিত ছবি পরীক্ষা করা হয়েছে। "
            f"প্রথম পরীক্ষায় {semantic_review['matched']}টি মিলেছে এবং "
            f"{semantic_review['mismatched']}টি মেলেনি। "
            f"{semantic_review['retried']}টি ছবির জন্য নতুন ছবি তৈরির চেষ্টা হয়েছে; "
            f"পুনরায় যাচাইয়ে {semantic_review['retry_matched']}টি মিলেছে এবং "
            f"{semantic_review['retry_mismatched']}টি এখনো মেলেনি। "
        )
        if semantic_review["unavailable"]:
            report_text += f"{semantic_review['unavailable']}টি যাচাইয়ের উত্তর পাওয়া যায়নি। "
        if semantic_review["duplicate_retry_reviewed"]:
            report_text += (
                f"একই ছবি এড়িয়ে তৈরি নতুন {semantic_review['duplicate_retry_reviewed']}টি ছবিও যাচাই করা হয়েছে। "
                f"এর মধ্যে {semantic_review['duplicate_retry_matched']}টি মিলেছে, "
                f"{semantic_review['duplicate_retry_mismatched']}টি মেলেনি এবং "
                f"{semantic_review['duplicate_retry_unavailable']}টির যাচাইয়ের উত্তর পাওয়া যায়নি। "
            )
        report_text += "এটি নির্বাচিত ছবির নমুনা যাচাই, সব ছবির শতভাগ নিশ্চয়তা নয়। "
    else:
        report_text += "এই ভিডিওতে ছবির অর্থগত AI যাচাইয়ের ফল পাওয়া যায়নি। "

    if isinstance(narration_scene_count, int) and narration_scene_count > 0:
        report_text += f"লেখা থেকে {narration_scene_count}টি বাক্যভিত্তিক দৃশ্য তৈরি হয়েছে। "
    if isinstance(scene_interval, int) and scene_interval > 0:
        report_text += f"নির্বাচিত ছবি পরিবর্তনের বিরতি ছিল {scene_interval} সেকেন্ড। "
    if interval_diagnostics["expected_images"] is not None and interval_diagnostics["average_seconds_per_image"] is not None:
        report_text += (
            f"এই দৈর্ঘ্যে {scene_interval} সেকেন্ড বিরতি মানতে আনুমানিক "
            f"{interval_diagnostics['expected_images']}টি ছবি দরকার ছিল। "
            f"প্রতি ছবির গড় কভারেজ {interval_diagnostics['average_seconds_per_image']} সেকেন্ড। "
        )
        if interval_diagnostics["warning"]:
            report_text += "তৈরি ছবির সংখ্যা কম হওয়ায় নির্বাচিত বিরতিতে ছবি বদলানো নিশ্চিত হয়নি। "
    captions = snapshot.get("caption_frame_count")
    if isinstance(captions, int) and captions > 0:
        report_text += f"তৈরির সময় {captions}টি সাবটাইটেল ফ্রেম তৈরি হয়েছিল। "
    else:
        report_text += "সাবটাইটেলের দৃশ্যমান লেখা আলাদাভাবে যাচাই করা যায়নি। "
    report_text += "এই প্রতিবেদন ফাইলের প্রযুক্তিগত পরীক্ষা; কণ্ঠে লেখা হুবহু পড়া হয়েছে কি না বা প্রতিটি সাবটাইটেল ঠিক আছে কি না তা নিশ্চিত করে না।"

    return {
        "job_id": job_id,
        "overall": overall,
        "summary": summary,
        "report_text": report_text,
        "checks": checks,
        "audio_check": audio_check,
        "scene_check": scene_check,
        "limitations": [
            "কণ্ঠে লেখা হুবহু পড়া হয়েছে কি না স্বয়ংক্রিয়ভাবে নিশ্চিত করা হয়নি।",
            "সাবটাইটেলের বানান ও সময়ের সঙ্গে কণ্ঠের মিল OCR বা মানুষের পর্যালোচনা ছাড়া নিশ্চিত নয়।",
            "ছবির অর্থগত AI যাচাই কেবল নির্বাচিত নমুনায় করা হয়; সব ছবির শতভাগ নির্ভুলতা নিশ্চিত করে না।"
        ],
    }


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