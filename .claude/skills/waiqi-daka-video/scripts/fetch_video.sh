#!/usr/bin/env bash
# 用法: fetch_video.sh <视频链接> <输出目录>   → 输出目录/source.mp4 (+ 英文字幕 en.vtt，若有)
# 先试 YouTube 的几种客户端；全部失败时，请改用同事件的 B 站/其他平台副本（yt-dlp 同样支持）。
URL="$1"; DIR="${2:-.}"; mkdir -p "$DIR"; cd "$DIR"
SKILL="$(cd "$(dirname "$0")/.." && pwd)"
if [ -d "$SKILL/.bgutil/server/build" ] && ! (echo > /dev/tcp/127.0.0.1/4416) 2>/dev/null; then
  (cd "$SKILL/.bgutil/server" && nohup node build/main.js >/tmp/bgutil.log 2>&1 &); sleep 4
fi
FMT='bv*[height<=720]+ba/b[height<=720]/b'
for C in mweb web_embedded tv_simply default; do
  echo "尝试客户端: $C"
  yt-dlp --no-warnings --js-runtimes node --extractor-args "youtube:player_client=$C" -f "$FMT" --merge-output-format mp4 \
         --write-auto-subs --sub-langs "en.*" --sub-format vtt -o "source.%(ext)s" "$URL" && [ -s source.mp4 ] && { echo OK; exit 0; }
  sleep 5
done
echo "下载失败。常见原因：1) 网络策略拦了 googlevideo.com（403/连接重置）；2) 要求登录/Cookie。"
echo "办法：在 B 站等平台搜同一事件的视频，用 yt-dlp 直接下载（B 站无需登录）。"; exit 1
