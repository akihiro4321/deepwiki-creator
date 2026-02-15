#!/usr/bin/env bash
# deepwiki-creator: コード偵察スクリプト v3（Code Reconnaissance）
# コードの export/import、設定ファイル、拡張機構定義を抽出する。
#
# 使用法: bash recon_code.sh <REPO_PATH> [INCLUDE_DIRS]
# 前提: collect_files.sh が実行済みで /tmp/deepwiki_files.txt が存在すること
# 出力: /tmp/deepwiki_recon.md

set -euo pipefail

REPO_PATH="${1:-.}"
INCLUDE_DIRS="${2:-}"

REPO_PATH="$(cd "$REPO_PATH" && pwd)"
RECON_OUT="/tmp/deepwiki_recon.md"
FILES_LIST="/tmp/deepwiki_files.txt"

if [ ! -f "$FILES_LIST" ]; then
  echo "ERROR: $FILES_LIST not found. Run collect_files.sh first."
  exit 1
fi

# INCLUDE_DIRS フィルタ
filter_files() {
  if [ -n "$INCLUDE_DIRS" ]; then
    IFS=',' read -ra DIRS <<< "$INCLUDE_DIRS"
    while IFS= read -r f; do
      for dir in "${DIRS[@]}"; do
        dir=$(echo "$dir" | xargs | sed 's|/$||')
        if echo "$f" | grep -q "^${dir}/\|^${dir}$"; then
          echo "$f"
          break
        fi
      done
    done
  else
    cat
  fi
}

cat "$FILES_LIST" | filter_files > /tmp/deepwiki_recon_targets.txt
TARGET_COUNT=$(wc -l < /tmp/deepwiki_recon_targets.txt | xargs)

cat > "$RECON_OUT" << EOF
# Code Reconnaissance Report

Generated: $(date -Iseconds 2>/dev/null || date)
Repository: $REPO_PATH
Files scanned: $TARGET_COUNT

EOF

# ============================================================
# 1. エントリーポイントと設定ファイル
# ============================================================
echo "## 1. エントリーポイントと設定ファイル" >> "$RECON_OUT"
echo "" >> "$RECON_OUT"

CONFIG_NAMES="package.json pyproject.toml Cargo.toml go.mod build.gradle pom.xml setup.py setup.cfg CMakeLists.txt Makefile Gemfile composer.json"

for config_name in $CONFIG_NAMES; do
  while IFS= read -r f; do
    full_path="$REPO_PATH/$f"
    [ ! -f "$full_path" ] && continue
    echo "### \`$f\`" >> "$RECON_OUT"
    echo '```' >> "$RECON_OUT"
    case "$f" in
      *package.json)
        grep -E '^\s*"(name|version|main|bin|exports|scripts|dependencies|devDependencies|peerDependencies)"' "$full_path" 2>/dev/null | head -60 >> "$RECON_OUT" || true
        ;;
      *pyproject.toml)
        grep -E '^\[|^name |^version |^dependencies|^scripts|^entry' "$full_path" 2>/dev/null | head -40 >> "$RECON_OUT" || true
        ;;
      *)
        head -40 "$full_path" >> "$RECON_OUT" 2>/dev/null || true
        ;;
    esac
    echo '```' >> "$RECON_OUT"
    echo "" >> "$RECON_OUT"
  done < <(grep -E "(^|/)${config_name}$" /tmp/deepwiki_recon_targets.txt 2>/dev/null || true)
done

# ============================================================
# 2. Export / Public API 一覧
# ============================================================
echo "## 2. Export / Public API 一覧" >> "$RECON_OUT"
echo "" >> "$RECON_OUT"

grep -E '\.(ts|tsx|js|jsx|py|go|rs|java|kt|rb|cs|php|swift|dart)$' /tmp/deepwiki_recon_targets.txt \
  | grep -viE '(\.test\.|\.spec\.|__test__|_test\.go|test_|\.d\.ts$|\.stories\.)' \
  | head -250 \
  | while IFS= read -r f; do
    full_path="$REPO_PATH/$f"
    [ ! -f "$full_path" ] && continue

    ext="${f##*.}"
    signatures=""

    case "$ext" in
      ts|tsx|js|jsx)
        signatures=$(grep -nE '^\s*export\s+(default\s+)?(class|function|const|let|interface|type|enum|abstract\s+class)\s+' "$full_path" 2>/dev/null \
          | head -25 | sed 's/^\([0-9]*\):/L\1: /' || true)
        ;;
      py)
        signatures=$(grep -nE '^(class |def |async def )' "$full_path" 2>/dev/null \
          | head -25 | sed 's/^\([0-9]*\):/L\1: /' || true)
        ;;
      go)
        signatures=$(grep -nE '^(func |type )[A-Z]' "$full_path" 2>/dev/null \
          | head -25 | sed 's/^\([0-9]*\):/L\1: /' || true)
        ;;
      rs)
        signatures=$(grep -nE '^\s*pub\s+(fn|struct|enum|trait|type|const|static|mod)\s+' "$full_path" 2>/dev/null \
          | head -25 | sed 's/^\([0-9]*\):/L\1: /' || true)
        ;;
      java|kt)
        signatures=$(grep -nE '^\s*(public|protected)\s+(class|interface|enum|abstract|static|final|fun|val|var)\s+' "$full_path" 2>/dev/null \
          | head -25 | sed 's/^\([0-9]*\):/L\1: /' || true)
        ;;
      rb)
        signatures=$(grep -nE '^\s*(class |module |def )' "$full_path" 2>/dev/null \
          | head -25 | sed 's/^\([0-9]*\):/L\1: /' || true)
        ;;
      cs)
        signatures=$(grep -nE '^\s*(public|internal|protected)\s+(class|interface|struct|enum|record|static)\s+' "$full_path" 2>/dev/null \
          | head -25 | sed 's/^\([0-9]*\):/L\1: /' || true)
        ;;
      php)
        signatures=$(grep -nE '^\s*(class |function |interface |trait |enum )' "$full_path" 2>/dev/null \
          | head -25 | sed 's/^\([0-9]*\):/L\1: /' || true)
        ;;
      swift)
        signatures=$(grep -nE '^\s*(public |open )?(class |struct |enum |protocol |func |var |let )' "$full_path" 2>/dev/null \
          | head -25 | sed 's/^\([0-9]*\):/L\1: /' || true)
        ;;
      dart)
        signatures=$(grep -nE '^(class |abstract class |mixin |extension |enum )' "$full_path" 2>/dev/null \
          | head -25 | sed 's/^\([0-9]*\):/L\1: /' || true)
        ;;
    esac

    if [ -n "$signatures" ]; then
      line_count=$(wc -l < "$full_path" | xargs)
      echo "### \`$f\` (${line_count} lines)" >> "$RECON_OUT"
      echo '```' >> "$RECON_OUT"
      echo "$signatures" >> "$RECON_OUT"
      echo '```' >> "$RECON_OUT"
      echo "" >> "$RECON_OUT"
    fi
  done

# ============================================================
# 3. 拡張機構の検出（プラグイン・スキル・フック・コマンド等）
# ============================================================
echo "## 3. 拡張機構の検出" >> "$RECON_OUT"
echo "" >> "$RECON_OUT"
echo "コードファイル以外で機能を定義する仕組み（プラグイン、スキル、フック、" >> "$RECON_OUT"
echo "カスタムコマンド、ミドルウェア、設定ベースのルーティング等）を検出する。" >> "$RECON_OUT"
echo "" >> "$RECON_OUT"

EXTENSION_FOUND=0

# 3a. SKILL.md / AGENTS.md（Gemini CLI Agent Skills / Agents）
while IFS= read -r f; do
  if echo "$f" | grep -qiE '(SKILL\.md|agents?/.*\.md)'; then
    echo "**Agent/Skill定義**: \`$f\`" >> "$RECON_OUT"
    head -15 "$REPO_PATH/$f" >> "$RECON_OUT" 2>/dev/null || true
    echo "" >> "$RECON_OUT"
    EXTENSION_FOUND=1
  fi
done < /tmp/deepwiki_recon_targets.txt

# 3b. .toml カスタムコマンド
while IFS= read -r f; do
  if echo "$f" | grep -qiE 'commands?/.*\.toml'; then
    echo "**カスタムコマンド**: \`$f\`" >> "$RECON_OUT"
    head -10 "$REPO_PATH/$f" >> "$RECON_OUT" 2>/dev/null || true
    echo "" >> "$RECON_OUT"
    EXTENSION_FOUND=1
  fi
done < /tmp/deepwiki_recon_targets.txt

# 3c. hooks / middleware / plugins ディレクトリ
while IFS= read -r f; do
  if echo "$f" | grep -qiE '(hooks?|middleware|plugins?|extensions?)/' | head -20; then
    echo "**拡張機構ファイル**: \`$f\`" >> "$RECON_OUT"
    EXTENSION_FOUND=1
  fi
done < /tmp/deepwiki_recon_targets.txt | head -30 >> "$RECON_OUT" 2>/dev/null || true

# 3d. Django urls.py / FastAPI router / Express router / Rails routes
while IFS= read -r f; do
  if echo "$f" | grep -qiE '(urls\.py|routes?\.(ts|js|rb|py)|router\.(ts|js))'; then
    echo "**ルーティング定義**: \`$f\`" >> "$RECON_OUT"
    EXTENSION_FOUND=1
  fi
done < /tmp/deepwiki_recon_targets.txt | head -20 >> "$RECON_OUT" 2>/dev/null || true

# 3e. YAML/JSON 設定による機能定義（CI, IaC, schema等）
while IFS= read -r f; do
  if echo "$f" | grep -qiE '\.(ya?ml|json)$' | grep -viE '(package\.json|tsconfig|\.eslint|\.prettier|node_modules)'; then
    case "$f" in
      *docker-compose*|*serverless*|*terraform*|*.github/workflows/*|*openapi*|*swagger*|*schema*)
        echo "**インフラ/スキーマ定義**: \`$f\`" >> "$RECON_OUT"
        EXTENSION_FOUND=1
        ;;
    esac
  fi
done < /tmp/deepwiki_recon_targets.txt | head -20 >> "$RECON_OUT" 2>/dev/null || true

# 3f. デコレータ・アノテーションベースの機能登録パターン
DECORATOR_FILES=$(grep -rlE '^\s*@(app\.|router\.|api\.|Controller|Injectable|Component|Module|Plugin|Hook|Command)' "$REPO_PATH" \
  --include='*.ts' --include='*.py' --include='*.java' --include='*.kt' 2>/dev/null \
  | head -20 | sed "s|^$REPO_PATH/||" || true)

if [ -n "$DECORATOR_FILES" ]; then
  echo "**デコレータベース機能登録**:" >> "$RECON_OUT"
  echo "$DECORATOR_FILES" | while IFS= read -r f; do
    echo "  - \`$f\`" >> "$RECON_OUT"
  done
  echo "" >> "$RECON_OUT"
  EXTENSION_FOUND=1
fi

# 3g. コード内拡張ポイント（ローダー、パーサー、レジストリ等）
# ファイルスキャンでは検出できない拡張機構を、コード内の関数名から推定する
EXTENSION_FUNCS=$(grep -rlE '(loadAgents|loadPlugins|loadExtensions|loadCommands|parseAgent|discoverTools|registerTool|registerPlugin|registerHook|registerMiddleware|loadFromDirectory|parseMarkdown.*agent|fromDirectory)' "$REPO_PATH" \
  --include='*.ts' --include='*.js' --include='*.py' --include='*.go' --include='*.rs' 2>/dev/null \
  | head -20 | sed "s|^$REPO_PATH/||" || true)

if [ -n "$EXTENSION_FUNCS" ]; then
  echo "**コード内拡張ポイント（loader/parser/register パターン）**:" >> "$RECON_OUT"
  echo "" >> "$RECON_OUT"
  echo "$EXTENSION_FUNCS" | while IFS= read -r f; do
    echo "  - \`$f\`" >> "$RECON_OUT"
    # 該当する関数のシグネチャを抽出
    grep -nE '(export )?(async )?(function |const |def |func )(load|parse|discover|register)' "$REPO_PATH/$f" 2>/dev/null \
      | head -5 | sed 's/^/    /' >> "$RECON_OUT" || true
  done
  echo "" >> "$RECON_OUT"
  EXTENSION_FOUND=1
fi

if [ "$EXTENSION_FOUND" -eq 0 ]; then
  echo "(拡張機構の定義ファイルは検出されませんでした)" >> "$RECON_OUT"
fi
echo "" >> "$RECON_OUT"

# ============================================================
# 4. モジュール間依存関係
# ============================================================
echo "## 4. モジュール間依存関係" >> "$RECON_OUT"
echo "" >> "$RECON_OUT"

# TypeScript/JavaScript
grep -E '\.(ts|tsx|js|jsx)$' /tmp/deepwiki_recon_targets.txt \
  | grep -viE '(\.test\.|\.spec\.|\.d\.ts$)' \
  | head -150 \
  | while IFS= read -r f; do
    full_path="$REPO_PATH/$f"
    [ ! -f "$full_path" ] && continue
    imports=$(grep -oE "from ['\"]\.\.?/[^'\"]+['\"]" "$full_path" 2>/dev/null \
      | sed "s/from ['\"]//;s/['\"]$//" | head -15 || true)
    if [ -n "$imports" ]; then
      echo "**\`$f\`** imports:" >> "$RECON_OUT"
      echo "$imports" | while IFS= read -r imp; do echo "  - \`$imp\`" >> "$RECON_OUT"; done
      echo "" >> "$RECON_OUT"
    fi
  done

# Python
grep -E '\.py$' /tmp/deepwiki_recon_targets.txt \
  | grep -viE '(test_|_test\.py$|conftest\.py$)' \
  | head -150 \
  | while IFS= read -r f; do
    full_path="$REPO_PATH/$f"
    [ ! -f "$full_path" ] && continue
    imports=$(grep -E '^from \.' "$full_path" 2>/dev/null | head -15 || true)
    if [ -n "$imports" ]; then
      echo "**\`$f\`** imports:" >> "$RECON_OUT"
      echo "$imports" | while IFS= read -r imp; do echo "  - \`$imp\`" >> "$RECON_OUT"; done
      echo "" >> "$RECON_OUT"
    fi
  done

# Go
grep -E '\.go$' /tmp/deepwiki_recon_targets.txt \
  | grep -viE '_test\.go$' \
  | head -100 \
  | while IFS= read -r f; do
    full_path="$REPO_PATH/$f"
    [ ! -f "$full_path" ] && continue
    # 同一モジュール内の相対 import を抽出
    mod_path=$(grep -m1 '^module ' "$REPO_PATH/go.mod" 2>/dev/null | awk '{print $2}' || true)
    if [ -n "$mod_path" ]; then
      imports=$(grep -oE "\"${mod_path}/[^\"]+\"" "$full_path" 2>/dev/null \
        | sed "s|\"${mod_path}/||;s|\"||g" | head -15 || true)
      if [ -n "$imports" ]; then
        echo "**\`$f\`** imports:" >> "$RECON_OUT"
        echo "$imports" | while IFS= read -r imp; do echo "  - \`$imp\`" >> "$RECON_OUT"; done
        echo "" >> "$RECON_OUT"
      fi
    fi
  done

# ============================================================
# 5. ディレクトリ別サマリー
# ============================================================
echo "## 5. ディレクトリ別サマリー" >> "$RECON_OUT"
echo "" >> "$RECON_OUT"
echo "| ディレクトリ | ファイル数 | 主な拡張子 |" >> "$RECON_OUT"
echo "|-------------|-----------|-----------|" >> "$RECON_OUT"

cat /tmp/deepwiki_recon_targets.txt \
  | awk -F'/' '{if(NF>=2) print $1"/"$2; else print $1}' \
  | sort | uniq -c | sort -rn | head -30 \
  | while read -r count dir; do
    top_ext=$(grep "^${dir}/" /tmp/deepwiki_recon_targets.txt 2>/dev/null \
      | sed 's/.*\.//' | sort | uniq -c | sort -rn | head -3 \
      | awk '{printf "%s ", $2}' || echo "-")
    echo "| \`$dir\` | $count | $top_ext |" >> "$RECON_OUT"
  done

echo "" >> "$RECON_OUT"

# ============================================================
# 統計
# ============================================================
RECON_LINES=$(wc -l < "$RECON_OUT" | xargs)
EXPORT_COUNT=$(grep -c '^\s*L[0-9]*:' "$RECON_OUT" 2>/dev/null || echo 0)
EXT_SECTION=$(grep -c '拡張機構' "$RECON_OUT" 2>/dev/null || echo 0)

echo "=== Code Reconnaissance Complete ==="
echo "Output: $RECON_OUT ($RECON_LINES lines)"
echo "Exports found: ~$EXPORT_COUNT"
echo "Extension mechanisms detected: $([ "$EXTENSION_FOUND" -eq 1 ] && echo 'Yes' || echo 'No')"
echo ""
echo "Use this file as input for Step 2 (Wiki Structure Design)."
