#!/usr/bin/env bash
# collect_structure.sh - コードベースのディレクトリ構造を収集するスクリプト
#
# 使用方法: ./collect_structure.sh <対象ディレクトリ> [最大深度]
# 例:       ./collect_structure.sh /path/to/project 5
#
# 出力: ディレクトリツリー、ファイル数、主要ファイルの情報

set -euo pipefail

TARGET_DIR="${1:-.}"
MAX_DEPTH="${2:-6}"

# 対象ディレクトリの検証
if [ ! -d "$TARGET_DIR" ]; then
  echo "ERROR: ディレクトリが存在しません: $TARGET_DIR" >&2
  exit 1
fi

# 絶対パスに変換
TARGET_DIR="$(cd "$TARGET_DIR" && pwd)"
DEEPWIKI_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "=== DeepWiki 構造分析 ==="
echo "対象: $TARGET_DIR"
echo "日時: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

# --- 除外パターン ---
EXCLUDE_DIRS=(
  .git node_modules __pycache__ .next .nuxt dist build out
  .cache .tmp .temp vendor .venv venv env .env
  .idea .vscode .DS_Store coverage .nyc_output
  .terraform .serverless .aws-sam
  target  # Rust/Java
  Pods    # iOS
)

EXCLUDE_FILES=(
  "*.lock" "*.sum" "*.min.js" "*.min.css" "*.map"
  "*.woff" "*.woff2" "*.ttf" "*.eot" "*.ico"
  "*.png" "*.jpg" "*.jpeg" "*.gif" "*.svg" "*.webp"
  "*.mp4" "*.mp3" "*.wav" "*.ogg"
  "*.zip" "*.tar" "*.gz" "*.bz2" "*.7z"
  "*.exe" "*.dll" "*.so" "*.dylib"
  "*.pyc" "*.pyo" "*.class" "*.o" "*.obj"
)

# find 用の除外オプション構築
FIND_EXCLUDES=""
for dir in "${EXCLUDE_DIRS[@]}"; do
  FIND_EXCLUDES="$FIND_EXCLUDES -name $dir -prune -o"
done

# --- セクション 1: ディレクトリツリー ---
echo "## ディレクトリ構造"
echo '```'

# tree コマンドがある場合は使用、なければ find で代替
if command -v tree &>/dev/null; then
  TREE_IGNORE=$(IFS='|'; echo "${EXCLUDE_DIRS[*]}")
  tree "$TARGET_DIR" -I "$TREE_IGNORE" --dirsfirst -L "$MAX_DEPTH" -F --noreport 2>/dev/null || \
    echo "(tree コマンドの実行に失敗しました)"
else
  # find でツリー風表示
  eval "find \"$TARGET_DIR\" -maxdepth $MAX_DEPTH \( $FIND_EXCLUDES -type f -print -o -type d -print \)" 2>/dev/null | \
    sed "s|^$TARGET_DIR/||" | sort || echo "(find の実行に失敗しました)"
fi

echo '```'
echo ""

# --- セクション 2: ファイル統計 ---
echo "## ファイル統計"

# 言語別ファイル数
echo ""
echo "### 言語別ファイル数"
echo '```'
set +o pipefail
eval "find \"$TARGET_DIR\" \( $FIND_EXCLUDES -type f -print \)" 2>/dev/null | \
  grep -v -E '(\.lock$|\.sum$|\.min\.|\.map$)' | \
  sed 's/.*\.//' | sort | uniq -c | sort -rn | head -20 || echo "(集計に失敗しました)"
set -o pipefail
echo '```'

# 総ファイル数
TOTAL_FILES=$(eval "find \"$TARGET_DIR\" \( $FIND_EXCLUDES -type f -print \)" 2>/dev/null | wc -l | tr -d ' ')
TOTAL_DIRS=$(eval "find \"$TARGET_DIR\" \( $FIND_EXCLUDES -type d -print \)" 2>/dev/null | wc -l | tr -d ' ')
echo ""
echo "- 総ファイル数: $TOTAL_FILES"
echo "- 総ディレクトリ数: $TOTAL_DIRS"

# --- セクション 3: 主要ファイルの検出 ---
echo ""
echo "## 主要ファイル"

echo ""
echo "### パッケージ/プロジェクト定義"
echo '```'
eval "find \"$TARGET_DIR\" \( $FIND_EXCLUDES -type f \( \
  -name 'package.json' -o -name 'Cargo.toml' -o -name 'pyproject.toml' -o \
  -name 'go.mod' -o -name 'build.gradle' -o -name 'pom.xml' -o \
  -name 'Gemfile' -o -name 'composer.json' -o -name '*.csproj' -o \
  -name 'CMakeLists.txt' -o -name 'Makefile' \
  \) -print \)" 2>/dev/null | sed "s|^$TARGET_DIR/||" | sort || true
echo '```'

echo ""
echo "### 設定ファイル"
echo '```'
eval "find \"$TARGET_DIR\" -maxdepth 3 \( $FIND_EXCLUDES -type f \( \
  -name 'tsconfig*.json' -o -name '.eslintrc*' -o -name '.prettierrc*' -o \
  -name 'webpack.config*' -o -name 'vite.config*' -o -name 'next.config*' -o \
  -name 'Dockerfile*' -o -name 'docker-compose*' -o -name '.env.example' -o \
  -name 'firebase.json' -o -name 'vercel.json' -o -name 'netlify.toml' \
  \) -print \)" 2>/dev/null | sed "s|^$TARGET_DIR/||" | sort || true
echo '```'

echo ""
echo "### ドキュメント"
echo '```'
eval "find \"$TARGET_DIR\" -maxdepth 3 \( $FIND_EXCLUDES -type f \( \
  -name 'README*' -o -name 'CONTRIBUTING*' -o -name 'CHANGELOG*' -o \
  -name 'LICENSE*' -o -name 'ARCHITECTURE*' -o -name 'DESIGN*' \
  \) -print \)" 2>/dev/null | sed "s|^$TARGET_DIR/||" | sort || true
echo '```'

echo ""
echo "### エントリーポイント候補"
echo '```'
eval "find \"$TARGET_DIR\" -maxdepth 4 \( $FIND_EXCLUDES -type f \( \
  -name 'main.*' -o -name 'index.*' -o -name 'app.*' -o \
  -name 'server.*' -o -name 'cli.*' -o -name 'mod.rs' \
  \) -print \)" 2>/dev/null | \
  grep -v -E '(\.test\.|\.spec\.|\.d\.ts$|\.css$|\.scss$|\.json$)' | \
  sed "s|^$TARGET_DIR/||" | sort || true
echo '```'

# --- (新規) README/ドキュメントサマリー抽出 ---
echo ""
echo "## 主要ドキュメントの内容抜粋"
echo '```'
eval "find \"$TARGET_DIR\" -maxdepth 2 \( -name 'README.md' -o -name 'README' \) -print" 2>/dev/null | head -3 | while read -r file; do
  echo "--- $file ---"
  head -n 20 "$file" | grep -v '^\s*$' || true
  echo "..."
done
echo '```'

# --- セクション 4: ファイルサイズランキング ---
echo ""
echo "## 依存関係マップ (import/export)"
python3 "$DEEPWIKI_DIR/scripts/analyze_dependencies.py" "$TARGET_DIR" 2>/dev/null || true
echo ""

echo "## ファイルサイズ Top 20（大きいファイル=重要度が高い可能性）"
echo '```'
set +o pipefail
eval "find \"$TARGET_DIR\" \( $FIND_EXCLUDES -type f \( \
  -name '*.ts' -o -name '*.tsx' -o -name '*.js' -o -name '*.jsx' -o \
  -name '*.py' -o -name '*.rs' -o -name '*.go' -o -name '*.java' -o \
  -name '*.rb' -o -name '*.cs' -o -name '*.cpp' -o -name '*.c' -o \
  -name '*.swift' -o -name '*.kt' \
  \) -print \)" 2>/dev/null | \
  xargs wc -l 2>/dev/null | sort -rn | head -21 | \
  (grep -v ' total$' || true) | \
  sed "s|$TARGET_DIR/||" || echo "(集計に失敗しました)"
set -o pipefail
echo '```'

# --- セクション 5: エクスポート情報 ---
echo ""
echo "## 主要エクスポート・関数シグネチャ"
python3 "$DEEPWIKI_DIR/scripts/extract_signatures.py" "$TARGET_DIR" 2>/dev/null || true

echo ""
echo "=== 分析完了 ==="
