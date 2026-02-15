#!/usr/bin/env bash
# deepwiki-creator: Wiki検証スクリプト v3
# JSON構文、コードスニペット、Mermaid図、行数、リンク整合性、重複をチェック
# 使用法: bash validate_wiki.sh <OUTPUT_DIR>

set -euo pipefail

OUTPUT_DIR="${1:-.}"
ERRORS=0
WARNINGS=0
MIN_LINES=60

echo "========================================="
echo "  DeepWiki Creator: Validation v3"
echo "========================================="
echo "Output directory: $OUTPUT_DIR"
echo ""

# ============================================================
# 1. _meta.json 構文チェック
# ============================================================
echo "--- 1. JSON Syntax Check ---"

if [ ! -f "$OUTPUT_DIR/_meta.json" ]; then
  echo "❌ ERROR: _meta.json not found"
  ERRORS=$((ERRORS + 1))
else
  # コメント（//）のチェック
  if grep -qE '^\s*//' "$OUTPUT_DIR/_meta.json" 2>/dev/null || grep -qE '\s+//' "$OUTPUT_DIR/_meta.json" 2>/dev/null; then
    echo "❌ ERROR: _meta.json contains comments (// ...). JSON does not support comments."
    grep -nE '//' "$OUTPUT_DIR/_meta.json" | head -5
    ERRORS=$((ERRORS + 1))
  fi

  # JSON構文チェック（python/node で）
  JSON_VALID=0
  if command -v python3 &>/dev/null; then
    if python3 -c "import json; json.load(open('$OUTPUT_DIR/_meta.json'))" 2>/dev/null; then
      JSON_VALID=1
    fi
  elif command -v node &>/dev/null; then
    if node -e "JSON.parse(require('fs').readFileSync('$OUTPUT_DIR/_meta.json','utf8'))" 2>/dev/null; then
      JSON_VALID=1
    fi
  else
    # python/node がない場合はスキップ
    echo "⚠️  Cannot validate JSON syntax (python3/node not found)"
    WARNINGS=$((WARNINGS + 1))
    JSON_VALID=1
  fi

  if [ "$JSON_VALID" -eq 1 ]; then
    echo "✅ _meta.json is valid JSON"
  else
    echo "❌ ERROR: _meta.json has invalid JSON syntax"
    ERRORS=$((ERRORS + 1))
  fi
fi

# ============================================================
# 2. 基本構造チェック
# ============================================================
echo ""
echo "--- 2. Structure Check ---"

if [ ! -f "$OUTPUT_DIR/index.md" ]; then
  echo "❌ ERROR: index.md not found"
  ERRORS=$((ERRORS + 1))
else
  echo "✅ index.md exists"
fi

if [ ! -d "$OUTPUT_DIR/sections" ]; then
  echo "❌ ERROR: sections/ directory not found"
  ERRORS=$((ERRORS + 1))
fi

MD_FILES=$(find "$OUTPUT_DIR/sections" -name "*.md" -type f 2>/dev/null | sort || true)
MD_COUNT=$(echo "$MD_FILES" | grep -c '.' 2>/dev/null || echo 0)
echo "📄 Total pages: $MD_COUNT"

# ページ数最低ラインチェック（comprehensive モード）
MODE=$(python3 -c "import json; d=json.load(open('$OUTPUT_DIR/_meta.json')); print(d.get('mode',''))" 2>/dev/null || true)
if [ "$MODE" = "comprehensive" ] && [ "$MD_COUNT" -lt 15 ]; then
  echo "⚠️  WARNING: Comprehensive mode requires >= 15 pages, found $MD_COUNT"
  WARNINGS=$((WARNINGS + 1))
fi

# _meta.json フィールド検証
if [ -f "$OUTPUT_DIR/_meta.json" ] && [ "$JSON_VALID" -eq 1 ]; then
  MISSING_FIELDS=$(python3 -c "
import json, sys
d = json.load(open('$OUTPUT_DIR/_meta.json'))
missing = 0
for s in d.get('sections', []):
  for p in s.get('pages', []):
    for f in ['relevant_files', 'primary_exports', 'suggested_diagrams', 'related_pages']:
      if f not in p:
        print(f'  Page {p.get(\"id\",\"?\")} missing field: {f}')
        missing += 1
sys.exit(missing)
" 2>/dev/null)
  FIELD_EXIT=$?
  if [ "$FIELD_EXIT" -gt 0 ]; then
    echo "⚠️  WARNING: _meta.json has $FIELD_EXIT missing fields:"
    echo "$MISSING_FIELDS"
    WARNINGS=$((WARNINGS + 1))
  fi
fi

# ============================================================
# 3. リンク検証
# ============================================================
echo ""
echo "--- 3. Link Validation ---"

BROKEN_LINKS=0
if [ -f "$OUTPUT_DIR/index.md" ]; then
  while IFS= read -r link; do
    path=$(echo "$link" | grep -oP '\]\(\K[^)]+' | head -1)
    if [ -n "$path" ]; then
      full_path="$OUTPUT_DIR/$path"
      if [ ! -f "$full_path" ]; then
        echo "❌ Broken link in index.md: $path"
        BROKEN_LINKS=$((BROKEN_LINKS + 1))
        ERRORS=$((ERRORS + 1))
      fi
    fi
  done < <(grep -oP '\[.*?\]\(\.\/.*?\)' "$OUTPUT_DIR/index.md" 2>/dev/null || true)
fi

# ページ内リンク
BROKEN_INTERNAL=0
for md_file in $MD_FILES; do
  md_dir=$(dirname "$md_file")
  while IFS= read -r link; do
    path=$(echo "$link" | grep -oP '\]\(\K[^)#]+' | head -1)
    if [ -n "$path" ] && [[ "$path" != http* ]]; then
      target="$md_dir/$path"
      if [ ! -f "$target" ]; then
        echo "⚠️  Broken link in $(basename "$md_file"): $path"
        BROKEN_INTERNAL=$((BROKEN_INTERNAL + 1))
        WARNINGS=$((WARNINGS + 1))
      fi
    fi
  done < <(grep -oP '\[.*?\]\([^)]+\)' "$md_file" 2>/dev/null | grep -v 'http' || true)
done

[ "$BROKEN_LINKS" -eq 0 ] && [ "$BROKEN_INTERNAL" -eq 0 ] && echo "✅ All links valid"

# ============================================================
# 4. ページ別品質チェック
# ============================================================
echo ""
echo "--- 4. Per-Page Quality ---"
echo ""

PAGES_WITHOUT_CODE=0
PAGES_WITHOUT_MERMAID=0
PAGES_TOO_SHORT=0
TOTAL_DIAGRAMS=0
TOTAL_SNIPPETS=0
UNCLOSED_MERMAID=0

printf "%-35s %5s %5s %5s %s\n" "Page" "Lines" "Code" "Diag" "Status"
printf "%-35s %5s %5s %5s %s\n" "---" "---" "---" "---" "---"

for md_file in $MD_FILES; do
  fname=$(basename "$md_file" .md)
  line_count=$(wc -l < "$md_file" | xargs)
  
  # Mermaid図カウント
  diag_count=$(grep -c '```mermaid' "$md_file" 2>/dev/null || echo 0)
  TOTAL_DIAGRAMS=$((TOTAL_DIAGRAMS + diag_count))
  
  # コードスニペットカウント（mermaid以外）
  all_code=$(grep -c '^```[a-z]' "$md_file" 2>/dev/null || echo 0)
  snippet_count=$((all_code - diag_count))
  [ "$snippet_count" -lt 0 ] && snippet_count=0
  TOTAL_SNIPPETS=$((TOTAL_SNIPPETS + snippet_count))

  # ステータス判定
  status=""
  if [ "$line_count" -lt "$MIN_LINES" ]; then
    status="${status}⚠️短 "
    PAGES_TOO_SHORT=$((PAGES_TOO_SHORT + 1))
    WARNINGS=$((WARNINGS + 1))
  fi
  if [ "$snippet_count" -eq 0 ]; then
    status="${status}⚠️コード無 "
    PAGES_WITHOUT_CODE=$((PAGES_WITHOUT_CODE + 1))
    WARNINGS=$((WARNINGS + 1))
  fi
  if [ "$diag_count" -eq 0 ]; then
    status="${status}⚠️図無 "
    PAGES_WITHOUT_MERMAID=$((PAGES_WITHOUT_MERMAID + 1))
    WARNINGS=$((WARNINGS + 1))
  fi

  # Mermaid閉じタグチェック
  if [ "$diag_count" -gt 0 ]; then
    in_mermaid=0
    while IFS= read -r line; do
      if echo "$line" | grep -q '```mermaid'; then in_mermaid=1;
      elif [ "$in_mermaid" -eq 1 ] && echo "$line" | grep -q '^```$'; then in_mermaid=0; fi
    done < "$md_file"
    if [ "$in_mermaid" -eq 1 ]; then
      status="${status}❌mermaid未閉 "
      UNCLOSED_MERMAID=$((UNCLOSED_MERMAID + 1))
      ERRORS=$((ERRORS + 1))
    fi
  fi

  [ -z "$status" ] && status="✅"
  printf "%-35s %5d %5d %5d %s\n" "$fname" "$line_count" "$snippet_count" "$diag_count" "$status"
done

# ============================================================
# 5. 空ファイルチェック
# ============================================================
echo ""
echo "--- 5. Empty File Check ---"

EMPTY_COUNT=0
for md_file in $MD_FILES; do
  if [ ! -s "$md_file" ]; then
    echo "❌ Empty file: $(basename "$md_file")"
    EMPTY_COUNT=$((EMPTY_COUNT + 1))
    ERRORS=$((ERRORS + 1))
  fi
done
[ "$EMPTY_COUNT" -eq 0 ] && echo "✅ No empty files"

# ============================================================
# 6. 重複チェック
# ============================================================
echo ""
echo "--- 6. Overlap Detection ---"

if [ "$MD_COUNT" -gt 1 ]; then
  ALL_H2S=""
  for md_file in $MD_FILES; do
    while IFS= read -r h; do
      ALL_H2S="${ALL_H2S}$(basename "$md_file"):${h#\#\# }\n"
    done < <(grep '^## ' "$md_file" 2>/dev/null || true)
  done

  OVERLAP_FOUND=0
  echo -e "$ALL_H2S" | sed 's/^[^:]*://' | sort | uniq -d | while IFS= read -r dup; do
    [ -z "$dup" ] && continue
    # 共通見出し（アーキテクチャ、関連ページ等）は除外
    if ! echo "$dup" | grep -qiE '^(アーキテクチャ|Architecture|関連ページ|Related|設定|Config|データフロー|Data Flow|エラーハンドリング|Error)'; then
      files=$(echo -e "$ALL_H2S" | grep ":${dup}$" | sed 's/:.*//' | tr '\n' ', ' | sed 's/,$//')
      echo "⚠️  Similar heading \"$dup\" in: $files"
      OVERLAP_FOUND=1
    fi
  done

  [ "$OVERLAP_FOUND" -eq 0 ] && echo "✅ No significant overlaps"
fi

# ============================================================
# サマリー
# ============================================================
echo ""
echo "========================================="
echo "         Validation Summary"
echo "========================================="
echo ""
echo "📄 Pages: $MD_COUNT"
echo "📊 Mermaid diagrams: $TOTAL_DIAGRAMS"
echo "💻 Code snippets: $TOTAL_SNIPPETS"
echo ""
echo "Quality Checks:"
if [ "$PAGES_WITHOUT_CODE" -eq 0 ]; then
  echo "  ✅ Code snippets: All pages have snippets"
else
  echo "  ⚠️  Code snippets: $PAGES_WITHOUT_CODE page(s) missing"
fi
if [ "$PAGES_WITHOUT_MERMAID" -eq 0 ]; then
  echo "  ✅ Mermaid diagrams: All pages have diagrams"
else
  echo "  ⚠️  Mermaid diagrams: $PAGES_WITHOUT_MERMAID page(s) missing"
fi
if [ "$PAGES_TOO_SHORT" -eq 0 ]; then
  echo "  ✅ Page depth: All pages >= $MIN_LINES lines"
else
  echo "  ⚠️  Page depth: $PAGES_TOO_SHORT page(s) under $MIN_LINES lines"
fi
if [ "$BROKEN_LINKS" -eq 0 ] && [ "$BROKEN_INTERNAL" -eq 0 ]; then
  echo "  ✅ Links: All valid"
else
  echo "  ❌ Links: $((BROKEN_LINKS + BROKEN_INTERNAL)) broken"
fi
if [ "$UNCLOSED_MERMAID" -eq 0 ]; then
  echo "  ✅ Mermaid syntax: All blocks closed"
else
  echo "  ❌ Mermaid syntax: $UNCLOSED_MERMAID unclosed block(s)"
fi
echo ""
echo "Total: $ERRORS error(s), $WARNINGS warning(s)"

if [ "$ERRORS" -eq 0 ] && [ "$WARNINGS" -eq 0 ]; then
  echo "🎉 Perfect! No issues found."
elif [ "$ERRORS" -eq 0 ]; then
  echo "✅ Passed with $WARNINGS warning(s)"
else
  echo "❌ Failed with $ERRORS error(s)"
fi

exit "$ERRORS"
