#!/usr/bin/env python3
"""
全WikiページのMermaidダイアグラムのルール違反を静的チェックし、
違反があればGemini CLIで修正するスクリプト。
generate_pages.py の全ページ生成完了後に呼び出す。

使用方法:
    python3 scripts/fix_mermaid.py $OUTPUT_DIR/outline.json
"""
import os
import sys
import json
import re
import asyncio
import argparse
from typing import List, Tuple, Optional

# --- Configuration ---
MAX_FIX_RETRIES = 1
GEMINI_TIMEOUT_SECONDS = 180

MERMAID_BLOCK_RE = re.compile(r'```mermaid\n(.*?)```', re.DOTALL)


def extract_mermaid_blocks(content: str) -> List[str]:
    """MarkdownコンテンツからMermaidブロックのコードを抽出する"""
    return MERMAID_BLOCK_RE.findall(content)


def check_violations(mermaid_code: str) -> List[str]:
    """
    Mermaidコードのルール違反を検出し、違反メッセージのリストを返す。
    違反がなければ空リストを返す。
    """
    violations = []

    # ルール1: LRレイアウト禁止
    if re.search(r'\b(?:graph|flowchart)\s+LR\b', mermaid_code):
        violations.append(
            "LRレイアウトが使用されています（graph LR / flowchart LR）。"
            "必ず TD を使用してください。"
        )

    # ルール2: ノードIDにハイフンを含む
    if re.search(r'\b[A-Za-z][A-Za-z0-9]*(?:-[A-Za-z0-9]+)+\s*[\[\({"\'`]', mermaid_code):
        violations.append(
            "ノードIDにハイフンが含まれています。"
            "アンダースコアに置き換えてください（例: my-node → my_node）。"
        )

    # ルール3: [] 内に () が含まれているのにクォートされていない
    # 例: D[Data Pipeline (api/data.py)] → NG
    unquoted_bracket_paren = re.findall(r'\[[^\]"]*\([^)]*\)[^\]"]*\]', mermaid_code)
    if unquoted_bracket_paren:
        violations.append(
            f'ノード定義 [] 内に括弧 () が含まれているのに [""] でクォートされていません: '
            f'{unquoted_bracket_paren[:2]}。必ず ["ラベル (補足)"] 形式を使用してください。'
        )

    # ルール4: () 内に [] が含まれているのにクォートされていない
    # 例: cmd(CMD ["/app/start.sh"]) → NG
    unquoted_paren_bracket = re.findall(r'\([^)"]*\[[^\]]*\][^)"]*\)', mermaid_code)
    if unquoted_paren_bracket:
        violations.append(
            f'ノード定義 () 内に角括弧 [] が含まれているのにクォートされていません: '
            f'{unquoted_paren_bracket[:2]}。クォートするか記号を削除してください。'
        )

    # ルール5: HTMLタグ（< > を含む記述）
    if re.search(r'<[a-zA-Z][^>]*>', mermaid_code):
        violations.append(
            "HTMLタグが使用されています（< > 記号）。"
            "Mermaidでは使用不可のため削除してください。"
        )

    # ルール6: シーケンス図でのフローチャート風記法
    if 'sequenceDiagram' in mermaid_code:
        if re.search(r'--\|[^|]*\|-->', mermaid_code):
            violations.append(
                "シーケンス図でフローチャート風の記法 A--|label|-->B が使われています。"
                "コロン記法（A->>B: label）を使用してください。"
            )

    return violations


def build_fix_prompt(file_path: str, violations_by_block: List[Tuple[str, List[str]]]) -> str:
    """Mermaid修正用のGeminiプロンプトを生成する"""
    violations_text = ""
    for i, (block, viols) in enumerate(violations_by_block):
        violations_text += f"\n### 違反ブロック {i + 1}\n"
        violations_text += f"```mermaid\n{block}\n```\n"
        violations_text += "**違反内容:**\n"
        for v in viols:
            violations_text += f"- {v}\n"

    return f"""以下のMarkdownファイルのMermaidダイアグラムにルール違反があります。
違反のあるMermaidブロックのみを修正して、ファイルを上書き保存してください。
**Mermaid以外の部分（テキスト、コードスニペット、Sources行など）は絶対に変更しないこと。**

ファイルパス: `{file_path}`

## 検出された違反
{violations_text}

## Mermaidダイアグラム修正ルール（必須・絶対厳守）

MarkdownパーサーおよびMermaidレンダリングエンジンでの**パースエラー・描画不能を絶対に防ぐため、以下のルールを完全に遵守すること。**

### 1. 縦方向 (Vertical) レイアウトの強制
- フローダイアグラムの指定には必ず `graph TD` または `flowchart TD` を使用すること。（LRは禁止）
- ノード内のテキストは最大でも3-4単語に収め、横幅が長くなりすぎないようにすること。

### 2. シーケンス図 (Sequence Diagrams) の厳格なルール
- 先頭行に必ず単独で `sequenceDiagram` を配置し、直後に participant を定義すること。
- 以下の矢印を意図に合わせて使用: `->>` (リクエスト), `-->>` (レスポンス), `-)` (非同期).
- アクティベーションボックスには必ず `+`/`-` プレフィックスを使用すること（例: `A->>+B: Start`, `B-->>-A: End`）。
- メッセージへのラベル付与にはコロン（`:`）を用いること。**絶対にフローチャート風の `A--|label|-->B` 表記を使用しないこと。**

### 3. 【致命的エラー防止: 全般的な構文ルール】
以下のルールに違反すると、図がすべて表示されなくなる致命的なエラーを引き起こす。

- ノードラベルに `()`、`[]`、`{{}}` などの括弧や記号類が含まれる場合は、**例外なく必ず `["ラベル"]` のようにダブルクォーテーションで囲む**こと。
  - **【頻出エラー1】** `D[Data Pipeline (api/data_pipeline.py)]` のように `[]` の内側に `()` を含むとパースエラーで図が崩壊します。**必ず `D["Data Pipeline (api/data_pipeline.py)"]` とクォートで囲むこと。**
  - **【頻出エラー2】** `cmd_start_sh(CMD ["/app/start.sh"])` のように `()` の内側に `[]` 等が含まれる場合もパースエラーになります。**必ず `cmd_start_sh("CMD /app/start.sh")` のようにクォートするか、記号を削除してください。**
- HTMLタグは使用不可（`<` や `>` などの記号もパースエラーの原因）。
- ノード ID にハイフンを含めない（アンダースコアを使用すること）。
- 実際のソースコードに存在する**クラス名・関数名**をノードラベルに用いること。

修正後にファイルを保存し、修正した箇所を簡潔に報告してください。"""


async def run_gemini_fix(prompt: str, target_dir: str, output_dir: str) -> bool:
    """Gemini CLIを呼び出してMermaid違反を修正する"""
    include_dirs = ",".join(set([target_dir, output_dir]))
    cmd = [
        "gemini",
        "-m", "gemini-2.5-flash",
        "--approval-mode", "auto_edit",
        "--include-directories", include_dirs,
    ]

    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=target_dir,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(input=prompt.encode("utf-8")),
                timeout=GEMINI_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            process.kill()
            await process.communicate()
            print(f"    [Timeout] Gemini CLI timed out.")
            return False

        if process.returncode != 0:
            print(f"    [Error] Gemini CLI failed: {stderr.decode('utf-8', errors='ignore')[:300]}")
            return False

        return True
    except Exception as e:
        print(f"    [Exception] {e}")
        return False


async def fix_file(
    file_path: str,
    violations_by_block: List[Tuple[str, List[str]]],
    target_dir: str,
    output_dir: str,
) -> bool:
    """単一ファイルのMermaid違反をGeminiで修正し、修正後に再チェックする"""
    for attempt in range(MAX_FIX_RETRIES + 1):
        if attempt > 0:
            print(f"    Retry {attempt}/{MAX_FIX_RETRIES}...")

        prompt = build_fix_prompt(file_path, violations_by_block)
        success = await run_gemini_fix(prompt, target_dir, output_dir)

        if not success:
            continue

        # 修正後に再チェック
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            print(f"    [Error] Could not re-read file: {e}")
            return False

        blocks = extract_mermaid_blocks(content)
        remaining = [(b, check_violations(b)) for b in blocks if check_violations(b)]

        if not remaining:
            return True

        print(f"    {sum(len(v) for _, v in remaining)} violation(s) still remain after fix.")
        violations_by_block = remaining  # 次のリトライ用に更新

    return False


async def scan_and_fix(outline_path: str) -> None:
    """outline.json の全 done ページを走査してMermaid違反を検出・修正する"""
    with open(outline_path, "r", encoding="utf-8") as f:
        outline_data = json.load(f)

    output_dir = os.path.dirname(outline_path)
    target_dir = outline_data.get("targetDir", output_dir)
    if not os.path.isabs(target_dir):
        target_dir = os.path.abspath(os.path.join(output_dir, target_dir))

    pages = outline_data.get("pages", [])
    done_pages = [p for p in pages if p.get("status") == "done"]

    if not done_pages:
        print("No done pages found in outline.json.")
        return

    print(f"Scanning {len(done_pages)} pages for Mermaid violations...\n")

    total_violations = 0
    fixed_count = 0
    failed_files = []

    for page in done_pages:
        page_id = page.get("id", "?")
        filename = page.get("filename")
        if not filename:
            continue

        file_path = os.path.join(output_dir, filename)
        if not os.path.exists(file_path):
            print(f"  [{page_id}] ⚠️  File not found: {filename}")
            continue

        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        blocks = extract_mermaid_blocks(content)
        if not blocks:
            print(f"  [{page_id}] -  No Mermaid blocks.")
            continue

        violations_by_block = [(b, check_violations(b)) for b in blocks if check_violations(b)]

        if not violations_by_block:
            print(f"  [{page_id}] ✅ {len(blocks)} block(s) — all OK")
            continue

        violation_count = sum(len(v) for _, v in violations_by_block)
        total_violations += violation_count
        print(
            f"  [{page_id}] ❌ {violation_count} violation(s) in "
            f"{len(violations_by_block)} block(s). Fixing..."
        )

        success = await fix_file(file_path, violations_by_block, target_dir, output_dir)
        if success:
            print(f"  [{page_id}] ✅ Fixed.")
            fixed_count += 1
        else:
            print(f"  [{page_id}] 🛑 Fix failed.")
            failed_files.append(filename)

    print(f"\n{'=' * 50}")
    print(f"Mermaid scan complete.")
    print(f"  Total violations detected : {total_violations}")
    print(f"  Files fixed               : {fixed_count}")
    if failed_files:
        print(f"  Files failed to fix       : {len(failed_files)}")
        for f in failed_files:
            print(f"    - {f}")


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="DeepWiki Mermaid rule checker & fixer"
    )
    parser.add_argument("outline_json", help="Path to the outline.json file")
    args = parser.parse_args()

    outline_path = os.path.abspath(args.outline_json)
    if not os.path.exists(outline_path):
        print(f"Error: outline.json not found at {outline_path}")
        sys.exit(1)

    await scan_and_fix(outline_path)


if __name__ == "__main__":
    asyncio.run(main())
