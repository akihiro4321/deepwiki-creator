#!/usr/bin/env bash
# deepwiki-creator: ファイル収集・フィルタリングスクリプト
# 使用法: bash collect_files.sh <REPO_PATH> [INCLUDE_DIRS]
#   REPO_PATH: 対象リポジトリのパス
#   INCLUDE_DIRS: 対象ディレクトリ（カンマ区切り、省略時は全体）

set -euo pipefail

REPO_PATH="${1:-.}"
INCLUDE_DIRS="${2:-}"

# 絶対パスに変換
REPO_PATH="$(cd "$REPO_PATH" && pwd)"

# 出力先
FILES_OUT="/tmp/deepwiki_files.txt"
TREE_OUT="/tmp/deepwiki_tree.txt"
README_OUT="/tmp/deepwiki_readme.md"
STATS_OUT="/tmp/deepwiki_stats.txt"

# 除外ディレクトリ
EXCLUDE_DIRS=(
  node_modules .git .svn .hg dist build .next .nuxt
  __pycache__ .pytest_cache .mypy_cache .tox .eggs
  vendor .bundle .gradle .maven target
  .idea .vscode .eclipse coverage .nyc_output
  tmp temp logs .cache .parcel-cache .turbo
)

# 除外ファイルパターン
EXCLUDE_FILES=(
  "*.min.js" "*.min.css" "*.map" "*.lock"
  "*.png" "*.jpg" "*.jpeg" "*.gif" "*.ico" "*.svg" "*.webp"
  "*.woff" "*.woff2" "*.ttf" "*.eot"
  "*.zip" "*.tar" "*.gz" "*.jar" "*.war" "*.class"
  "*.pyc" "*.pyo" "*.so" "*.dylib" "*.dll" "*.exe"
  "*.db" "*.sqlite" "*.sqlite3"
  "*.pdf" "*.doc" "*.docx" "*.xls" "*.xlsx"
  ".DS_Store" "Thumbs.db" ".gitkeep"
  "package-lock.json" "yarn.lock" "pnpm-lock.yaml" "composer.lock"
  "Gemfile.lock" "Cargo.lock" "poetry.lock"
)

# find の除外引数を構築
FIND_EXCLUDES=""
for dir in "${EXCLUDE_DIRS[@]}"; do
  FIND_EXCLUDES="$FIND_EXCLUDES -path '*/$dir' -prune -o"
done

NAME_EXCLUDES=""
for pat in "${EXCLUDE_FILES[@]}"; do
  NAME_EXCLUDES="$NAME_EXCLUDES ! -name '$pat'"
done

# 対象ディレクトリの処理
if [ -n "$INCLUDE_DIRS" ]; then
  IFS=',' read -ra DIRS <<< "$INCLUDE_DIRS"
  > "$FILES_OUT"
  for dir in "${DIRS[@]}"; do
    dir=$(echo "$dir" | xargs)  # trim
    target="$REPO_PATH/$dir"
    if [ -d "$target" ]; then
      eval "find '$target' $FIND_EXCLUDES -type f $NAME_EXCLUDES -print" >> "$FILES_OUT" 2>/dev/null || true
    fi
  done
else
  eval "find '$REPO_PATH' $FIND_EXCLUDES -type f $NAME_EXCLUDES -print" > "$FILES_OUT" 2>/dev/null || true
fi

# 相対パスに変換
if [ -s "$FILES_OUT" ]; then
  TMP_REL="/tmp/deepwiki_files_rel.txt"
  while IFS= read -r f; do
    echo "${f#$REPO_PATH/}"
  done < "$FILES_OUT" > "$TMP_REL"
  mv "$TMP_REL" "$FILES_OUT"
fi

# ツリー構造の生成
if command -v tree &>/dev/null; then
  TREE_PRUNE=""
  for dir in "${EXCLUDE_DIRS[@]}"; do
    TREE_PRUNE="$TREE_PRUNE -I '$dir'"
  done
  eval "tree '$REPO_PATH' -L 4 --noreport --charset ascii $TREE_PRUNE" > "$TREE_OUT" 2>/dev/null || true
else
  # tree がない場合は find + sed で簡易ツリー
  echo "$REPO_PATH" > "$TREE_OUT"
  head -200 "$FILES_OUT" | sort | sed 's|[^/]*/|  |g' >> "$TREE_OUT"
fi

# README の抽出
README_FILE=""
for name in README.md README.rst README.txt README readme.md; do
  if [ -f "$REPO_PATH/$name" ]; then
    README_FILE="$REPO_PATH/$name"
    break
  fi
done

if [ -n "$README_FILE" ]; then
  head -200 "$README_FILE" > "$README_OUT"
else
  echo "(README not found)" > "$README_OUT"
fi

# 統計情報
FILE_COUNT=$(wc -l < "$FILES_OUT" | xargs)
echo "=== DeepWiki Creator: File Collection Stats ===" > "$STATS_OUT"
echo "Repository: $REPO_PATH" >> "$STATS_OUT"
echo "Total files: $FILE_COUNT" >> "$STATS_OUT"
echo "" >> "$STATS_OUT"
echo "Top extensions:" >> "$STATS_OUT"
sed 's/.*\.//' "$FILES_OUT" | sort | uniq -c | sort -rn | head -15 >> "$STATS_OUT"
echo "" >> "$STATS_OUT"
echo "Top directories:" >> "$STATS_OUT"
cut -d'/' -f1 "$FILES_OUT" | sort | uniq -c | sort -rn | head -15 >> "$STATS_OUT"

cat "$STATS_OUT"

echo ""
echo "Output files:"
echo "  $FILES_OUT"
echo "  $TREE_OUT"
echo "  $README_OUT"
