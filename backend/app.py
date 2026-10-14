import json
import os
import re
import shutil
import subprocess
import threading
import time
import uuid
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from PIL import Image, ImageDraw, ImageFont

APP_DIR = Path(__file__).resolve().parent
WORK_DIR = Path(os.getenv("WORK_DIR", "/tmp/bangla-video-jobs"))
WORK_DIR.mkdir(parents=True, exist_ok=True)
MAX_SCRIPT_CHARS = int(os.getenv("MAX_SCRIPT_CHARS", "12000"))
MAX_AUDIO_MB = int(os.getenv("MAX_AUDIO_MB", "40"))
JOBS = {}
LOCK = threading.Lock()
app = FastAPI(title="Bangla AI Voice Video Maker API", version="0.1.0")


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


def make_background(script: str, folder: Path):
    width, height = 720, 1280
    image = Image.new("RGB", (width, height))
    pixels = image.load()
    for y in range(height):
        ratio = y / height
        color = (int(13 + 22 * ratio), int(29 + 18 * ratio), int(63 + 42 * ratio))
        for x in range(width):
            pixels[x, y] = color
    draw = ImageDraw.Draw(image)
    draw.ellipse((470, -130, 900, 300), fill=(30, 69, 113))
    draw.ellipse((-200, 880, 330, 1410), fill=(23, 57, 91))
    title_font = load_font(48, True)
    body_font = load_font(34)
    title = "বাংলা AI ভিডিও"
    title_lines = wrap_text(draw, title, title_font, 600)
    y = 150
    for line in title_lines:
        box = draw.textbbox((0, 0), line, font=title_font)
        draw.text(((width - (box[2] - box[0])) / 2, y), line, font=title_font, fill=(255, 255, 255))
        y += 65
    draw.rounded_rectangle((60, 300, 660, 306), radius=3, fill=(83, 177, 244))
    excerpt = re.sub(r"\s+", " ", script).strip()
    lines = wrap_text(draw, excerpt[:420], body_font, 590)
    y = 370
    for line in lines[:13]:
        draw.text((65, y), line, font=body_font, fill=(231, 241, 250))
        y += 54
    draw.text((65, 1160), "Bangla AI Voice Video Maker", font=load_font(22), fill=(169, 195, 221))
    target = folder / "background.png"
    image.save(target)
    return target


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


def render(job_id: str, script: str, mode: str, audio_path: Optional[Path]):
    folder = WORK_DIR / job_id
    folder.mkdir(parents=True, exist_ok=True)
    try:
        with LOCK:
            JOBS[job_id]["status"] = "processing"
            JOBS[job_id]["progress"] = 10
            JOBS[job_id]["message"] = "ভয়েস ও দৃশ্য প্রস্তুত করা হচ্ছে"
        if audio_path is None:
            voice = "bn" if re.search(r"[\u0980-\u09FF]", script) else "en"
            audio_path = folder / "voice.wav"
            try:
                run(["espeak-ng", "-v", voice, "-s", "145", "-w", str(audio_path), script[:MAX_SCRIPT_CHARS]], 120)
            except Exception:
                # Do not silently switch language: return a clear error.
                raise RuntimeError("এই সার্ভারে প্রয়োজনীয় বাংলা/ইংরেজি Text-to-Speech কণ্ঠ পাওয়া যায়নি।")
        duration = duration_of(audio_path)
        with LOCK:
            JOBS[job_id]["progress"] = 35
            JOBS[job_id]["message"] = "ভিডিওর পটভূমি ও সাবটাইটেল তৈরি হচ্ছে"
        background = make_background(script, folder)
        subtitles = folder / "captions.srt"
        make_srt(script, duration, subtitles)
        output = folder / "video.mp4"
        # Single-scene graphic background with gentle zoom and burned-in captions.
        font_dir = "/usr/share/fonts/truetype/noto"
        subtitle_filter = f"subtitles={subtitles.as_posix()}:fontsdir={font_dir}"
        # Use one still-image frame per second, then expand each to 25 output frames.
        # Escape the comma inside min() so FFmpeg does not parse it as a filter separator.
        vf = f"scale=720:1280,zoompan=z='min(zoom+0.00035\\,1.08)':d=25:s=720x1280:fps=25,{subtitle_filter},format=yuv420p"
        run([
            "ffmpeg", "-y", "-loop", "1", "-framerate", "1", "-i", str(background), "-i", str(audio_path),
            "-vf", vf, "-t", str(duration), "-r", "25", "-c:v", "libx264", "-preset", "ultrafast",
            "-crf", "27", "-c:a", "aac", "-b:a", "128k", "-shortest", "-movflags", "+faststart", str(output)
        ], 240)
        with LOCK:
            JOBS[job_id].update(status="completed", progress=100, message="ভিডিও তৈরি হয়েছে", download_url=f"/api/jobs/{job_id}/download", duration=round(duration, 2), completed_at=time.time())
    except Exception as exc:
        with LOCK:
            JOBS[job_id].update(status="failed", progress=100, message=str(exc)[:1000], completed_at=time.time())


@app.get("/")
def root():
    return {"name": "Bangla AI Voice Video Maker API", "status": "ok", "docs": "/docs"}


@app.get("/health")
def health():
    tools = {name: shutil.which(name) is not None for name in ("ffmpeg", "ffprobe", "espeak-ng")}
    return {"status": "ok" if all(tools.values()) else "degraded", "tools": tools, "version": "0.1.0"}


@app.post("/api/jobs", status_code=202)
async def create_job(script: str = Form(...), mode: str = Form("auto"), audio: Optional[UploadFile] = File(None)):
    script = script.strip()
    if not script:
        raise HTTPException(400, "আগে বাংলা বা ইংরেজি লেখা যোগ করুন।")
    if len(script) > MAX_SCRIPT_CHARS:
        raise HTTPException(413, f"লেখা সর্বোচ্চ {MAX_SCRIPT_CHARS} অক্ষরের হতে পারবে।")
    if mode not in ("auto", "audio"):
        raise HTTPException(400, "ভিডিও তৈরির পদ্ধতি সঠিক নয়।")
    if mode == "audio" and audio is None:
        raise HTTPException(400, "লেখার সঙ্গে অডিও ফাইলও দিতে হবে।")
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
    threading.Thread(target=render, args=(job_id, script, mode, audio_path), daemon=True).start()
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
