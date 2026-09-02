import json
import uuid
import os
import re
from datetime import datetime
from pathlib import Path

# Hugging Face 国内镜像，必须在 import faster_whisper 之前设置
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
os.environ["HF_HUB_DISABLE_XET"] = "1"

from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import httpx
from faster_whisper import WhisperModel

load_dotenv()

# --- 配置 ---
UPLOAD_DIR = Path("uploads")
DATA_DIR = Path("data")
UPLOAD_DIR.mkdir(exist_ok=True)
DATA_DIR.mkdir(exist_ok=True)

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"

# Whisper 模型: tiny/base/small/medium/large-v3
# tiny 最快但精度低, base 够用且快, small 精度好但慢
WHISPER_MODEL_SIZE = "base"
whisper_model = None

app = FastAPI(title="英语精听训练")


def get_whisper_model():
    global whisper_model
    if whisper_model is None:
        whisper_model = WhisperModel(WHISPER_MODEL_SIZE, device="cpu", compute_type="int8")
    return whisper_model


# --- 句子分割 ---
# Whisper 的 segment 通常对应一个语义停顿或说话人切换
# 少于 min_words 的段持续向后合并，直到累计够词数才输出
# 过滤掉纯音乐/无意义拟声词产生的低质量段落
FILLER_WORDS = {"mmm", "mm", "hmm", "uh", "um", "ah", "oh", "huh", "yeah", "hey", "wow", "la", "na"}

def is_meaningful(text):
    """判断文本是否有实际语义内容，过滤纯音乐/拟声词"""
    words = text.lower().strip().strip(".,!?;:'\"()[]").split()
    if not words:
        return False
    real_words = [w for w in words if w not in FILLER_WORDS]
    return len(real_words) >= 2

def split_sentences(segments, min_words=5):
    results = []
    pending_text = ""
    pending_start = None
    pending_end = None

    for seg in segments:
        text = seg.text.strip()
        if not text or not is_meaningful(text):
            continue

        if pending_text == "":
            pending_text = text
            pending_start = seg.start
            pending_end = seg.end
        else:
            pending_text += " " + text
            pending_end = seg.end

        # 达到最低词数才输出
        if len(pending_text.split()) >= min_words:
            results.append({
                "id": len(results) + 1,
                "start_time": round(pending_start, 2),
                "end_time": round(pending_end, 2),
                "text": pending_text,
            })
            pending_text = ""
            pending_start = None
            pending_end = None

    # 处理最后残留的短段，合并到最后一条
    if pending_text:
        if results:
            results[-1]["text"] += " " + pending_text
            results[-1]["end_time"] = round(pending_end, 2)
        else:
            results.append({
                "id": 1,
                "start_time": round(pending_start, 2),
                "end_time": round(pending_end, 2),
                "text": pending_text,
            })

    return results


# --- 翻译 ---
async def translate_batch(sentences: list[str]) -> list[str]:
    if not DEEPSEEK_API_KEY:
        # 没有配置 API key，返回空翻译
        return [""] * len(sentences)

    # 把所有句子编号拼成一次请求，减少 API 调用
    numbered = "\n".join(f"{i+1}. {s}" for i, s in enumerate(sentences))
    prompt = (
        f"将以下英语句子翻译成中文，保持编号格式，每行一句：\n\n{numbered}\n\n"
        f"只输出翻译结果，格式为编号+翻译，不要多余内容。"
    )

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            DEEPSEEK_API_URL,
            headers={
                "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "deepseek-chat",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
            },
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]

    # 解析翻译结果: "1. 翻译内容"
    translations = {}
    for line in content.strip().split("\n"):
        match = re.match(r'^(\d+)\.\s*(.+)', line.strip())
        if match:
            idx = int(match.group(1))
            translations[idx] = match.group(2)

    return [translations.get(i + 1, "") for i in range(len(sentences))]


# --- API 路由 ---

@app.post("/api/upload")
async def upload_audio(file: UploadFile = File(...)):
    # 保存音频文件
    audio_id = f"audio_{uuid.uuid4().hex[:8]}"
    ext = Path(file.filename).suffix or ".mp3"
    audio_path = UPLOAD_DIR / f"{audio_id}{ext}"

    content = await file.read()
    audio_path.write_bytes(content)

    # Whisper 识别，直接用 segment 级别的时间戳
    model = get_whisper_model()
    segments, _ = model.transcribe(
        str(audio_path),
        language="en",
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 500, "speech_pad_ms": 200},
    )
    segments = list(segments)

    # 按句分割
    sentences = split_sentences(segments)

    # 批量翻译
    texts = [s["text"] for s in sentences]
    translations = await translate_batch(texts)
    for s, t in zip(sentences, translations):
        s["translation"] = t

    # 保存 JSON
    data = {
        "audio_id": audio_id,
        "audio_name": file.filename,
        "audio_path": f"{audio_id}{ext}",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "segments": sentences,
    }
    json_path = DATA_DIR / f"{audio_id}.json"
    json_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    return {"audio_id": audio_id, "segments": sentences}


@app.get("/api/audio_list")
async def audio_list():
    files = sorted(DATA_DIR.glob("*.json"), key=lambda f: f.stat().st_mtime, reverse=True)
    result = []
    for f in files:
        data = json.loads(f.read_text(encoding="utf-8"))
        result.append({
            "audio_id": data["audio_id"],
            "audio_name": data["audio_name"],
            "created_at": data["created_at"],
            "segment_count": len(data["segments"]),
        })
    return result


@app.get("/api/audio/{audio_id}")
async def get_audio(audio_id: str):
    json_path = DATA_DIR / f"{audio_id}.json"
    if not json_path.exists():
        raise HTTPException(status_code=404, detail="音频不存在")
    return json.loads(json_path.read_text(encoding="utf-8"))


@app.get("/api/audio_file/{filename}")
async def get_audio_file(filename: str):
    audio_path = UPLOAD_DIR / filename
    if not audio_path.exists():
        raise HTTPException(status_code=404, detail="文件不存在")
    return FileResponse(audio_path)


@app.delete("/api/audio/{audio_id}")
async def delete_audio(audio_id: str):
    json_path = DATA_DIR / f"{audio_id}.json"
    if json_path.exists():
        data = json.loads(json_path.read_text(encoding="utf-8"))
        json_path.unlink()
        audio_file = UPLOAD_DIR / data.get("audio_path", "")
        if audio_file.exists():
            audio_file.unlink()
        return {"ok": True}
    raise HTTPException(status_code=404, detail="音频不存在")


# 首页
@app.get("/")
async def index():
    return FileResponse("static/index.html")


# 静态文件
app.mount("/static", StaticFiles(directory="static"), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
