#!/usr/bin/env bash
# 一次性环境准备：依赖 + 字体。可重复运行。
set -e
SKILL="$(cd "$(dirname "$0")/.." && pwd)"
FONTS="${WAIQI_FONTS:-$SKILL/fonts}"; mkdir -p "$FONTS"
command -v ffmpeg >/dev/null || { echo "需要先安装 ffmpeg"; exit 1; }
pip install -q -U pillow numpy "yt-dlp[default]" edge-tts faster-whisper bgutil-ytdlp-pot-provider 2>&1 | grep -v WARNING || true
G=https://raw.githubusercontent.com/google/fonts/main/ofl
get() { [ -s "$FONTS/$2" ] || curl -fsSL -o "$FONTS/$2" "$G/$1"; }
get "notoserifsc/NotoSerifSC%5Bwght%5D.ttf" "NotoSerifSC[wght].ttf"   # 标题/金句：思源宋体
get "notosanssc/NotoSansSC%5Bwght%5D.ttf"   "NotoSansSC[wght].ttf"    # 中文字幕：思源黑体
get "inter/Inter%5Bopsz,wght%5D.ttf"        "Inter[opsz,wght].ttf"     # 英文字幕：Inter
# 可选：YouTube 防机器人令牌服务（fetch_video.sh 会自动用到）
if [ ! -d "$SKILL/.bgutil/server/build" ] && command -v git >/dev/null && command -v npm >/dev/null; then
  git clone -q --depth 1 https://github.com/Brainicism/bgutil-ytdlp-pot-provider.git "$SKILL/.bgutil" \
   && (cd "$SKILL/.bgutil/server" && npm ci --silent && npx tsc) || echo "bgutil 安装失败（仅影响 YouTube 下载）"
fi
echo "setup 完成，字体在 $FONTS"
