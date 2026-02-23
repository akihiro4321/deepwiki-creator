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
GEMINI_TIMEOUT_SECONDS = 600 # 10 minutes

# --- Prompt Constants ---
PROMPT_SYSTEM_INSTRUCTION = """You are the deepwiki_page_generator, an expert technical documentation writer.
Your task is to write a single, highly detailed Wiki page based strictly on the provided context.
"""

PROMPT_FORMAT_INSTRUCTIONS = """
## 出力フォーマット仕様 (Output Format & Guidelines)

【執筆の最重要指示】
下記セクション「3. 個別ページの模範構成テンプレート」に**最も厳格に**従ってMarkdownを出力してください。指定外の推測に基づいた情報は記述しないでください。

### 1. セクション構成の基本方針
- [Overview] プロジェクト概要、アーキテクチャ、モジュール構成
- [Getting Started] インストール、認証、設定
- [User Guide] ユーザー向け機能（コマンド、UI、操作方法等）
- [Core Systems] 内部アーキテクチャの主要モジュール
- [Advanced Topics] 拡張性、セキュリティ、可観測性、プラグイン等
- [Development] 開発環境、ビルド、テスト

### 2. コードスニペットと Sources 行のルール
- スニペットは疑似コード禁止。実際のコードから抜粋する。
- スニペット冒頭に必ず出典コメントを記載する。言語に合わせてコメント記号を使い分けること。
  - TypeScript/JavaScript/Go/Rust/Java/C++: `// パス:L開始-L終了`
  - Python/Ruby/Shell/YAML: `# パス:L開始-L終了`
- **スニペット内の省略禁止**: スニペット中に `...` や `// ...` や `// (省略)` などの省略表現を含めること。実際のコードをそのまま抜粋すること。行数が長すぎる場合は、重要な行のみを含む範囲に絞る。
- **Sources行**は各セクションの末尾に必ず配置し、**実際に参照した範囲（200行以内）の行番号を明記**する。（例: `[file.ts:L50-L100]`）。全行を指定する（例: `L1-L1000`）や、ページ末尾にまとめて1箇所に記載するのは減点対象。
- **【行番号の取得手順】** `read_file` でファイルを読んだ直後に、参照した関数・クラスの開始行〜終了行をメモしておくこと。書き終えてから行番号を推測で補うことは禁止。

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
- **コロン（`:`）の後には必ずラベルを記載すること。** `DB-->>-Service:` のようにコロン後が空のままにするとパースエラーになる。戻り値がない場合は `void`、成功応答は `OK` や `完了` などを使用すること。

### 3. 【🔥 致命的エラー防止: フローチャート構文ルール】
> [!CAUTION]
> **以下のルールに違反すると、図がすべて表示されなくなる致命的なエラーを引き起こす。**

#### 3-A. 使用するノードシェイプの制限（3種類のみ）
フローチャートで使用できるシェイプは以下の **3種類のみ** とし、それ以外の複雑なシェイプ（`[[]]`・`[()]`・`{{}}` 等）は**使用禁止**。

| シェイプ | 記法 | 用途 |
| :--- | :--- | :--- |
| 長方形 | `A[ラベル]` | 一般コンポーネント・モジュール |
| 角丸長方形 | `A(ラベル)` | プロセス・アクション |
| ひし形 | `A{ラベル}` | 条件分岐・判断 |

#### 3-B. 特殊文字を含むラベルは必ずダブルクォートで囲む

**以下の文字がラベルに1文字でも含まれる場合、例外なく `["ラベル"]` 形式でクォートすること:**

| 文字 | 理由 |
| :--- | :--- |
| `(` `)` | 角丸長方形シェイプ記号と混同 |
| `[` `]` | 長方形シェイプ記号と混同 |
| `{` `}` | ひし形シェイプ記号と混同 |
| `\|` | エッジラベル記法（`-->|label|`）と混同 |
| `/` `\` | 平行四辺形シェイプ（`[/text/]`）と混同 |
| `<` `>` | HTMLタグ・シェイプと混同 |
| `#` | コメント記号（`%%`）と混同 |
| `:` | シーケンス図のメッセージ区切りと混同 |
| `%` | コメント記号（`%%`）と混同 |

- `"` 自体をラベルに含めたい場合は `&quot;` でエスケープすること。
- **【頻出エラー例1】** `D[Data Pipeline (api/data_pipeline.py)]` → **必ず** `D["Data Pipeline (api/data_pipeline.py)"]`
- **【頻出エラー例2】** `cmd["CMD ['/app/start.sh']"]` のように括弧が入れ子になる場合は角括弧を削除して `cmd["CMD '/app/start.sh'"]` と書くこと。
- **【頻出エラー例3】** `A{is valid?}` → **必ず** `A{"is valid?"}`（ひし形ラベルに `?` が含まれる場合もクォート推奨）

#### 3-C. ノード ID のルール
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

### コードスニペット内訳の目安（達成方法）

スニペット数が不足しやすいため、以下の内訳を参考に構成すること。

**importance: high（5-8個）の場合:**
1. 主要クラス・インターフェースの定義（型・フィールド確認用） × 1-2
2. コアロジックの重要メソッド（処理の核心部分） × 2-3
3. データフロー・呼び出し連鎖（エントリーポイント〜主要処理） × 1
4. 設定・定数・Enum 等の一覧 × 1
5. エラーハンドリング・特殊ケースの実装 × 1（あれば）

**importance: medium（3-5個）の場合:**
1. 主要クラス・インターフェース定義 × 1
2. コアメソッド（1-2個） × 1-2
3. 利用例・呼び出し方 × 1

**importance: low（1-2個）の場合:**
1. 代表的な定義か利用例 × 1-2
"""

def build_prompt(title: str, description: str, file_paths: List[str], importance: str, feedback: Optional[str] = None, all_pages: Optional[List[Dict[str, Any]]] = None) -> str:
    """
    Constructs the prompt logic previously handled by the subagent.
    all_pages: outline.json の全ページリスト。関連ページリンクの候補として使用。
    """
    paths_str = "\n".join([f"- {path}" for path in file_paths])
    
    prompt = f"{PROMPT_SYSTEM_INSTRUCTION}\n"
    prompt += f"## ページ情報 (Target Page Information)\n"
    prompt += f"- **タイトル**: {title}\n"
    prompt += f"- **説明**: {description}\n"
    prompt += f"- **重要度**: {importance}\n\n"
    
    prompt += f"## 参照ファイル (Source Files)\n"
    prompt += (
        f"以下のファイルを必ず参照してください。\n"
        f"**【重要】まず全ファイルを `read_file` ツールで実際に開き、主要なクラス定義・関数定義・インターフェースを確認してから書き始めること。**\n"
        f"ファイルを読まずにプロンプトの情報だけで書き始めることは禁止します。\n"
        f"各ファイルを読んだ直後に、参照した行番号範囲（例: L45-L120）をメモしておき、Sources行やコードスニペットの出典に正確に反映してください。\n"
        f"{paths_str}\n\n"
    )
    
    prompt += PROMPT_FORMAT_INSTRUCTIONS
    prompt += PROMPT_MERMAID_RULES
    prompt += PROMPT_QUALITY_STANDARDS
    
    if feedback:
        prompt += f"""
## 修正ループ時の動作指示 (Correction Instructions for Retry)
前回の生成結果に品質上の問題がありました。以下の手順で修正してください。

**【必須手順】**
1. まず `read_file` で既存の生成済みファイルを開き、現在の内容を確認する
2. 下記フィードバックで指摘された不足要素のみを追加・修正する
3. 内容全体を書き直すのではなく、不足している要素の追加に集中する
4. 修正後、ファイルを上書き保存する

同じ問題を繰り返さないことが最重要です。

### フィードバック（修正すべき問題点）:
{feedback}
"""

    if all_pages:
        others = [p for p in all_pages if p.get("title") != title]
        pages_list = "\n".join(
            [f"- [{p['title']}](./{p['filename']})" for p in others if p.get("filename")]
        )
        prompt += f"""
## 関連ページリンクのルール（厳守）
「## 関連ページ」セクションには、**以下のリストに含まれるページのみ**を記載してください。
このリストに存在しないページへのリンクや、`(仮)` と書かれたリンクは**絶対に含めないこと**。

利用可能なページ一覧:
{pages_list}
"""

    prompt += "\n### 生成時の注意事項\n"
    prompt += "解説などの前置きは発言せず、コンテキストを最小限に絞った状態で独立したWikiページを完成させ、そのままマークダウンファイルとして保存できるコンテンツのみを出力してください。\n"

    return prompt

def extract_critical_feedback(validation_output: str, max_issues: int = 3) -> str:
    """
    バリデーション出力から重要なフィードバックのみを抽出して返す。
    安価なモデルに渡す際、長い出力全体ではなく❌ / ⚠️ の指摘に絞ることで
    リトライ時の修正精度を高める。
    """
    critical = [l.strip() for l in validation_output.splitlines() if "❌" in l]
    warnings = [l.strip() for l in validation_output.splitlines() if "⚠️" in l]

    selected = critical[:max_issues]
    if len(selected) < max_issues:
        selected += warnings[: max_issues - len(selected)]

    if not selected:
        # フォールバック: 先頭数行をそのまま使う
        selected = [l.strip() for l in validation_output.splitlines() if l.strip()][:5]

    return "\n".join(selected)


def build_save_prompt(title: str, target_file_path: str) -> str:
    """
    Builds the final instruction to save the generated content to a file.
    Separated from the main prompt to ensure Gemini focuses on writing first, then saving.
    """
    return f"""
上記の指示に従い、「{title}」のWikiページのMarkdownコンテンツを生成し、
**必ず以下のファイルパスに保存してください。**

保存先ファイルパス: `{target_file_path}`

ファイルへの書き込み（write_file ツール使用）が完了したら、その旨を報告してください。
"""

async def run_gemini_cli(prompt: str, working_dir: str, target_dir: str, output_dir: str, additional_dirs: List[str] = []) -> bool:
    """
    Executes the gemini CLI command to generate the page.
    Returns True if the command executes without throwing an exception.
    """
    # プロンプトは stdin で渡す（-p/--prompt は deprecated のため使用しない）
    # stdin に入力がある場合 gemini は自動的に non-interactive モードで動作する
    # --sandbox はmacOS Seatbeltによりファイル書き込みを制限するため使用しない
    # output_dir を --include-directories に含めないと Gemini がファイルを書き込めない
    include_dirs = ",".join(set([working_dir, target_dir, output_dir] + additional_dirs))
    cmd = [
        "gemini",
        "-m", "gemini-2.5-flash",
        "--approval-mode", "auto_edit",
        "--include-directories", include_dirs,
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
        sys.executable,  # generate_pages.py を呼んだPythonと同じ実行ファイル（.venv/bin/python）を使う
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

async def process_page(page: Dict[str, Any], output_dir: str, working_dir: str, target_dir: str, all_pages: Optional[List[Dict[str, Any]]] = None, additional_dirs: List[str] = []) -> Tuple[bool, Optional[str]]:
    """
    Processes a single page: builds prompt, runs gemini, validates, and loops if necessary.
    Returns (success, error_message). error_message is None on success.
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
        prompt = build_prompt(title, description, abs_file_paths, importance, feedback, all_pages)
        prompt += build_save_prompt(title, target_file_path)
        
        # 2. Run Gemini
        print(f"[{page_id}] Running Gemini CLI...")
        cli_success = await run_gemini_cli(prompt, working_dir, target_dir, output_dir, additional_dirs)
        
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
            feedback = extract_critical_feedback(validation_output)

    if not success:
        print(f"[{page_id}] 🛑 Failed to generate a valid page after {MAX_RETRIES} retries.")
        return False, feedback

    return True, None

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

    # 周辺サービス等の追加ディレクトリ（Gemini CLIのアクセス許可対象）
    raw_additional = outline_data.get("additionalDirs", [])
    additional_dirs = []
    for d in raw_additional:
        if not os.path.isabs(d):
            d = os.path.abspath(os.path.join(output_dir, d))
        additional_dirs.append(d)

    pages = outline_data.get("pages", [])
    pending_pages = [p for p in pages if p.get("status") in ("pending", "error")]

    if not pending_pages:
        print("No pending pages found in outline.json.")
        return

    print(f"Found {len(pending_pages)} pages to generate. Starting parallel processing (max {MAX_CONCURRENT_PAGES})...")

    # Process pages concurrently with a semaphore
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_PAGES)

    all_pages = outline_data.get("pages", [])

    async def process_with_semaphore(page, idx):
        async with semaphore:
            success, error_msg = await process_page(page, output_dir, working_dir, target_dir, all_pages, additional_dirs)
            # Update status in memory
            if success:
                page["status"] = "done"
                page.pop("error", None)  # 再実行で成功した場合はエラー情報をクリア
            else:
                page["status"] = "error"
                page["error"] = error_msg or "Unknown error"
            
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
