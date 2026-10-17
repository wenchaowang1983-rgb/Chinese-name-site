"""语音听写：python3 transcribe.py <视频或音频> <模型 small|medium> <语言 en|zh|auto> <输出.json>
输出每句的起止秒数与逐词时间戳，用于对字幕时间轴。"""
import sys, json, subprocess, tempfile, wave
import numpy as np
from faster_whisper import WhisperModel
src, model, lang, out = sys.argv[1:5]
wav = tempfile.mktemp(suffix=".wav")
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", src, "-ac", "1", "-ar", "16000", wav], check=True)
w = wave.open(wav); a = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
m = WhisperModel(model, device="cpu", compute_type="int8", cpu_threads=4)
segs, _ = m.transcribe(a, language=None if lang == "auto" else lang, vad_filter=True, word_timestamps=True)
res = []
for s in segs:
    res.append({"s": s.start, "e": s.end, "t": s.text.strip(), "w": [(x.start, x.end, x.word) for x in s.words]})
    print(f"{s.start:7.2f}-{s.end:7.2f} {s.text.strip()}", flush=True)
json.dump(res, open(out, "w"), ensure_ascii=False)
