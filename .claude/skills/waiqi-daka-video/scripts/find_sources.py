"""找素材：同时搜 YouTube（和可选的 B 站），按播放量排序，列出候选。
用法: python3 find_sources.py "Elizabeth Holmes interview" ["另一个关键词" ...] [--n 15] [--min-views 200000] [--min-dur 120] [--max-dur 3600] [--bili]
环境变量 COOKIES_FROM_BROWSER=chrome 可让 yt-dlp 带登录态（本机运行时）。
YouTube 的搜索结果不带上传日期：判断"近两年"请结合标题/频道，或用网页搜索核对。"""
import sys, os, json, re, subprocess, argparse, time
ap = argparse.ArgumentParser(); ap.add_argument("queries", nargs="+")
ap.add_argument("--n", type=int, default=15); ap.add_argument("--min-views", type=int, default=0)
ap.add_argument("--min-dur", type=int, default=0); ap.add_argument("--max-dur", type=int, default=10**9)
ap.add_argument("--bili", action="store_true")
a = ap.parse_args()
rows = {}
def add(src, vid, dur, views, ch, title):
    if views is None or views < a.min_views or dur is None or not (a.min_dur <= dur <= a.max_dur): return
    rows[(src, vid)] = (src, vid, dur, views, ch or "", title or "")
for q in a.queries:
    cmd = ["yt-dlp", "--no-warnings", "--flat-playlist", "--print", "%(id)s\t%(duration)s\t%(view_count)s\t%(channel)s\t%(title)s", f"ytsearch{a.n}:{q}"]
    if os.environ.get("COOKIES_FROM_BROWSER"): cmd[1:1] = ["--cookies-from-browser", os.environ["COOKIES_FROM_BROWSER"]]
    for ln in subprocess.run(cmd, capture_output=True, text=True).stdout.splitlines():
        p = ln.split("\t")
        if len(p) < 5: continue
        try: add("yt", p[0], int(float(p[1])), int(float(p[2])), p[3], p[4])
        except ValueError: pass
    if a.bili:
        for _ in range(3):
            out = subprocess.run(["curl", "-sS", "-A", "Mozilla/5.0", "-b", "buvid3=abc-infoc", "-G", "https://api.bilibili.com/x/web-interface/search/type",
                                  "--data-urlencode", "search_type=video", "--data-urlencode", f"keyword={q}", "--data-urlencode", "order=click"], capture_output=True, text=True).stdout
            try: res = (json.loads(out).get("data") or {}).get("result", []); break
            except Exception: time.sleep(3); res = []
        for r in res[:a.n]:
            m = re.match(r"(?:(\d+):)?(\d+):(\d+)$", r.get("duration", "")); 
            d = (int(m.group(1) or 0) * 3600 + int(m.group(2)) * 60 + int(m.group(3))) if m else None
            add("bili", r["bvid"], d, r.get("play"), r.get("author"), re.sub("<[^>]+>", "", r.get("title", "")))
def fmt(s): return f"{s // 60}:{s % 60:02d}"
print("src\tid\t时长\t播放\t频道\t标题")
for r in sorted(rows.values(), key=lambda x: -x[3]):
    print(f"{r[0]}\t{r[1]}\t{fmt(r[2])}\t{r[3]}\t{r[4][:18]}\t{r[5][:70]}")
