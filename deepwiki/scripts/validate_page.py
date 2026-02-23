#!/usr/bin/env python3
"""
DeepWiki ページ品質バリデーター

生成された Wiki ページが品質基準を満たしているかを検証する。
各ページに対してスコアと改善指摘を出力する。
ディレクトリ指定時は Wiki 全体の構造（ページ数・セクション網羅性・配分）も検証する。

品質基準は、開発者がキャッチアップや既存機能の拡張検討に
十分な網羅性・深度・ソース参照密度を備えているかを基準とする。

使用方法:
  python validate_page.py <ページファイル.md> [--importance high|medium|low]
  python validate_page.py <wikiディレクトリ> [--scale small|medium|large]
"""

import sys
import re
import os
import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ValidationResult:
    """1ページのバリデーション結果"""
    file: str
    importance: str  # high / medium / low / unknown
    score: int = 0  # 0-100
    max_score: int = 0
    issues: list = field(default_factory=list)
    passes: list = field(default_factory=list)

    @property
    def grade(self) -> str:
        pct = (self.score / self.max_score * 100) if self.max_score > 0 else 0
        if pct >= 90:
            return "A"
        elif pct >= 75:
            return "B"
        elif pct >= 60:
            return "C"
        elif pct >= 40:
            return "D"
        else:
            return "F"

    @property
    def percentage(self) -> float:
        return (self.score / self.max_score * 100) if self.max_score > 0 else 0


# --- 品質基準定義（Claude Opus 版を標準） ---
REQUIREMENTS = {
    "high": {
        "min_words": 1200,
        "min_mermaid": 2,
        "min_mermaid_types": 2,
        "min_code_snippets": 5,
        "min_sources_lines": 4,
        "sources_need_line_numbers": True,
        "min_sections": 4,
        "min_tables": 1,
    },
    "medium": {
        "min_words": 600,
        "min_mermaid": 1,
        "min_mermaid_types": 1,
        "min_code_snippets": 3,
        "min_sources_lines": 3,
        "sources_need_line_numbers": True,
        "min_sections": 3,
        "min_tables": 0,
    },
    "low": {
        "min_words": 300,
        "min_mermaid": 1,
        "min_mermaid_types": 1,
        "min_code_snippets": 1,
        "min_sources_lines": 2,
        "sources_need_line_numbers": True,
        "min_sections": 2,
        "min_tables": 0,
    },
    "index": {
        "min_words": 200,
        "min_mermaid": 1,
        "min_mermaid_types": 1,
        "min_code_snippets": 0,
        "min_sources_lines": 0,
        "sources_need_line_numbers": False,
        "min_sections": 2,
        "min_tables": 0,
    },
}

# Sources 行番号の精度しきい値（この行数以上の範囲は「不正確」）
MAX_ACCEPTABLE_LINE_RANGE = 200


def count_words(text: str) -> int:
    """日本語+英語の混合テキストの語数を推定。
    日本語: 文字数 ≒ 語数（助詞等含む）
    英語: スペース区切り
    """
    # コードブロックと Mermaid を除外
    cleaned = re.sub(r'```[\s\S]*?```', '', text)
    # Markdown の見出しや記号を除外
    cleaned = re.sub(r'[#|>\-*`\[\]()]', ' ', cleaned)

    # 日本語文字をカウント
    jp_chars = len(re.findall(r'[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]', cleaned))
    # 英語単語をカウント
    en_words = len(re.findall(r'[a-zA-Z]+', cleaned))

    return jp_chars + en_words


def count_mermaid_diagrams(text: str) -> int:
    return len(re.findall(r'```mermaid', text))


def get_mermaid_types(text: str) -> set:
    """使用されている Mermaid ダイアグラムの種類を返す"""
    types = set()
    mermaid_blocks = re.findall(r'```mermaid\n([\s\S]*?)```', text)
    for block in mermaid_blocks:
        first_line = block.strip().split('\n')[0].strip().lower()
        if first_line.startswith('graph'):
            types.add('graph')
        elif first_line.startswith('flowchart'):
            types.add('flowchart')
        elif first_line.startswith('sequencediagram'):
            types.add('sequenceDiagram')
        elif first_line.startswith('classdiagram'):
            types.add('classDiagram')
        elif first_line.startswith('statediagram'):
            types.add('stateDiagram')
        elif first_line.startswith('erdiagram'):
            types.add('erDiagram')
        elif first_line.startswith('gantt'):
            types.add('gantt')
        elif first_line.startswith('pie'):
            types.add('pie')
        else:
            types.add('other')
    return types


def count_code_snippets(text: str) -> int:
    """Mermaid 以外のコードブロックをカウント"""
    all_blocks = re.findall(r'```(\w*)', text)
    return sum(1 for lang in all_blocks if lang and lang != 'mermaid')


def count_snippet_citations(text: str) -> int:
    """コードスニペット内の出典コメント (// path:L行番号 または # path:L行番号) をカウント。
    // は TS/JS/Go/Rust/Java など、# は Python/Ruby/Shell/YAML など。
    """
    code_blocks = re.findall(r'```\w+\n([\s\S]*?)```', text)
    citations = 0
    for block in code_blocks:
        # (?://|#) で // または # のどちらのコメント形式も受け入れる
        if re.search(
            r'(?://|#)\s*\S+\.(ts|js|py|go|rs|java|tsx|jsx|vue|sh|rb|kt|swift|cs|cpp|c|h|php|scala|ex|exs|dart|lua|r)\s*[:\s]L\d+',
            block,
        ):
            citations += 1
    return citations


def count_tables(text: str) -> int:
    """Markdown テーブルの数をカウント（ヘッダ行 + 区切り行のペアで判定）"""
    # テーブルは | header | header | のような行の後に | --- | --- | が続く
    lines = text.split('\n')
    table_count = 0
    for i in range(len(lines) - 1):
        if re.match(r'\s*\|.*\|.*\|', lines[i]) and \
           re.match(r'\s*\|[\s\-:]+\|[\s\-:]+\|', lines[i + 1]):
            table_count += 1
    return table_count


def find_sources_lines(text: str) -> list:
    """Sources: 行を全て抽出"""
    return re.findall(r'^.*Sources?:.*$', text, re.MULTILINE)


def check_line_numbers_in_sources(sources_lines: list) -> tuple:
    """Sources 行に行番号 (L数字) が含まれているか。精度もチェック。"""
    with_line_nums = 0
    with_imprecise_line_nums = 0
    without_line_nums = 0

    for line in sources_lines:
        ranges = re.findall(r'L(\d+)[-–]L?(\d+)', line)
        if ranges:
            precise = True
            for start, end in ranges:
                span = int(end) - int(start)
                if span > MAX_ACCEPTABLE_LINE_RANGE:
                    precise = False
                    break
            if precise:
                with_line_nums += 1
            else:
                with_imprecise_line_nums += 1
        elif re.search(r'L\d+', line):
            with_line_nums += 1
        else:
            without_line_nums += 1

    return with_line_nums, with_imprecise_line_nums, without_line_nums


def count_sections(text: str) -> int:
    """## レベルの見出し数をカウント"""
    return len(re.findall(r'^## ', text, re.MULTILINE))


def check_mermaid_has_real_names(text: str) -> tuple:
    """Mermaid ダイアグラム内に具体的なクラス名が使われているか"""
    mermaid_blocks = re.findall(r'```mermaid\n([\s\S]*?)```', text)
    generic_names = {'Component', 'Module', 'Service', 'System', 'Client', 'Server',
                     'Manager', 'Handler', 'Engine', 'Registry', 'Controller'}
    has_specific = 0
    has_generic = 0
    for block in mermaid_blocks:
        labels = re.findall(r'\[([^\]]+)\]', block)
        for label in labels:
            clean = label.strip('"').strip()
            # 2語以上 or PascalCase なら具体的
            if re.match(r'[A-Z][a-z]+[A-Z]', clean) or len(clean.split()) >= 2:
                has_specific += 1
            elif clean in generic_names:
                has_generic += 1
    return has_specific, has_generic


def check_related_pages(text: str) -> bool:
    """関連ページリンクがあるか"""
    return bool(re.search(r'(関連ページ|Related|← 前|→ 次|参照)', text, re.IGNORECASE))


def check_overview_paragraph(text: str) -> bool:
    """冒頭に概要段落があるか（最初の ## の前にテキストがあるか）"""
    lines = text.split('\n')
    found_h1 = False
    has_overview = False
    for line in lines:
        if line.startswith('# ') and not line.startswith('## '):
            found_h1 = True
            continue
        if found_h1 and line.startswith('## '):
            break
        if found_h1 and line.strip() and not line.startswith('#') and not line.startswith('```') and not line.startswith('>'):
            has_overview = True
    return has_overview


def detect_importance(filepath: str) -> str:
    """ファイルパスからimportanceを推測（セクション番号ベース）"""
    basename = os.path.basename(filepath)
    if basename == 'index.md':
        return 'index'

    # x.y 形式の番号を抽出
    match = re.match(r'(\d+)\.(\d+)', basename)
    if match:
        section = int(match.group(1))
        # Overview (1.x), Core Systems (4.x) は high
        if section in (1, 4):
            return 'high'
        # その他は medium
        else:
            return 'medium'

    return 'medium'  # デフォルト


def validate_page(filepath: str, importance: Optional[str] = None) -> ValidationResult:
    """1ページを検証"""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    if importance is None:
        importance = detect_importance(filepath)

    reqs = REQUIREMENTS.get(importance, REQUIREMENTS['medium'])
    result = ValidationResult(file=filepath, importance=importance)

    # --- 1. 語数チェック (15点) ---
    result.max_score += 15
    word_count = count_words(content)
    min_words = reqs['min_words']
    if word_count >= min_words:
        result.score += 15
        result.passes.append(f"✅ 語数: {word_count} (基準: {min_words}以上)")
    elif word_count >= min_words * 0.7:
        result.score += 8
        result.issues.append(f"⚠️  語数不足: {word_count} (基準: {min_words}以上, 70%以上なので部分点)")
    else:
        result.issues.append(f"❌ 語数不足: {word_count} (基準: {min_words}以上)")

    # --- 2. Mermaid ダイアグラム数 (10点) ---
    result.max_score += 10
    mermaid_count = count_mermaid_diagrams(content)
    min_mermaid = reqs['min_mermaid']
    if mermaid_count >= min_mermaid:
        result.score += 10
        result.passes.append(f"✅ Mermaid: {mermaid_count}個 (基準: {min_mermaid}以上)")
    elif mermaid_count > 0:
        result.score += 5
        result.issues.append(f"⚠️  Mermaid不足: {mermaid_count}個 (基準: {min_mermaid}以上)")
    else:
        result.issues.append(f"❌ Mermaidなし (基準: {min_mermaid}以上)")

    # --- 3. Mermaid 種類の多様性 (5点) ---
    result.max_score += 5
    mermaid_types = get_mermaid_types(content)
    min_types = reqs['min_mermaid_types']
    if len(mermaid_types) >= min_types:
        result.score += 5
        result.passes.append(f"✅ Mermaid種類: {', '.join(sorted(mermaid_types))} ({len(mermaid_types)}種類, 基準: {min_types}以上)")
    elif len(mermaid_types) > 0:
        result.score += 2
        result.issues.append(f"⚠️  Mermaid種類不足: {', '.join(sorted(mermaid_types))} ({len(mermaid_types)}種類, 基準: {min_types}以上)")
    else:
        result.issues.append(f"❌ Mermaidなし")

    # --- 4. コードスニペット数 (15点) ---
    result.max_score += 15
    snippet_count = count_code_snippets(content)
    min_snippets = reqs['min_code_snippets']
    if snippet_count >= min_snippets:
        result.score += 15
        result.passes.append(f"✅ コードスニペット: {snippet_count}個 (基準: {min_snippets}以上)")
    elif snippet_count > 0 and min_snippets > 0:
        # 割合に応じた部分点
        partial = min(10, int(15 * snippet_count / min_snippets))
        result.score += partial
        result.issues.append(f"⚠️  コードスニペット不足: {snippet_count}個 (基準: {min_snippets}以上)")
    elif min_snippets > 0:
        result.issues.append(f"❌ コードスニペットなし (基準: {min_snippets}以上)")
    else:
        result.score += 15
        result.passes.append(f"✅ コードスニペット: 不要 (importance: low)")

    # --- 5. スニペット出典コメント (5点) ---
    result.max_score += 5
    if snippet_count > 0:
        citation_count = count_snippet_citations(content)
        if citation_count >= snippet_count * 0.6:
            result.score += 5
            result.passes.append(f"✅ スニペット出典: {citation_count}/{snippet_count}個に出典コメントあり")
        elif citation_count > 0:
            result.score += 2
            result.issues.append(f"⚠️  スニペット出典不足: {citation_count}/{snippet_count}個のみ出典あり (60%以上が基準)")
        else:
            result.issues.append(f"❌ スニペット出典なし (// path/to/file.ts:L行番号 形式のコメントが必要)")
    else:
        result.score += 0  # スニペットがなければ出典もチェックしない

    # --- 6. Sources 行存在 (10点) ---
    result.max_score += 10
    sources_lines = find_sources_lines(content)
    min_sources = reqs['min_sources_lines']
    if len(sources_lines) >= min_sources:
        result.score += 10
        result.passes.append(f"✅ Sources行: {len(sources_lines)}行 (基準: {min_sources}以上)")
    elif len(sources_lines) > 0:
        result.score += 5
        result.issues.append(f"⚠️  Sources行不足: {len(sources_lines)}行 (基準: {min_sources}以上)")
    else:
        result.issues.append(f"❌ Sources行なし (基準: {min_sources}以上)")

    # --- 7. Sources 行番号精度 (10点) ---
    result.max_score += 10
    if sources_lines and reqs['sources_need_line_numbers']:
        precise, imprecise, no_ln = check_line_numbers_in_sources(sources_lines)
        total_with_any = precise + imprecise
        if precise > 0 and imprecise == 0 and no_ln == 0:
            result.score += 10
            result.passes.append(f"✅ Sources行番号: 全{precise}行に正確な行番号あり")
        elif precise > 0:
            result.score += 7
            msg_parts = []
            if imprecise > 0:
                msg_parts.append(f"不正確{imprecise}行(範囲>{MAX_ACCEPTABLE_LINE_RANGE}行)")
            if no_ln > 0:
                msg_parts.append(f"行番号なし{no_ln}行")
            result.issues.append(f"⚠️  Sources行番号: 正確{precise}行, {', '.join(msg_parts)}")
        elif imprecise > 0:
            result.score += 3
            result.issues.append(f"⚠️  Sources行番号が不正確: {imprecise}行が{MAX_ACCEPTABLE_LINE_RANGE}行超の広範囲 (例: L1-L1000 は不可)")
        else:
            result.issues.append(f"❌ Sources行に行番号なし (例: [file.ts:L100-L200])")
    elif sources_lines:
        result.score += 5  # 行番号不要の場合の部分点

    # --- 8. セクション数 (5点) ---
    result.max_score += 5
    section_count = count_sections(content)
    min_sections = reqs['min_sections']
    if section_count >= min_sections:
        result.score += 5
        result.passes.append(f"✅ セクション数: {section_count} (基準: {min_sections}以上)")
    else:
        result.issues.append(f"⚠️  セクション不足: {section_count} (基準: {min_sections}以上)")
        result.score += 2 if section_count > 0 else 0

    # --- 9. 概要段落 (5点) ---
    result.max_score += 5
    if check_overview_paragraph(content):
        result.score += 5
        result.passes.append("✅ 概要段落あり")
    else:
        result.issues.append("❌ 概要段落なし (# 見出しの直後にスコープ説明が必要)")

    # --- 10. ダイアグラムの具体性 (5点) ---
    result.max_score += 5
    if mermaid_count > 0:
        specific, generic = check_mermaid_has_real_names(content)
        if specific > 0:
            result.score += 5
            result.passes.append(f"✅ Mermaid内に具体的な名前: {specific}個")
        elif generic > 0:
            result.score += 2
            result.issues.append(f"⚠️  Mermaid内が汎用名のみ ({generic}個) → 実際のクラス名を使用")
    else:
        result.score += 0

    # --- 11. 関連ページリンク (5点) ---
    result.max_score += 5
    if check_related_pages(content):
        result.score += 5
        result.passes.append("✅ 関連ページリンクあり")
    else:
        result.issues.append("⚠️  関連ページリンクなし")

    # --- 12. Mermaid構文静的チェック (5点) ---
    result.max_score += 5
    mermaid_blocks_raw = re.findall(r'```mermaid\n([\s\S]*?)```', content)
    mermaid_syntax_errors = []
    for block in mermaid_blocks_raw:
        # LRレイアウト
        if re.search(r'\b(?:graph|flowchart)\s+LR\b', block):
            mermaid_syntax_errors.append("LRレイアウト (graph LR / flowchart LR) が使用されています")
        # []内に()が含まれてクォートされていない
        unquoted_bp = re.findall(r'\[[^\]"]*\([^)]*\)[^\]"]*\]', block)
        if unquoted_bp:
            mermaid_syntax_errors.append(f"ノード [] 内に括弧 () が含まれているのにクォートされていません: {unquoted_bp[:1]}")
        # ()内に[]が含まれてクォートされていない
        unquoted_pb = re.findall(r'\([^)"]*\[[^\]]*\][^)"]*\)', block)
        if unquoted_pb:
            mermaid_syntax_errors.append(f"ノード () 内に角括弧 [] が含まれているのにクォートされていません: {unquoted_pb[:1]}")
        # {}内に括弧や|が含まれてクォートされていない
        unquoted_bs = re.findall(r'\{[^}"]*[(\[|][^}"]*\}', block)
        if unquoted_bs:
            mermaid_syntax_errors.append(f"ひし形ノード {{}} 内に括弧や | が含まれているのにクォートされていません: {unquoted_bs[:1]}")
        # フローチャートのノードラベル内に|パイプが含まれてクォートされていない
        if re.search(r'\b(?:graph|flowchart)\b', block):
            unquoted_pipe = re.findall(r'(?:\[|\()([^"()\[\]]*\|[^"()\[\]]*?)(?:\]|\))', block)
            if unquoted_pipe:
                mermaid_syntax_errors.append(f"ノードラベル内に | パイプ文字が含まれているのにクォートされていません: {unquoted_pipe[:1]}")
        # HTMLタグ
        if re.search(r'<[a-zA-Z][^>]*>', block):
            mermaid_syntax_errors.append("Mermaid内にHTMLタグが使用されています")
        # シーケンス図固有チェック
        if 'sequenceDiagram' in block:
            # フローチャート風記法
            if re.search(r'--\|[^|]*\|-->', block):
                mermaid_syntax_errors.append("シーケンス図でフローチャート風記法 A--|label|-->B が使われています")
            # コロン後が空のラベル
            if re.search(r'(?:->>[+\-]?|-->>[+\-]?|-\)[+\-]?)\s*[\w]+\s*:\s*$', block, re.MULTILINE):
                mermaid_syntax_errors.append("シーケンス図のメッセージ行でコロン（:）後のラベルが空です（例: A->>B:）")

    if not mermaid_syntax_errors:
        result.score += 5
        if mermaid_count > 0:
            result.passes.append("✅ Mermaid構文: 静的チェックOK")
        else:
            result.passes.append("✅ Mermaid構文: ブロックなし（チェック対象なし）")
    else:
        for err in mermaid_syntax_errors[:3]:
            result.issues.append(f"❌ Mermaid構文エラー: {err}")

    # --- 13. テーブル (5点) ---
    result.max_score += 5
    table_count = count_tables(content)
    min_tables = reqs['min_tables']
    if min_tables > 0:
        if table_count >= min_tables:
            result.score += 5
            result.passes.append(f"✅ テーブル: {table_count}個 (基準: {min_tables}以上)")
        elif table_count > 0:
            result.score += 2
            result.issues.append(f"⚠️  テーブル不足: {table_count}個 (基準: {min_tables}以上)")
        else:
            result.issues.append(f"❌ テーブルなし (基準: {min_tables}以上, 列挙型・定数・カテゴリをテーブルで整理)")
    else:
        if table_count > 0:
            result.score += 5
            result.passes.append(f"✅ テーブル: {table_count}個 (推奨)")
        else:
            result.score += 3  # medium/low ではテーブルなしでも許容
            result.passes.append(f"✅ テーブル: 任意 (importance: {importance})")

    return result


def format_result(result: ValidationResult) -> str:
    """結果のフォーマット"""
    lines = []
    basename = os.path.basename(result.file)
    lines.append(f"{'='*60}")
    lines.append(f"📄 {basename}")
    lines.append(f"   Importance: {result.importance}  |  Grade: {result.grade}  |  Score: {result.score}/{result.max_score} ({result.percentage:.0f}%)")
    lines.append(f"{'='*60}")

    if result.issues:
        lines.append("")
        lines.append("  改善が必要:")
        for issue in result.issues:
            lines.append(f"    {issue}")

    if result.passes:
        lines.append("")
        lines.append("  合格項目:")
        for p in result.passes:
            lines.append(f"    {p}")

    if getattr(result, 'mermaid_validation_errors', None):
        lines.append("")
        lines.append("  ❌ Mermaid構文エラー:")
        for err in result.mermaid_validation_errors:
            indented_err = "\n".join([f"    > {line}" for line in err.split("\n")])
            lines.append(indented_err)

    lines.append("")
    return '\n'.join(lines)


def format_summary(results: list) -> str:
    """全体サマリーのフォーマット"""
    lines = []
    lines.append(f"\n{'#'*60}")
    lines.append(f"  DeepWiki 品質レポート")
    lines.append(f"{'#'*60}\n")

    total_score = sum(r.score for r in results)
    total_max = sum(r.max_score for r in results)
    avg_pct = (total_score / total_max * 100) if total_max > 0 else 0

    # グレード分布
    grades = {}
    for r in results:
        g = r.grade
        grades[g] = grades.get(g, 0) + 1

    lines.append(f"  総合スコア: {total_score}/{total_max} ({avg_pct:.0f}%)")
    lines.append(f"  ページ数: {len(results)}")
    lines.append(f"  グレード分布: {', '.join(f'{g}={c}' for g, c in sorted(grades.items()))}")
    lines.append("")

    # ページ別サマリー表
    lines.append(f"  {'ページ':<45} {'Grade':>5}  {'Score':>10}")
    lines.append(f"  {'-'*45} {'-'*5}  {'-'*10}")
    for r in results:
        basename = os.path.basename(r.file)
        lines.append(f"  {basename:<45} {r.grade:>5}  {r.score:>3}/{r.max_score:<3} ({r.percentage:.0f}%)")

    # 不合格ページ
    failing = [r for r in results if r.grade in ('D', 'F')]
    if failing:
        lines.append(f"\n  ⚠️  要改善ページ ({len(failing)}件):")
        for r in failing:
            basename = os.path.basename(r.file)
            top_issues = [i for i in r.issues if i.startswith('❌')][:3]
            lines.append(f"    - {basename}: {', '.join(top_issues)}")

    lines.append("")
    return '\n'.join(lines)


# --- Wiki 全体構造バリデーション ---

# 規模別ガイドライン（SKILL.md Phase 2 と同期）
SCALE_GUIDELINES = {
    "small": {
        "label": "小規模",
        "file_count": "<30",
        "min_sections": 3,
        "max_sections": 4,
        "min_pages": 8,
        "max_pages": 15,
    },
    "medium": {
        "label": "中規模",
        "file_count": "30-200",
        "min_sections": 4,
        "max_sections": 6,
        "min_pages": 15,
        "max_pages": 30,
    },
    "large": {
        "label": "大規模",
        "file_count": ">200",
        "min_sections": 6,
        "max_sections": 8,
        "min_pages": 30,
        "max_pages": 50,
    },
}

# 必須セクション（SKILL.md のセクション構成テンプレートに基づく）
SECTION_DEFINITIONS = {
    1: {"name": "Overview", "required": True, "desc": "アーキテクチャ概要・プロジェクト構成"},
    2: {"name": "Getting Started", "required": True, "desc": "インストール・セットアップ・認証・設定"},
    3: {"name": "User Guide", "required": True, "desc": "ユーザー向け機能（CLI、UI、操作方法）"},
    4: {"name": "Core Systems", "required": True, "desc": "内部アーキテクチャの主要モジュール"},
    5: {"name": "Advanced Topics", "required": False, "desc": "拡張性・セキュリティ・プラグイン・可観測性"},
    6: {"name": "Development", "required": False, "desc": "開発環境・ビルド・テスト"},
}


def infer_scale(page_count: int) -> str:
    """ページ数から規模を推定"""
    if page_count <= 15:
        return "small"
    elif page_count <= 30:
        return "medium"
    else:
        return "large"


def analyze_sections(results: list) -> dict:
    """ファイル名からセクション構造を分析"""
    sections = {}  # section_num -> list of page basenames
    unclassified = []

    for r in results:
        basename = os.path.basename(r.file)
        if basename == 'index.md':
            continue
        # x.y-name.md or x-name.md
        match = re.match(r'^(\d+)', basename)
        if match:
            section_num = int(match.group(1))
            if section_num not in sections:
                sections[section_num] = []
            sections[section_num].append(basename)
        else:
            unclassified.append(basename)

    return sections, unclassified


@dataclass
class WikiStructureResult:
    """Wiki全体構造の検証結果"""
    scale: str
    page_count: int
    issues: list = field(default_factory=list)
    passes: list = field(default_factory=list)
    score: int = 0
    max_score: int = 0


def validate_wiki_structure(results: list, scale: Optional[str] = None) -> WikiStructureResult:
    """Wiki全体の構造を検証（ページ数・セクション網羅性・配分）"""
    page_count = len([r for r in results if os.path.basename(r.file) != 'index.md'])

    if scale is None:
        scale = infer_scale(page_count)

    guide = SCALE_GUIDELINES[scale]
    ws = WikiStructureResult(scale=scale, page_count=page_count)
    sections, unclassified = analyze_sections(results)

    # --- 1. 総ページ数チェック (20点) ---
    ws.max_score += 20
    min_p, max_p = guide['min_pages'], guide['max_pages']
    if min_p <= page_count <= max_p:
        ws.score += 20
        ws.passes.append(f"✅ ページ数: {page_count} (規模'{guide['label']}': {min_p}-{max_p}ページ)")
    elif page_count > max_p:
        ws.score += 15  # ページ多い分は減点少なめ
        ws.issues.append(f"⚠️  ページ数が多い: {page_count} (規模'{guide['label']}': {min_p}-{max_p}ページ)")
    elif page_count >= min_p * 0.7:
        ws.score += 10
        ws.issues.append(f"⚠️  ページ数がやや少ない: {page_count} (規模'{guide['label']}': {min_p}-{max_p}ページ)")
    else:
        ws.issues.append(f"❌ ページ数不足: {page_count} (規模'{guide['label']}': {min_p}ページ以上必要)")

    # --- 2. 必須セクション網羅性チェック (30点) ---
    ws.max_score += 30
    required_present = 0
    required_total = 0
    missing_required = []
    missing_optional = []

    for sec_num, sec_def in SECTION_DEFINITIONS.items():
        if sec_def['required']:
            required_total += 1
            if sec_num in sections:
                required_present += 1
            else:
                missing_required.append(f"Section {sec_num} ({sec_def['name']}): {sec_def['desc']}")
        else:
            if sec_num not in sections:
                missing_optional.append(f"Section {sec_num} ({sec_def['name']}): {sec_def['desc']}")

    if required_present == required_total:
        ws.score += 30
        ws.passes.append(f"✅ 必須セクション: {required_present}/{required_total} 全て存在")
    else:
        ws.score += int(30 * required_present / required_total)
        for m in missing_required:
            ws.issues.append(f"❌ 必須セクション欠落: {m}")

    if missing_optional:
        for m in missing_optional:
            ws.issues.append(f"⚠️  推奨セクション欠落: {m}")

    # --- 3. Core Systems + User Guide の配分チェック (20点) ---
    ws.max_score += 20
    core_user_pages = len(sections.get(3, [])) + len(sections.get(4, []))
    if page_count > 0:
        ratio = core_user_pages / page_count
        if 0.40 <= ratio <= 0.70:
            ws.score += 20
            ws.passes.append(f"✅ Core Systems + User Guide の配分: {core_user_pages}/{page_count} ({ratio:.0%})")
        elif 0.30 <= ratio < 0.40:
            ws.score += 10
            ws.issues.append(f"⚠️  Core Systems + User Guide の配分が低い: {core_user_pages}/{page_count} ({ratio:.0%}, 推奨: 50-60%)")
        elif ratio > 0.70:
            ws.score += 15
            ws.issues.append(f"⚠️  Core Systems + User Guide が多すぎる: {core_user_pages}/{page_count} ({ratio:.0%}, Overview/Getting Started も充実させる)")
        else:
            ws.issues.append(f"❌ Core Systems + User Guide の配分が不適切: {core_user_pages}/{page_count} ({ratio:.0%}, 推奨: 50-60%)")

    # --- 4. セクション数チェック (15点) ---
    ws.max_score += 15
    section_count = len(sections)
    min_s, max_s = guide['min_sections'], guide['max_sections']
    if min_s <= section_count <= max_s:
        ws.score += 15
        ws.passes.append(f"✅ セクション数: {section_count} (規模'{guide['label']}': {min_s}-{max_s})")
    elif section_count > max_s:
        ws.score += 12
        ws.issues.append(f"⚠️  セクション数が多い: {section_count} (規模'{guide['label']}': {min_s}-{max_s})")
    elif section_count >= min_s - 1:
        ws.score += 8
        ws.issues.append(f"⚠️  セクション数がやや少ない: {section_count} (規模'{guide['label']}': {min_s}-{max_s})")
    else:
        ws.issues.append(f"❌ セクション数不足: {section_count} (規模'{guide['label']}': {min_s}以上必要)")

    # --- 5. 品質グレード分布チェック (15点) ---
    ws.max_score += 15
    grade_b_plus = sum(1 for r in results if r.grade in ('A', 'B') and os.path.basename(r.file) != 'index.md')
    grade_d_f = sum(1 for r in results if r.grade in ('D', 'F') and os.path.basename(r.file) != 'index.md')
    b_plus_ratio = grade_b_plus / page_count if page_count > 0 else 0
    if b_plus_ratio >= 0.80:
        ws.score += 15
        ws.passes.append(f"✅ Grade B以上の比率: {grade_b_plus}/{page_count} ({b_plus_ratio:.0%})")
    elif b_plus_ratio >= 0.60:
        ws.score += 10
        ws.issues.append(f"⚠️  Grade B以上の比率が低い: {grade_b_plus}/{page_count} ({b_plus_ratio:.0%}, 目標: 80%以上)")
    else:
        ws.score += 5 if grade_b_plus > 0 else 0
        ws.issues.append(f"❌ Grade B以上の比率が不足: {grade_b_plus}/{page_count} ({b_plus_ratio:.0%}, 目標: 80%以上)")

    if grade_d_f > 0:
        ws.issues.append(f"❌ Grade D/F のページが {grade_d_f} 件あり（修正が必要）")

    return ws


def format_structure_result(ws: WikiStructureResult, sections: dict) -> str:
    """構造チェック結果のフォーマット"""
    lines = []
    lines.append(f"\n{'='*60}")
    lines.append(f"  📊 Wiki 構造チェック (規模: {SCALE_GUIDELINES[ws.scale]['label']})")
    lines.append(f"{'='*60}")
    pct = (ws.score / ws.max_score * 100) if ws.max_score > 0 else 0
    lines.append(f"  スコア: {ws.score}/{ws.max_score} ({pct:.0f}%)")
    lines.append("")

    # セクション別ページ数
    lines.append("  セクション別ページ数:")
    for sec_num in sorted(sections.keys()):
        sec_def = SECTION_DEFINITIONS.get(sec_num, {"name": f"Section {sec_num}", "required": False})
        req_mark = "★" if sec_def.get('required') else " "
        lines.append(f"    {req_mark} Section {sec_num} ({sec_def['name']}): {len(sections[sec_num])}ページ")
    lines.append("")

    if ws.passes:
        lines.append("  合格項目:")
        for p in ws.passes:
            lines.append(f"    {p}")
        lines.append("")

    if ws.issues:
        lines.append("  改善が必要:")
        for i in ws.issues:
            lines.append(f"    {i}")
        lines.append("")

    return '\n'.join(lines)


def generate_ai_corrections(results: list, ws: Optional[WikiStructureResult] = None) -> str:
    """AIモデルが実行すべき修正指示を生成する"""
    lines = []
    lines.append(f"\n{'='*60}")
    lines.append(f"  🤖 AIモデル向け修正指示")
    lines.append(f"{'='*60}")

    instructions = []
    priority = 1

    # --- 構造レベルの修正指示 ---
    if ws:
        for issue in ws.issues:
            if '必須セクション欠落' in issue:
                # セクション名を抽出
                match = re.search(r'Section (\d+) \((.+?)\): (.+)', issue)
                if match:
                    sec_num, sec_name, sec_desc = match.groups()
                    instructions.append({
                        "priority": priority,
                        "type": "構造: セクション追加",
                        "action": f"Section {sec_num} ({sec_name}) を新規作成してください。\n"
                                  f"        内容: {sec_desc}\n"
                                  f"        ファイル命名例: {sec_num}.1-{sec_name.lower().replace(' ', '-')}.md\n"
                                  f"        作成手順: Phase 3a（ソースコード分析）→ Phase 3b（ページ生成）の順で進め、\n"
                                  f"        関連するソースファイルをファイル閲覧ツール等で読み、スニペット候補を5個以上リストアップしてから書き始めてください。",
                    })
                    priority += 1

            elif 'ページ数不足' in issue:
                instructions.append({
                    "priority": priority,
                    "type": "構造: ページ追加",
                    "action": f"ページ数が不足しています。Core Systems (Section 4) で1モジュール=1ページの原則に沿って分割を検討してください。\n"
                              f"        特に、1つのページで複数モジュールを説明している場合は分割してください。\n"
                              f"        User Guide (Section 3) でもユーザー向け機能ごとにページを追加できるか確認してください。",
                })
                priority += 1

            elif 'Grade D/F' in issue:
                d_f_pages = [r for r in results if r.grade in ('D', 'F') and os.path.basename(r.file) != 'index.md']
                for r in d_f_pages:
                    basename = os.path.basename(r.file)
                    top_issues = [i for i in r.issues if i.startswith('❌')]
                    instructions.append({
                        "priority": priority,
                        "type": f"ページ修正: {basename}",
                        "action": f"このページは Grade {r.grade} ({r.percentage:.0f}%) です。以下を修正してください:\n" +
                                  "\n".join(f"        - {i}" for i in top_issues),
                    })
                    priority += 1

    # --- ページレベルの修正指示（Grade C 以下） ---
    problem_pages = sorted(
        [r for r in results if r.grade in ('C', 'D', 'F') and os.path.basename(r.file) != 'index.md'],
        key=lambda r: r.percentage
    )

    for r in problem_pages:
        basename = os.path.basename(r.file)
        critical_issues = [i for i in r.issues if i.startswith('❌')]
        warning_issues = [i for i in r.issues if i.startswith('⚠️')]

        if not critical_issues and not warning_issues:
            continue

        action_parts = []

        for issue in critical_issues:
            if 'コードスニペット' in issue:
                action_parts.append(
                    "コードスニペットを追加してください。対象ファイルをファイル閲覧ツール等で読み直し、\n"
                    "          主要クラスの定義、インターフェース、重要メソッドのシグネチャを抜粋してください。\n"
                    "          各スニペットの先頭に `// path/to/file.ts:L行番号` の出典コメントを付けてください。"
                )
            elif '語数不足' in issue:
                action_parts.append(
                    "内容を充実させてください。具体的には:\n"
                    "          - 設計パターンの説明と適用箇所の解説を追加\n"
                    "          - データフロー（入力→処理→出力）の説明を追加\n"
                    "          - エッジケースやエラーハンドリングの解説を追加"
                )
            elif 'Mermaid構文エラー' in issue:
                action_parts.append(
                    f"Mermaidグラフの構文エラーを修正してください: {issue}\n"
                    "          エラー詳細は実行結果の 'Mermaid構文エラー' セクションを確認してください。"
                )
            elif 'Mermaid' in issue:
                action_parts.append(
                    "Mermaidダイアグラムを追加してください。推奨: flowchart（処理フロー）+ sequenceDiagram（モジュール間通信）の2種類。\n"
                    "          ノードラベルには実際のクラス名・関数名を使用してください。"
                )
            elif 'Sources' in issue:
                action_parts.append(
                    "Sources行を各セクション末尾に追加してください。形式: **Sources:** [file.ts:L100-L200](file:///path#L100-L200)\n"
                    "          行番号は実際にファイル閲覧ツール等で読んだ範囲を200行以内で指定してください。"
                )
            elif 'テーブル' in issue:
                action_parts.append(
                    "テーブルを追加してください。対象: 列挙型の値一覧、定数グループ、コンポーネントの役割分担、設定パラメータ等。"
                )

        for issue in warning_issues:
            if 'Mermaid種類が単一' in issue or 'Mermaid内が汎用名' in issue:
                action_parts.append(
                    "Mermaidダイアグラムの種類を増やしてください。graph TD だけでなく sequenceDiagram や stateDiagram-v2 も使い分けてください。"
                )
            elif '行番号が不正確' in issue or '行番号なし' in issue:
                action_parts.append(
                    "Sources行の行番号を正確にしてください。L1-L1000 のような広範囲は不可。参照した関数・クラスの実際の行範囲を200行以内で記載してください。"
                )

        if action_parts:
            # 重複した指示を排除
            seen = set()
            unique_parts = []
            for part in action_parts:
                key = part[:30]  # 先頭30文字で重複判定
                if key not in seen:
                    seen.add(key)
                    unique_parts.append(part)

            instructions.append({
                "priority": priority,
                "type": f"ページ改善: {basename} (Grade {r.grade}, {r.percentage:.0f}%)",
                "action": "\n".join(f"        [{i+1}] {p}" for i, p in enumerate(unique_parts)),
            })
            priority += 1

    # --- 出力 ---
    if not instructions:
        lines.append("\n  ✅ 修正指示なし — 全ページが基準を満たしています。")
    else:
        lines.append(f"\n  修正指示: {len(instructions)}件 (優先度順)\n")
        for inst in instructions:
            lines.append(f"  [{inst['priority']}] {inst['type']}")
            lines.append(f"      {inst['action']}")
            lines.append("")

    lines.append("")
    return '\n'.join(lines)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    target = sys.argv[1]
    importance_override = None
    scale_override = None

    if '--importance' in sys.argv:
        idx = sys.argv.index('--importance')
        if idx + 1 < len(sys.argv):
            importance_override = sys.argv[idx + 1]

    if '--scale' in sys.argv:
        idx = sys.argv.index('--scale')
        if idx + 1 < len(sys.argv):
            scale_override = sys.argv[idx + 1]

    # 単一ファイル or ディレクトリ
    if os.path.isfile(target):
        result = validate_page(target, importance_override)
        print(format_result(result))

        # ページ単体でもAI修正指示を出す
        if result.grade in ('C', 'D', 'F'):
            print(generate_ai_corrections([result]))

        # 終了コード: Grade B以上が合格
        sys.exit(0 if result.grade in ('A', 'B') else 1)

    elif os.path.isdir(target):
        md_files = sorted(Path(target).glob('*.md'))
        if not md_files:
            print(f"ERROR: {target} に .md ファイルがありません")
            sys.exit(1)

        results = []
        for md_file in md_files:
            result = validate_page(str(md_file), importance_override)
            results.append(result)

        # Now we can safely print the outputs
        for result in results:
            print(format_result(result))

        print(format_summary(results))

        # Wiki 構造チェック
        ws = validate_wiki_structure(results, scale_override)
        sections, _ = analyze_sections(results)
        print(format_structure_result(ws, sections))

        # AI 修正指示
        problem_pages = [r for r in results if r.grade in ('C', 'D', 'F')]
        if problem_pages or ws.issues:
            print(generate_ai_corrections(results, ws))

        # 全ページ B以上なら成功
        failing = [r for r in results if r.grade in ('C', 'D', 'F')]
        sys.exit(0 if not failing else 1)

    else:
        print(f"ERROR: {target} が見つかりません")
        sys.exit(1)


if __name__ == '__main__':
    main()
