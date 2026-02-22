#!/usr/bin/env python3
import os
import sys
import json
import asyncio
import argparse
from typing import List, Dict, Any, Optional, Tuple

# --- Configuration ---
MAX_CONCURRENT_PAGES = 3
MAX_RETRIES = 2
GEMINI_TIMEOUT_SECONDS = 300 # 5 minutes

# --- Prompt Constants ---
PROMPT_SYSTEM_INSTRUCTION = """You are the deepwiki_page_generator, an expert technical documentation writer.
Your task is to write a single, highly detailed Wiki page based strictly on the provided context.
"""

PROMPT_FORMAT_INSTRUCTIONS = """
## 出力フォーマット仕様 (Output Format & Guidelines)

【執筆の最重要指示】
そこに定義されている「個別ページの模範構成テンプレート」に**最も厳格に**従ってMarkdownを出力してください。指定外の推測に基づいた情報は記述しないでください。

### 1. セクション構成の基本方針
- [Overview] プロジェクト概要、アーキテクチャ、モジュール構成
- [Getting Started] インストール、認証、設定
- [User Guide] ユーザー向け機能（コマンド、UI、操作方法等）
- [Core Systems] 内部アーキテクチャの主要モジュール
- [Advanced Topics] 拡張性、セキュリティ、可観測性、プラグイン等
- [Development] 開発環境、ビルド、テスト

### 2. コードスニペットと Sources 行のルール
- スニペットは疑似コード禁止。実際のコードから抜粋する。
- スニペット冒頭に必ず出典コメント (`// パス:L開始-L終了`) を記載する。
- **Sources行**は各セクションの末尾に必ず配置し、**実際に参照した範囲（200行以内）の行番号を明記**する。（例: `[file.ts:L50-L100]`）。全行を指定する（例: `L1-L1000`）や、ページ末尾にまとめて1箇所に記載するのは減点対象。

### 3. 個別ページの模範構成テンプレート

```markdown
# [ページタイトル]

[概要: 2-3文でこのページのスコープを説明。何を解説し、何は別ページかを明記。]

**Sources:** [ソースファイル1:L範囲](file:///パス#L開始-L終了), ...

## [セクション1: アーキテクチャ/概要]

[コンポーネントの役割と全体像を説明。実際のクラス名/関数名を使う。]

### [設計パターン名] パターン

[設定項目やカテゴリ分類を具体的に説明ならびに必要に応じてテーブルを使用]

```mermaid
flowchart TD
    A["ToolRegistry"] -->|"lookup()"| B["DeclarativeTool"]
```

```typescript
// packages/core/src/tools/tools.ts:L45-L62
export interface DeclarativeTool { ... }
```
**Sources:** [tools.ts:L45-L62](file:///path/to/tools.ts#L45-L62)

## 関連ページ
- [← 前: ページタイトル](./previous.md)
- [→ 次: ページタイトル](./next.md)
```
"""

PROMPT_MERMAID_RULES = """
## Mermaidダイアグラム作成ルール（必須・絶対厳守）

MarkdownパーサーおよびMermaidレンダリングエンジンでの**パースエラー・描画不能を絶対に防ぐため、以下のルールを完全に遵守すること。**

### 1. 縦方向 (Vertical) レイアウトの強制
- フローダイアグラムの指定には必ず `graph TD` または `flowchart TD` を使用すること。（LRは禁止）
- ノード内のテキストは最大でも3-4単語に収め、横幅が長くなりすぎないようにすること。

### 2. シーケンス図 (Sequence Diagrams) の厳格なルール
- 先頭行に必ず単独で `sequenceDiagram` を配置し、直後に participant を定義すること。
- 以下の矢印を意図に合わせて使用: `->>` (リクエスト), `-->>` (レスポンス), `-)` (非同期).
- アクティベーションボックスには必ず `+`/`-` プレフィックスを使用すること（例: `A->>+B: Start`, `B-->>-A: End`）。
- メッセージへのラベル付与にはコロン（`:`）を用いること。**絶対にフローチャート風の `A--|label|-->B` 表記を使用しないこと。**

### 3. 【🔥 致命的エラー防止: 全般的な構文ルール】
> [!CAUTION]
> **以下のルールに違反すると、図がすべて表示されなくなる致命的なエラーを引き起こす。**

- ノードラベルに `()`、`[]`、`{}` などの括弧や記号類が含まれる場合は、**例外なく必ず `["ラベル"]` のようにダブルクォーテーションで囲む**こと。
  - **【頻出エラー1】** `D[Data Pipeline (api/data_pipeline.py)]` のように `[]` の内側に `()` を含むとパースエラーで図が崩壊します。**必ず `D["Data Pipeline (api/data_pipeline.py)"]` とクォートで囲むこと。**
  - **【頻出エラー2】** `cmd_start_sh(CMD ["/app/start.sh"])` のように `()` の内側に `[]` 等が含まれる場合もパースエラーになります。**必ず `cmd_start_sh("CMD /app/start.sh")` のようにクォートするか、記号を削除してください。**
- HTMLタグは使用不可（`<` や `>` などの記号もパースエラーの原因）。
- ノード ID にハイフンを含めない（アンダースコアを使用すること）。
- 実際のソースコードに存在する**クラス名・関数名**をノードラベルに用いること。
"""

PROMPT_QUALITY_STANDARDS = """
## importance 別の最低要件（品質基準マトリクス）

以下の基準に厳密に従ってください。親から importance の指定がない場合は `medium` とします。

| importance | 語数 | ダイアグラム | Mermaid種類 | コードスニペット | Sources 行 | テーブル |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| high | **1200語以上** | 2-3個 | **2種類以上** | **5-8個必須** | 全セクション | **1個以上** |
| medium | **600-1000語** | 1-2個 | 1種類以上 | **3-5個必須** | 全セクション | 推奨 |
| low | 300-500語 | 1個 | 1種類以上 | 1-2個 | 主要セクション | 任意 |
"""

def build_prompt(title: str, description: str, file_paths: List[str], importance: str, feedback: Optional[str] = None) -> str:
    """
    Constructs the prompt logic previously handled by the subagent.
    """
    paths_str = "\n".join([f"- {path}" for path in file_paths])
    
    prompt = f"{PROMPT_SYSTEM_INSTRUCTION}\n"
    prompt += f"## ページ情報 (Target Page Information)\n"
    prompt += f"- **タイトル**: {title}\n"
    prompt += f"- **説明**: {description}\n"
    prompt += f"- **重要度**: {importance}\n\n"
    
    prompt += f"## 参照ファイル (Source Files)\n"
    prompt += f"以下のファイルを必ず参照して、事実に基づいた正確なドキュメントを作成してください。\n{paths_str}\n\n"
    
    prompt += PROMPT_FORMAT_INSTRUCTIONS
    prompt += PROMPT_MERMAID_RULES
    prompt += PROMPT_QUALITY_STANDARDS
    
    if feedback:
        prompt += f"""
## 修正ループ時の動作指示 (Correction Instructions for Retry)
フィードバック（不足やエラーの指摘）を受け付けた場合、既存の生成済みMarkdownファイルを読み込んで問題箇所を確認し、修正を反映・上書きしてください。同じ過ちを繰り返さないことが重要です。

### フィードバック（エラー内容）:
{feedback}
"""

    prompt += "\n### 生成時の注意事項\n"
    prompt += "解説などの前置きは発言せず、コンテキストを最小限に絞った状態で独立したWikiページを完成させ、そのままマークダウンファイルとして保存できるコンテンツのみを出力してください。\n"
    
    return prompt

async def run_gemini_cli(prompt: str, working_dir: str, target_dir: str) -> bool:
    """
    Executes the gemini CLI command to generate the page.
    Returns True if the command executes without throwing an exception.
    """
    # プロンプトは stdin で渡す（-p/--prompt は deprecated のため使用しない）
    # stdin に入力がある場合 gemini は自動的に non-interactive モードで動作する
    cmd = [
        "gemini",
        "-m", "gemini-2.5-flash",
        "--approval-mode", "yolo",
        "--sandbox",
        "--include-directories", f"{working_dir},{target_dir}",
    ]

    print("=" * 60)
    print(f"Executing Gemini CLI in {target_dir}:\n{' '.join(cmd)}")
    print("=" * 60)

    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=target_dir,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        try:
            # 標準入力にプロンプトを流し込んで実行
            stdout, stderr = await asyncio.wait_for(
                process.communicate(input=prompt.encode('utf-8')),
                timeout=GEMINI_TIMEOUT_SECONDS
            )
        except asyncio.TimeoutError:
            process.kill()
            await process.communicate()
            print(f"[Timeout] Gemini CLI execution timed out after {GEMINI_TIMEOUT_SECONDS} seconds.")
            return False
            
        if process.returncode != 0:
            print(f"[Error] Gemini CLI failed with exit code {process.returncode}")
            print(f"Stderr: {stderr.decode('utf-8', errors='ignore')}")
            return False
            
        return True
    except Exception as e:
        print(f"[Exception] Failed to run Gemini CLI: {e}")
        return False

async def validate_page(page_file_path: str, importance: str, working_dir: str) -> Tuple[bool, str]:
    """
    Runs validate_page.py on the generated markdown file.
    Returns (is_passed, feedback_output)
    """
    if not os.path.exists(page_file_path):
        return False, f"File not found: {page_file_path}. The agent failed to create the file."
        
    script_dir = os.path.dirname(os.path.abspath(__file__))
    validate_script = os.path.join(script_dir, "validate_page.py")

    cmd = [
        "python3",
        validate_script,
        page_file_path,
        "--importance", importance
    ]

    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=working_dir,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        
        output = stdout.decode('utf-8')
        
        # validate_page.py: Grade B以上で exit(0)、C以下で exit(1)
        if process.returncode == 0:
            return True, output
        return False, output + "\n" + stderr.decode('utf-8', errors='ignore')
            
    except Exception as e:
        return False, f"Exception during validation: {e}"

async def process_page(page: Dict[str, Any], output_dir: str, working_dir: str, target_dir: str) -> bool:
    """
    Processes a single page: builds prompt, runs gemini, validates, and loops if necessary.
    """
    page_id = page.get("id")
    title = page.get("title")
    description = page.get("description")
    file_paths = page.get("filePaths", [])
    
    # プロンプト用のファイルパスを絶対パスに変換
    abs_file_paths = []
    for path in file_paths:
        if not os.path.isabs(path):
            abs_file_paths.append(os.path.abspath(os.path.join(target_dir, path)))
        else:
            abs_file_paths.append(path)
            
    importance = page.get("importance", "medium")
    
    file_name = page.get("filename") or (f"{page_id}.md" if page_id else title.replace(" ", "_").lower() + ".md")
    target_file_path = os.path.join(output_dir, file_name)
    
    print(f"[{page_id}] Starting generation of roughly {importance} importance page...")
    
    feedback = None
    success = False
    
    for attempt in range(MAX_RETRIES + 1):
        if attempt > 0:
            print(f"[{page_id}] Retry attempt {attempt}/{MAX_RETRIES} due to validation failure...")
            
        # 1. Build prompt
        full_title = f"{title} (Target Path: {target_file_path})"
        prompt = build_prompt(full_title, description, abs_file_paths, importance, feedback)
        
        # 2. Run Gemini
        print(f"[{page_id}] Running Gemini CLI...")
        cli_success = await run_gemini_cli(prompt, working_dir, target_dir)
        
        if not cli_success:
            feedback = "Gemini CLI execution failed or timed out. Please try to write the file again by strictly following instructions."
            continue
            
        # 3. Validate Output
        print(f"[{page_id}] Validating output...")
        is_valid, validation_output = await validate_page(target_file_path, importance, working_dir)
        
        if is_valid:
            print(f"[{page_id}] ✅ Successfully generated and passed validation!")
            success = True
            break
        else:
            print(f"[{page_id}] ❌ Validation failed. Gathering feedback for retry...")
            feedback = validation_output
            
    if not success:
        print(f"[{page_id}] 🛑 Failed to generate a valid page after {MAX_RETRIES} retries.")
        
    return success

async def main():
    parser = argparse.ArgumentParser(description="DeepWiki Page Generator Orchestrator")
    parser.add_argument("outline_json", help="Path to the outline.json file")
    args = parser.parse_args()
    
    outline_path = os.path.abspath(args.outline_json)
    if not os.path.exists(outline_path):
        print(f"Error: outline.json not found at {outline_path}")
        sys.exit(1)
        
    output_dir = os.path.dirname(outline_path)
    # The script should be run from the root of the target project, which should be the CWD
    working_dir = os.getcwd() 
    
    with open(outline_path, "r", encoding="utf-8") as f:
        outline_data = json.load(f)
        
    target_dir = outline_data.get("targetDir")
    if target_dir:
        # 相対パスの場合は outline.json のあるディレクトリを基準に解決
        if not os.path.isabs(target_dir):
            target_dir = os.path.abspath(os.path.join(output_dir, target_dir))
    else:
        target_dir = working_dir
        
    pages = outline_data.get("pages", [])
    pending_pages = [p for p in pages if p.get("status") in ("pending", "error")]
    
    if not pending_pages:
        print("No pending pages found in outline.json.")
        return
        
    print(f"Found {len(pending_pages)} pages to generate. Starting parallel processing (max {MAX_CONCURRENT_PAGES})...")
    
    # Process pages concurrently with a semaphore
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_PAGES)
    
    async def process_with_semaphore(page, idx):
        async with semaphore:
            success = await process_page(page, output_dir, working_dir, target_dir)
            # Update status in memory
            page["status"] = "done" if success else "error"
            
            # Save progress synchronously to avoid race conditions on the JSON file
            try:
                with open(outline_path, "w", encoding="utf-8") as f:
                    json.dump(outline_data, f, indent=2, ensure_ascii=False)
            except Exception as e:
                print(f"Failed to update outline.json: {e}")
                
    tasks = [process_with_semaphore(page, i) for i, page in enumerate(pending_pages)]
    await asyncio.gather(*tasks)
    
    print("All page generation tasks completed.")

if __name__ == "__main__":
    asyncio.run(main())
