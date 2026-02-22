#!/usr/bin/env python3
import sys
import json
import os
from pathlib import Path

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

    index_path = output_dir / "index.md"
    
    with open(index_path, 'w', encoding='utf-8') as f:
        f.write(f"# {outline.get('title', 'プロジェクト Wiki')}\n\n")
        f.write(f"対象プロジェクト: `{target_dir}`\n\n")
        
        f.write("## 目次\n\n")
        
        # セクションごとにグループ化して表示する簡単なロジック
        current_section = ""
        for page in pages:
            # page_idからセクション番号を抽出 (例: "1.1" -> "1")
            page_id = page.get("id", "")
            if "." in page_id:
                section_prefix = page_id.split('.')[0]
                if section_prefix != current_section:
                    current_section = section_prefix
                    f.write(f"### Section {current_section}\n")
            
            title = page.get("title", "No Title")
            filename = page.get("filename", "")
            if not filename:
                filename = f"{page_id}.md" if page_id else f"{title.replace(' ', '_').lower()}.md"
                
            description = page.get("description", "")
            
            f.write(f"- **[{page_id} {title}](./{filename})**\n")
            if description:
                f.write(f"  - {description}\n")
                
        f.write("\n---\n*このインデックスは `create_index.py` によって自動生成されました。*\n")

    print(f"✅ Created index page at {index_path}")

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python create_index.py <path_to_outline.json>")
        sys.exit(1)
        
    create_index(sys.argv[1])
