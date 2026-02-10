#!/bin/bash
# 安裝 youtube-note Skill 到 ~/.claude/skills/youtube-note/

set -e

SKILL_NAME="youtube-note"
SKILL_DIR="$HOME/.claude/skills/$SKILL_NAME"
SOURCE_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "🚀 安裝 YouTube Note Skill..."
echo "   來源: $SOURCE_DIR"
echo "   目標: $SKILL_DIR"

# 檢測依賴
echo ""
echo "📋 檢測依賴..."

check_command() {
    if command -v "$1" &> /dev/null; then
        echo "   ✅ $1 已安裝"
        return 0
    else
        echo "   ❌ $1 未安裝 — $2"
        return 1
    fi
}

check_python_module() {
    if python3 -c "import $1" 2>/dev/null; then
        echo "   ✅ $1 已安裝"
        return 0
    else
        echo "   ❌ $1 未安裝 — pip install $2"
        return 1
    fi
}

MISSING=0

check_command "yt-dlp" "brew install yt-dlp" || MISSING=1
check_command "ffmpeg" "brew install ffmpeg" || MISSING=1
check_command "python3" "需要 Python 3.8+" || MISSING=1

check_python_module "yt_dlp" "yt-dlp" || MISSING=1
check_python_module "youtube_transcript_api" "youtube-transcript-api" || MISSING=1
check_python_module "deepgram" "deepgram-sdk" || MISSING=1
check_python_module "dotenv" "python-dotenv" || MISSING=1

if [ $MISSING -eq 1 ]; then
    echo ""
    echo "⚠️  部分依賴缺失，你可以先安裝缺失的依賴，或繼續安裝 Skill（之後再補裝）"
    read -p "   繼續安裝？(y/N) " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "❌ 安裝取消"
        exit 1
    fi
fi

# 建立目標目錄
echo ""
echo "📁 建立 Skill 目錄..."
mkdir -p "$SKILL_DIR/scripts"
mkdir -p "$SKILL_DIR/templates"
mkdir -p "$SKILL_DIR/references"

# 複製檔案
echo "📋 複製檔案..."
cp "$SOURCE_DIR/SKILL.md" "$SKILL_DIR/"
cp "$SOURCE_DIR/scripts/"*.py "$SKILL_DIR/scripts/"
cp "$SOURCE_DIR/templates/"*.md "$SKILL_DIR/templates/"
cp "$SOURCE_DIR/references/"*.md "$SKILL_DIR/references/"

# 複製 .env（如果存在且目標不存在）
if [ -f "$SOURCE_DIR/.env" ] && [ ! -f "$SKILL_DIR/.env" ]; then
    cp "$SOURCE_DIR/.env" "$SKILL_DIR/.env"
    echo "   📄 已複製 .env"
elif [ -f "$SOURCE_DIR/.env.example" ] && [ ! -f "$SKILL_DIR/.env" ]; then
    cp "$SOURCE_DIR/.env.example" "$SKILL_DIR/.env"
    echo "   📄 已複製 .env.example 為 .env（請編輯填入 API key）"
fi

echo ""
echo "✅ YouTube Note Skill 安裝完成！"
echo ""
echo "📂 Skill 路徑: $SKILL_DIR"
echo ""
echo "📝 使用方式:"
echo "   在 Claude Code 中說：「幫我整理這個影片的筆記：https://youtube.com/watch?v=xxx」"
echo ""
echo "⚙️  如果需要 Deepgram（無字幕影片）："
echo "   編輯 $SKILL_DIR/.env 填入 DEEPGRAM_API_KEY"
