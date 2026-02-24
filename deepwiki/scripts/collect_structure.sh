#!/usr/bin/env bash
# collect_structure.sh - コードベースのディレクトリ構造を収集するスクリプト
#
# 使用方法: ./collect_structure.sh <対象ディレクトリ> [最大深度] [--exclude-tests]
# 例:       ./collect_structure.sh /path/to/project 5
#            ./collect_structure.sh /path/to/project --exclude-tests
#            ./collect_structure.sh /path/to/project 5 --exclude-tests
#
# 出力: ディレクトリツリー、ファイル数、主要ファイルの情報

set -euo pipefail

TARGET_DIR="${1:-.}"
MAX_DEPTH="6"
EXCLUDE_TESTS=false

# 第2引数以降からオプション解析（位置に依存しない）
for arg in "${@:2}"; do
  case "$arg" in
    --exclude-tests) EXCLUDE_TESTS=true ;;
    [0-9]*) MAX_DEPTH="$arg" ;;
  esac
done

# 対象ディレクトリの検証
if [ ! -d "$TARGET_DIR" ]; then
  echo "ERROR: ディレクトリが存在しません: $TARGET_DIR" >&2
  exit 1
fi

# 絶対パスに変換
TARGET_DIR="$(cd "$TARGET_DIR" && pwd)"
DEEPWIKI_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# git リポジトリかチェック
USE_GIT=false
if git -C "$TARGET_DIR" rev-parse --is-inside-work-tree &>/dev/null 2>&1; then
  USE_GIT=true
fi

# --- 除外パターン（find フォールバック用） ---
# target: Rust/Java ビルド成果物, Pods: iOS CocoaPods
EXCLUDE_DIRS=(
  .git node_modules __pycache__ .next .nuxt dist build out
  .cache .tmp .temp vendor .venv venv env .env
  .idea .vscode .DS_Store coverage .nyc_output
  .terraform .serverless .aws-sam
  target
  Pods
)

# find 用の除外オプション構築
FIND_EXCLUDES=""
for dir in "${EXCLUDE_DIRS[@]}"; do
  FIND_EXCLUDES="$FIND_EXCLUDES -name \"$dir\" -prune -o"
done

# --- ユーティリティ関数 ---

# .gitignore を考慮したファイル列挙（絶対パスで返す）
# gitリポジトリなら git ls-files を使用。そうでなければ find フォールバック。
list_files() {
  if $USE_GIT; then
    git -C "$TARGET_DIR" ls-files --cached --others --exclude-standard \
      | sed "s|^|$TARGET_DIR/|"
  else
    eval "find \"$TARGET_DIR\" \( $FIND_EXCLUDES -type f -print \)" 2>/dev/null
  fi
}

# バイナリ・生成物のフィルタリング（gitモード時にも必要）
filter_binary() {
  grep -v -E '\.(lock|sum|woff2?|ttf|eot|ico|png|jpe?g|gif|webp|mp4|mp3|wav|ogg|zip|tar|gz|bz2|7z|exe|dll|so|dylib|pyc|pyo|class|o|obj|DS_Store)$' | \
  grep -v -E '(\.min\.js$|\.min\.css$|\.map$|\.bundle\.js$)'
}

# テストファイルのフィルタリング（--exclude-tests 時のみ除外）
filter_tests() {
  if $EXCLUDE_TESTS; then
    grep -v -E '/(tests?|spec|__tests__|e2e)/|\.test\.(ts|tsx|js|jsx|py|go|rs|java|kt|rb|cs|swift|dart)$|\.spec\.(ts|tsx|js|jsx|py|go|rs|java|kt|rb|cs|swift|dart)$|test_[^/]+\.(py|go)$|[^/]+_test\.(py|go|rs)$|[^/]+Test\.(java|kt)$'
  else
    cat
  fi
}

echo "=== DeepWiki 構造分析 ==="
echo "対象: $TARGET_DIR"
echo "日時: $(date '+%Y-%m-%d %H:%M:%S')"
if $USE_GIT; then
  echo "モード: git ls-files（.gitignore を自動除外）"
fi
if $EXCLUDE_TESTS; then
  echo "テストファイル: 除外"
else
  echo "テストファイル: 含む"
fi
echo ""

# --- セクション 1: ディレクトリツリー ---
echo "## ディレクトリ構造"
echo '```'

if command -v tree &>/dev/null; then
  TREE_IGNORE=$(IFS='|'; echo "${EXCLUDE_DIRS[*]}")
  # tree の --gitignore は新しいバージョンのみ対応
  TREE_GIT_FLAG=""
  if $USE_GIT && tree --help 2>&1 | grep -q '\-\-gitignore'; then
    TREE_GIT_FLAG="--gitignore"
  fi
  tree "$TARGET_DIR" -I "$TREE_IGNORE" ${TREE_GIT_FLAG:+"$TREE_GIT_FLAG"} --dirsfirst -L "$MAX_DEPTH" -F --noreport 2>/dev/null || \
    echo "(tree コマンドの実行に失敗しました)"
else
  if $USE_GIT; then
    # git ls-files を相対パスで表示
    git -C "$TARGET_DIR" ls-files --cached --others --exclude-standard \
      | sort | head -300 || echo "(git ls-files の実行に失敗しました)"
  else
    eval "find \"$TARGET_DIR\" -maxdepth $MAX_DEPTH \( $FIND_EXCLUDES -type f -print -o -type d -print \)" 2>/dev/null | \
      sed "s|^$TARGET_DIR/||" | sort || echo "(find の実行に失敗しました)"
  fi
fi

echo '```'
echo ""

# --- セクション 2: ファイル統計 ---
echo "## ファイル統計"
echo ""
echo "### 言語別ファイル数"
echo '```'
set +o pipefail
list_files | filter_binary | filter_tests | \
  grep -E '\.[a-zA-Z0-9]+$' | \
  sed 's/.*\.//' | sort | uniq -c | sort -rn | head -20 || echo "(集計に失敗しました)"
set -o pipefail
echo '```'

# 総ファイル数・ディレクトリ数
TOTAL_FILES=$(list_files | filter_binary | filter_tests | wc -l | tr -d ' ')
if $USE_GIT; then
  TOTAL_DIRS=$(list_files | sed 's|/[^/]*$||' | sort -u | wc -l | tr -d ' ')
else
  TOTAL_DIRS=$(eval "find \"$TARGET_DIR\" \( $FIND_EXCLUDES -type d -print \)" 2>/dev/null | wc -l | tr -d ' ')
fi
echo ""
echo "- 総ファイル数: $TOTAL_FILES"
echo "- 総ディレクトリ数: $TOTAL_DIRS"

# --- セクション 3: 主要ファイルの検出 ---
echo ""
echo "## 主要ファイル"

echo ""
echo "### パッケージ/プロジェクト定義"
echo '```'
# 設定ファイル系はテスト除外対象外（testとは無関係なため）
list_files | \
  grep -E '(^|/)(package\.json|Cargo\.toml|pyproject\.toml|go\.mod|build\.gradle|pom\.xml|Gemfile|composer\.json|[^/]+\.csproj|CMakeLists\.txt|Makefile)$' | \
  sed "s|^$TARGET_DIR/||" | sort || true
echo '```'

echo ""
echo "### 設定ファイル"
echo '```'
list_files | \
  grep -E '(^|/)(tsconfig[^/]*\.json|\.eslintrc[^/]*|\.prettierrc[^/]*|webpack\.config[^/]*|vite\.config[^/]*|next\.config[^/]*|Dockerfile[^/]*|docker-compose[^/]*|\.env\.example|firebase\.json|vercel\.json|netlify\.toml)$' | \
  sed "s|^$TARGET_DIR/||" | sort | head -30 || true
echo '```'

echo ""
echo "### ドキュメント"
echo '```'
list_files | \
  grep -E '(^|/)(README[^/]*|CONTRIBUTING[^/]*|CHANGELOG[^/]*|LICENSE[^/]*|ARCHITECTURE[^/]*|DESIGN[^/]*)$' | \
  sed "s|^$TARGET_DIR/||" | sort | head -20 || true
echo '```'

echo ""
echo "### エントリーポイント候補"
echo '```'
list_files | filter_tests | \
  grep -E '(^|/)(main|index|app|server|cli|mod)\.[^/]+$' | \
  grep -v -E '(\.test\.|\.spec\.|\.d\.ts$|\.css$|\.scss$|\.json$)' | \
  sed "s|^$TARGET_DIR/||" | sort | head -30 || true
echo '```'

# --- README/ドキュメントサマリー抽出 ---
echo ""
echo "## 主要ドキュメントの内容抜粋"
echo '```'
list_files | grep -E '(^|/)(README\.md|README)$' | head -3 | while read -r file; do
  echo "--- $file ---"
  head -n 20 "$file" | grep -v '^\s*$' || true
  echo "..."
done
echo '```'

# --- セクション 4: 依存関係マップ ---
echo ""
echo "## 依存関係マップ (import/export)"

# 仮想環境のPythonがあれば優先して使用する
PYTHON_CMD="python3"
if [ -f "$DEEPWIKI_DIR/.venv/bin/python" ]; then
  PYTHON_CMD="$DEEPWIKI_DIR/.venv/bin/python"
fi

$PYTHON_CMD "$DEEPWIKI_DIR/scripts/analyze_dependencies.py" "$TARGET_DIR" 2>/dev/null || true
echo ""

echo "## ファイルサイズ Top 20（大きいファイル=重要度が高い可能性）"
echo '```'
set +o pipefail
list_files | filter_binary | filter_tests | \
  grep -E '\.(ts|tsx|js|jsx|py|rs|go|java|rb|cs|cpp|c|swift|kt|vue|svelte|php|dart)$' | \
  xargs wc -l 2>/dev/null | sort -rn | head -21 | \
  (grep -v ' total$' || true) | \
  sed "s|$TARGET_DIR/||" || echo "(集計に失敗しました)"
set -o pipefail
echo '```'

# --- セクション 5: エクスポート情報 ---
echo ""
echo "## 主要エクスポート・関数シグネチャ"
$PYTHON_CMD "$DEEPWIKI_DIR/scripts/extract_signatures.py" "$TARGET_DIR" 2>/dev/null || true

echo ""
echo "=== 分析完了 ==="
