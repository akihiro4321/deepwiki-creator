#!/usr/bin/env python3
"""
microservices-wiki ページ品質バリデーター

生成されたアーキテクチャ Wiki ページが品質基準を満たしているかを検証する。
deepwiki の validate_page.py をベースに、アーキテクチャWiki特有の基準を追加。

使用方法:
  python validate_arch_page.py <ページファイル.md> [--importance high|medium|low]
  python validate_arch_page.py <arch-wikiディレクトリ> [--scale small|medium|large]
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
    importance: str
    score: int = 0
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


# --- 品質基準定義 ---
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
        "min_tables": 1,
    },
}

MAX_ACCEPTABLE_LINE_RANGE = 200

# アーキテクチャWiki特有: サービス名として汎用的すぎる名前
GENERIC_SERVICE_NAMES = {
    'ServiceA', 'ServiceB', 'ServiceC',
    'service-a', 'service-b', 'service-c',
    'Service', 'Microservice', 'Backend', 'Frontend',
    'API', 'Client', 'Server', 'Database', 'Cache',
    'Component', 'Module', 'System',
}


def count_words(text: str) -> int:
    """日本語+英語の混合テキストの語数を推定"""
    cleaned = re.sub(r'```[\s\S]*?```', '', text)
    cleaned = re.sub(r'[#|>\-*`\[\]()]', ' ', cleaned)
    jp_chars = len(re.findall(r'[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]', cleaned))
    en_words = len(re.findall(r'[a-zA-Z]+', cleaned))
    return jp_chars + en_words


def count_mermaid_diagrams(text: str) -> int:
    return len(re.findall(r'```mermaid', text))


def get_mermaid_types(text: str) -> set:
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
        else:
            types.add('other')
    return types


def count_code_snippets(text: str) -> int:
    """Mermaid 以外のコードブロックをカウント"""
    all_blocks = re.findall(r'```(\w*)', text)
    return sum(1 for lang in all_blocks if lang and lang != 'mermaid')


def count_snippet_citations(text: str) -> int:
    """コードスニペット内の出典コメントをカウント"""
    code_blocks = re.findall(r'```\w+\n([\s\S]*?)```', text)
    citations = 0
    for block in code_blocks:
        # path:L行番号 形式、またはファイル名: 形式
        if re.search(r'(#|//|--)\s*\S+\.(ya?ml|tf|json|sql|conf|proto|toml)\s*[:\s]', block) or \
           re.search(r'//\s*\S+\.(ts|js|py|go|rs|java)\s*[:\s]L\d+', block):
            citations += 1
    return citations


def count_tables(text: str) -> int:
    lines = text.split('\n')
    table_count = 0
    for i in range(len(lines) - 1):
        if re.match(r'\s*\|.*\|.*\|', lines[i]) and \
           re.match(r'\s*\|[\s\-:]+\|[\s\-:]+\|', lines[i + 1]):
            table_count += 1
    return table_count


def find_sources_lines(text: str) -> list:
    return re.findall(r'^.*Sources?:.*$', text, re.MULTILINE)


def check_line_numbers_in_sources(sources_lines: list) -> tuple:
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
    return len(re.findall(r'^## ', text, re.MULTILINE))


def check_overview_paragraph(text: str) -> bool:
    lines = text.split('\n')
    found_h1 = False
    for line in lines:
        if line.startswith('# ') and not line.startswith('## '):
            found_h1 = True
            continue
        if found_h1 and line.startswith('## '):
            break
        if found_h1 and line.strip() and not line.startswith('#') and \
           not line.startswith('```') and not line.startswith('>'):
            return True
    return False


def check_related_pages(text: str) -> bool:
    return bool(re.search(r'(関連ページ|Related|← 前|→ 次|参照)', text, re.IGNORECASE))


def check_arch_specific_quality(text: str) -> tuple:
    """
    アーキテクチャWiki特有の品質チェック:
    1. Mermaid内にサービス名の具体性（汎用名でないか）
    2. 通信プロトコルがMermaidまたはテキストに明記されているか
    """
    issues = []
    passes = []
    score = 0
    max_score = 0

    # --- 1. Mermaid内のサービス名具体性チェック (5点) ---
    max_score += 5
    mermaid_blocks = re.findall(r'```mermaid\n([\s\S]*?)```', text)
    generic_count = 0
    specific_count = 0

    for block in mermaid_blocks:
        # ノードラベルを抽出
        labels = re.findall(r'\[([^\]]+)\]', block)
        labels += re.findall(r'"([^"]+)"', block)
        for label in labels:
            clean = label.strip('"').strip()
            if clean in GENERIC_SERVICE_NAMES:
                generic_count += 1
            elif re.match(r'[a-zA-Z][a-zA-Z0-9_-]+-[a-zA-Z]', clean) or \
                 re.match(r'[A-Z][a-z]+[A-Z]', clean) or \
                 len(clean.split()) >= 2:
                specific_count += 1

    if specific_count > 0 and generic_count == 0:
        score += 5
        passes.append(f"✅ Mermaid内のサービス名が具体的: {specific_count}個")
    elif specific_count > 0:
        score += 3
        issues.append(f"⚠️  Mermaid内に汎用名が混在: 具体的{specific_count}個, 汎用{generic_count}個")
    elif generic_count > 0:
        score += 0
        issues.append(f"❌ Mermaid内のサービス名が汎用的: {generic_count}個 (実際のサービス名を使用してください)")
    else:
        score += 3  # Mermaidがない場合は中間点
        passes.append("✅ Mermaid内のラベルチェック: 対象外")

    # --- 2. 通信プロトコルの明記チェック (5点) ---
    max_score += 5
    protocol_patterns = [
        r'\bREST\b', r'\bgRPC\b', r'\bHTTP\b', r'\bHTTPS\b',
        r'\bKafka\b', r'\bRabbitMQ\b', r'\bNATS\b', r'\bSQS\b',
        r'\bWebSocket\b', r'\bGraphQL\b', r'\bEvent\b.*\bStreaming\b',
    ]
    found_protocols = []
    for pattern in protocol_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            found_protocols.append(pattern.replace(r'\b', '').replace(r'\B', ''))

    if len(found_protocols) >= 2:
        score += 5
        passes.append(f"✅ 通信プロトコルが明記されている: {', '.join(found_protocols[:3])} 等")
    elif len(found_protocols) == 1:
        score += 3
        passes.append(f"✅ 通信プロトコルの言及あり: {found_protocols[0]}")
    else:
        issues.append("⚠️  通信プロトコル（REST/gRPC/Kafka等）の明記がない")

    return score, max_score, issues, passes


def detect_importance(filepath: str) -> str:
    """ファイルパスからimportanceを推測"""
    basename = os.path.basename(filepath)
    if basename == 'index.md':
        return 'index'

    match = re.match(r'(\d+)\.(\d+)', basename)
    if match:
        section = int(match.group(1))
        # System Overview (1.x) と Service Communication (2.x) は high
        if section in (1, 2):
            return 'high'
        else:
            return 'medium'

    return 'medium'


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
        result.issues.append(f"⚠️  語数不足: {word_count} (基準: {min_words}以上)")
    else:
        result.issues.append(f"❌ 語数不足: {word_count} (基準: {min_words}以上)")

    # --- 2. Mermaid数 (10点) ---
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

    # --- 3. Mermaid種類の多様性 (5点) ---
    result.max_score += 5
    mermaid_types = get_mermaid_types(content)
    min_types = reqs['min_mermaid_types']
    if len(mermaid_types) >= min_types:
        result.score += 5
        result.passes.append(f"✅ Mermaid種類: {', '.join(sorted(mermaid_types))} ({len(mermaid_types)}種類)")
    elif len(mermaid_types) > 0:
        result.score += 2
        result.issues.append(f"⚠️  Mermaid種類不足: {', '.join(sorted(mermaid_types))} ({len(mermaid_types)}種類, 基準: {min_types}以上)")
    else:
        result.issues.append("❌ Mermaidなし")

    # --- 4. コードスニペット数 (15点) ---
    result.max_score += 15
    snippet_count = count_code_snippets(content)
    min_snippets = reqs['min_code_snippets']
    if snippet_count >= min_snippets:
        result.score += 15
        result.passes.append(f"✅ コードスニペット: {snippet_count}個 (基準: {min_snippets}以上)")
    elif snippet_count > 0 and min_snippets > 0:
        partial = min(10, int(15 * snippet_count / min_snippets))
        result.score += partial
        result.issues.append(f"⚠️  コードスニペット不足: {snippet_count}個 (基準: {min_snippets}以上)")
    elif min_snippets > 0:
        result.issues.append(f"❌ コードスニペットなし (基準: {min_snippets}以上, インフラ定義ファイルから引用)")
    else:
        result.score += 15

    # --- 5. スニペット出典コメント (5点) ---
    result.max_score += 5
    if snippet_count > 0:
        citation_count = count_snippet_citations(content)
        if citation_count >= snippet_count * 0.6:
            result.score += 5
            result.passes.append(f"✅ スニペット出典: {citation_count}/{snippet_count}個に出典コメントあり")
        elif citation_count > 0:
            result.score += 2
            result.issues.append(f"⚠️  スニペット出典不足: {citation_count}/{snippet_count}個のみ")
        else:
            result.issues.append("❌ スニペット出典なし (# path/to/file.yml 形式のコメントが必要)")

    # --- 6. Sources行存在 (10点) ---
    result.max_score += 10
    sources_lines = find_sources_lines(content)
    min_sources = reqs['min_sources_lines']
    if len(sources_lines) >= min_sources:
        result.score += 10
        result.passes.append(f"✅ Sources行: {len(sources_lines)}行")
    elif len(sources_lines) > 0:
        result.score += 5
        result.issues.append(f"⚠️  Sources行不足: {len(sources_lines)}行 (基準: {min_sources}以上)")
    else:
        result.issues.append(f"❌ Sources行なし")

    # --- 7. Sources行番号精度 (10点) ---
    result.max_score += 10
    if sources_lines and reqs['sources_need_line_numbers']:
        precise, imprecise, no_ln = check_line_numbers_in_sources(sources_lines)
        if precise > 0 and imprecise == 0 and no_ln == 0:
            result.score += 10
            result.passes.append(f"✅ Sources行番号: 全{precise}行に正確な行番号あり")
        elif precise > 0:
            result.score += 7
            result.issues.append(f"⚠️  Sources行番号: 正確{precise}行, 不正確{imprecise}行, 行番号なし{no_ln}行")
        elif imprecise > 0:
            result.score += 3
            result.issues.append(f"⚠️  Sources行番号が不正確: {imprecise}行が{MAX_ACCEPTABLE_LINE_RANGE}行超")
        else:
            result.issues.append("❌ Sources行に行番号なし ([docker-compose.yml:L1-L45] 形式)")
    elif sources_lines:
        result.score += 5

    # --- 8. セクション数 (5点) ---
    result.max_score += 5
    section_count = count_sections(content)
    min_sections = reqs['min_sections']
    if section_count >= min_sections:
        result.score += 5
        result.passes.append(f"✅ セクション数: {section_count}")
    else:
        result.issues.append(f"⚠️  セクション不足: {section_count} (基準: {min_sections}以上)")
        result.score += 2 if section_count > 0 else 0

    # --- 9. 概要段落 (5点) ---
    result.max_score += 5
    if check_overview_paragraph(content):
        result.score += 5
        result.passes.append("✅ 概要段落あり")
    else:
        result.issues.append("❌ 概要段落なし")

    # --- 10. 関連ページリンク (5点) ---
    result.max_score += 5
    if check_related_pages(content):
        result.score += 5
        result.passes.append("✅ 関連ページリンクあり")
    else:
        result.issues.append("⚠️  関連ページリンクなし")

    # --- 11. テーブル (5点) ---
    result.max_score += 5
    table_count = count_tables(content)
    min_tables = reqs['min_tables']
    if min_tables > 0:
        if table_count >= min_tables:
            result.score += 5
            result.passes.append(f"✅ テーブル: {table_count}個")
        elif table_count > 0:
            result.score += 2
            result.issues.append(f"⚠️  テーブル不足: {table_count}個 (基準: {min_tables}以上)")
        else:
            result.issues.append("❌ テーブルなし (サービス一覧・API一覧等をテーブルで整理)")
    else:
        result.score += 5 if table_count > 0 else 3

    # --- 12. アーキテクチャ特有チェック (10点) ---
    arch_score, arch_max, arch_issues, arch_passes = check_arch_specific_quality(content)
    result.score += arch_score
    result.max_score += arch_max
    result.issues.extend(arch_issues)
    result.passes.extend(arch_passes)

    return result


def format_result(result: ValidationResult) -> str:
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

    lines.append("")
    return '\n'.join(lines)


def format_summary(results: list) -> str:
    lines = []
    lines.append(f"\n{'#'*60}")
    lines.append(f"  microservices-wiki 品質レポート")
    lines.append(f"{'#'*60}\n")

    total_score = sum(r.score for r in results)
    total_max = sum(r.max_score for r in results)
    avg_pct = (total_score / total_max * 100) if total_max > 0 else 0

    grades = {}
    for r in results:
        g = r.grade
        grades[g] = grades.get(g, 0) + 1

    lines.append(f"  総合スコア: {total_score}/{total_max} ({avg_pct:.0f}%)")
    lines.append(f"  ページ数: {len(results)}")
    lines.append(f"  グレード分布: {', '.join(f'{g}={c}' for g, c in sorted(grades.items()))}")
    lines.append("")

    lines.append(f"  {'ページ':<45} {'Grade':>5}  {'Score':>10}")
    lines.append(f"  {'-'*45} {'-'*5}  {'-'*10}")
    for r in results:
        basename = os.path.basename(r.file)
        lines.append(f"  {basename:<45} {r.grade:>5}  {r.score:>3}/{r.max_score:<3} ({r.percentage:.0f}%)")

    failing = [r for r in results if r.grade in ('D', 'F')]
    if failing:
        lines.append(f"\n  ⚠️  要改善ページ ({len(failing)}件):")
        for r in failing:
            basename = os.path.basename(r.file)
            top_issues = [i for i in r.issues if i.startswith('❌')][:3]
            lines.append(f"    - {basename}: {', '.join(top_issues)}")

    lines.append("")
    return '\n'.join(lines)


# --- Wiki全体構造バリデーション ---

SCALE_GUIDELINES = {
    "small": {
        "label": "小規模 (3-5サービス)",
        "min_pages": 10,
        "max_pages": 18,
        "min_sections": 3,
        "max_sections": 5,
    },
    "medium": {
        "label": "中規模 (6-15サービス)",
        "min_pages": 18,
        "max_pages": 30,
        "min_sections": 4,
        "max_sections": 6,
    },
    "large": {
        "label": "大規模 (16サービス以上)",
        "min_pages": 30,
        "max_pages": 50,
        "min_sections": 5,
        "max_sections": 8,
    },
}

REQUIRED_SECTIONS = {
    1: "System Overview",
    2: "Service Communication",
    3: "Data Architecture",
    4: "Infrastructure & Deployment",
}


def validate_wiki_structure(results: list, scale: Optional[str] = None) -> dict:
    """Wiki全体の構造を検証"""
    page_count = len([r for r in results if os.path.basename(r.file) != 'index.md'])

    if scale is None:
        if page_count <= 18:
            scale = "small"
        elif page_count <= 30:
            scale = "medium"
        else:
            scale = "large"

    guide = SCALE_GUIDELINES[scale]
    issues = []
    passes = []
    score = 0
    max_score = 0

    # ページ数チェック
    max_score += 20
    min_p, max_p = guide['min_pages'], guide['max_pages']
    if min_p <= page_count <= max_p:
        score += 20
        passes.append(f"✅ ページ数: {page_count} ({guide['label']}: {min_p}-{max_p}ページ)")
    elif page_count > max_p:
        score += 15
        issues.append(f"⚠️  ページ数が多い: {page_count} ({min_p}-{max_p}ページ)")
    elif page_count >= min_p * 0.7:
        score += 10
        issues.append(f"⚠️  ページ数がやや少ない: {page_count} ({min_p}ページ以上推奨)")
    else:
        issues.append(f"❌ ページ数不足: {page_count} ({min_p}ページ以上必要)")

    # 必須セクション確認
    max_score += 30
    sections_found = set()
    for r in results:
        basename = os.path.basename(r.file)
        m = re.match(r'^(\d+)', basename)
        if m:
            sections_found.add(int(m.group(1)))

    missing = []
    for sec_num, sec_name in REQUIRED_SECTIONS.items():
        if sec_num not in sections_found:
            missing.append(f"Section {sec_num} ({sec_name})")

    if not missing:
        score += 30
        passes.append(f"✅ 必須セクション: 全て存在")
    else:
        score += int(30 * (len(REQUIRED_SECTIONS) - len(missing)) / len(REQUIRED_SECTIONS))
        for m_item in missing:
            issues.append(f"❌ 必須セクション欠落: {m_item}")

    # Grade B以上の比率チェック
    max_score += 20
    grade_b_plus = sum(1 for r in results if r.grade in ('A', 'B')
                       and os.path.basename(r.file) != 'index.md')
    b_ratio = grade_b_plus / page_count if page_count > 0 else 0
    if b_ratio >= 0.80:
        score += 20
        passes.append(f"✅ Grade B以上: {grade_b_plus}/{page_count} ({b_ratio:.0%})")
    elif b_ratio >= 0.60:
        score += 12
        issues.append(f"⚠️  Grade B以上の比率が低い: {grade_b_plus}/{page_count} ({b_ratio:.0%}, 目標: 80%)")
    else:
        issues.append(f"❌ Grade B以上の比率が不足: {grade_b_plus}/{page_count} ({b_ratio:.0%})")

    return {
        "scale": scale,
        "page_count": page_count,
        "score": score,
        "max_score": max_score,
        "issues": issues,
        "passes": passes,
        "sections_found": sorted(sections_found),
    }


def main():
    import argparse

    parser = argparse.ArgumentParser(description='microservices-wiki ページ品質バリデーター')
    parser.add_argument('target', help='検証するMarkdownファイルまたはディレクトリ')
    parser.add_argument('--importance', choices=['high', 'medium', 'low', 'index'],
                        help='ページの重要度')
    parser.add_argument('--scale', choices=['small', 'medium', 'large'],
                        help='Wikiの規模 (ディレクトリ指定時のみ)')
    args = parser.parse_args()

    target = Path(args.target)

    if target.is_file():
        # 単一ページの検証
        result = validate_page(str(target), args.importance)
        print(format_result(result))

        grade_d_f = result.grade in ('D', 'F')
        sys.exit(1 if grade_d_f else 0)

    elif target.is_dir():
        # ディレクトリ全体の検証
        md_files = sorted(target.glob('*.md'))
        if not md_files:
            print(f"ERROR: Markdownファイルが見つかりません: {target}")
            sys.exit(1)

        results = []
        for md_file in md_files:
            result = validate_page(str(md_file))
            print(format_result(result))
            results.append(result)

        print(format_summary(results))

        # 構造チェック
        ws = validate_wiki_structure(results, args.scale)
        print(f"\n{'='*60}")
        print(f"  📊 Wiki 構造チェック (規模: {SCALE_GUIDELINES[ws['scale']]['label']})")
        print(f"{'='*60}")
        print(f"  スコア: {ws['score']}/{ws['max_score']} ({ws['score']/ws['max_score']*100:.0f}%)")
        print(f"  検出されたセクション: {ws['sections_found']}")
        print("")
        if ws['passes']:
            print("  合格項目:")
            for p in ws['passes']:
                print(f"    {p}")
        if ws['issues']:
            print("  改善が必要:")
            for i in ws['issues']:
                print(f"    {i}")
        print("")

        failing = sum(1 for r in results if r.grade in ('D', 'F'))
        sys.exit(1 if failing > 0 else 0)

    else:
        print(f"ERROR: ファイルまたはディレクトリが存在しません: {target}")
        sys.exit(1)


if __name__ == '__main__':
    main()
