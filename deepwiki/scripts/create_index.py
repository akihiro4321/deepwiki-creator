#!/usr/bin/env python3
import sys
import json
import os
from pathlib import Path
from collections import defaultdict

STATUS_BADGE = {
    "done": "✅",
    "pending": "⏳",
    "error": "❌",
}
IMPORTANCE_BADGE = {
    "high": "⭐",
    "medium": "",
    "low": "",
}

def group_pages_by_section(pages):
    """ページをセクション番号でグループ化して返す。"""
    sections = defaultdict(list)
    for page in pages:
        page_id = page.get("id", "")
        section_prefix = page_id.split('.')[0] if "." in page_id else page_id
        sections[section_prefix].append(page)
    return sections

def get_reading_order(pages):
    """importance: high のページを先頭に、推奨読書順を返す。"""
    high = [p for p in pages if p.get("importance") == "high"]
    others = [p for p in pages if p.get("importance") != "high"]
    return high + others

def create_index(outline_path: str):
    outline_file = Path(outline_path)
    if not outline_file.exists():
        print(f"Error: {outline_path} not found.")
        sys.exit(1)

    with open(outline_file, 'r', encoding='utf-8') as f:
        outline = json.load(f)

    output_dir = Path(outline.get("outputDir", outline_file.parent))
    target_dir = outline.get("targetDir", "プロジェクト")
    pages = outline.get("pages", [])
    generated_at = outline.get("generatedAt", "")

    # 統計集計
    total = len(pages)
    done_count = sum(1 for p in pages if p.get("status") == "done")
    error_count = sum(1 for p in pages if p.get("status") == "error")
    high_count = sum(1 for p in pages if p.get("importance") == "high")

    index_path = output_dir / "index.md"

    with open(index_path, 'w', encoding='utf-8') as f:
        # ヘッダー
        f.write(f"# {outline.get('title', 'プロジェクト Wiki')}\n\n")
        f.write(f"対象プロジェクト: `{target_dir}`\n\n")

        # 概要・統計
        f.write("## 概要\n\n")
        f.write(f"| 項目 | 値 |\n")
        f.write(f"| :--- | :--- |\n")
        f.write(f"| 総ページ数 | {total} |\n")
        f.write(f"| 生成済み | {done_count} / {total} |\n")
        if error_count > 0:
            f.write(f"| エラー | {error_count} |\n")
        f.write(f"| 重要ページ (high) | {high_count} |\n")
        if generated_at:
            f.write(f"| 生成日時 | {generated_at} |\n")
        f.write("\n")

        # 推奨読書順（high ページのみ）
        high_pages = [p for p in pages if p.get("importance") == "high"]
        if high_pages:
            f.write("## はじめに読むページ（重要度: high）\n\n")
            for page in high_pages:
                page_id = page.get("id", "")
                title = page.get("title", "No Title")
                filename = page.get("filename", f"{page_id}.md")
                status = STATUS_BADGE.get(page.get("status", "pending"), "⏳")
                f.write(f"- {status} **[{page_id} {title}](./{filename})**\n")
            f.write("\n")

        # 目次（全ページ、セクション別）
        f.write("## 目次\n\n")
        sections = group_pages_by_section(pages)

        for section_prefix in sorted(sections.keys(), key=lambda x: int(x) if x.isdigit() else x):
            section_pages = sections[section_prefix]
            f.write(f"### Section {section_prefix}\n")
            for page in section_pages:
                page_id = page.get("id", "")
                title = page.get("title", "No Title")
                filename = page.get("filename", "")
                if not filename:
                    filename = f"{page_id}.md" if page_id else f"{title.replace(' ', '_').lower()}.md"

                description = page.get("description", "")
                status = STATUS_BADGE.get(page.get("status", "pending"), "⏳")
                importance_badge = IMPORTANCE_BADGE.get(page.get("importance", "medium"), "")
                badge_str = f" {importance_badge}" if importance_badge else ""

                f.write(f"- {status}{badge_str} **[{page_id} {title}](./{filename})**\n")
                if description:
                    f.write(f"  - {description}\n")
            f.write("\n")

        f.write("---\n*このインデックスは `create_index.py` によって自動生成されました。*\n")

    print(f"✅ Created index page at {index_path}")

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python create_index.py <path_to_outline.json>")
        sys.exit(1)

    create_index(sys.argv[1])
