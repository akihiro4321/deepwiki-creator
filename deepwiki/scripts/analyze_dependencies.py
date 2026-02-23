#!/usr/bin/env python3
import sys
import os
import re
import ast
import json
from pathlib import Path
from typing import Dict, List, Set, Any

def analyze_python_dependencies(filepath: Path) -> Set[str]:
    dependencies = set()
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        tree = ast.parse(content)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    dependencies.add(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    # module might be something like 'os.path', we now retain the full path
                    dependencies.add(node.module)
    except Exception as e:
        print(f"Warning: Failed to parse Python file {filepath}: {e}", file=sys.stderr)
    return dependencies

def analyze_js_ts_dependencies(filepath: Path) -> Set[str]:
    dependencies = set()
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Pattern for ES6 imports: import ... from '...'
        import_pattern = re.compile(r"import\s+(?:(?:.+?)\s+from\s+)?['\"]([^'\"]+)['\"]", re.MULTILINE)
        # Pattern for dynamic imports: import('...')
        dynamic_import_pattern = re.compile(r"import\s*\(\s*['\"]([^'\"]+)['\"]\s*\)", re.MULTILINE)
        # Pattern for require: require('...')
        require_pattern = re.compile(r"require\s*\(\s*['\"]([^'\"]+)['\"]\s*\)", re.MULTILINE)
        # Pattern for export ... from '...'
        export_from_pattern = re.compile(r"export\s+.*?\s+from\s+['\"]([^'\"]+)['\"]", re.MULTILINE)
        
        for match in import_pattern.findall(content):
            dependencies.add(match)
        for match in dynamic_import_pattern.findall(content):
            dependencies.add(match)
        for match in require_pattern.findall(content):
            dependencies.add(match)
        for match in export_from_pattern.findall(content):
            dependencies.add(match)
            
    except Exception as e:
        print(f"Warning: Failed to parse JS/TS file {filepath}: {e}", file=sys.stderr)
    return dependencies

def analyze_java_dependencies(filepath: Path) -> Set[str]:
    dependencies = set()
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            
        import_pattern = re.compile(r"^\s*import\s+([\w\.]+)\s*;", re.MULTILINE)
        for match in import_pattern.findall(content):
            dependencies.add(match)
            
    except Exception as e:
        print(f"Warning: Failed to parse Java file {filepath}: {e}", file=sys.stderr)
    return dependencies

def main():
    if len(sys.argv) < 2:
        print("Usage: python analyze_dependencies.py <target_directory> [--json]", file=sys.stderr)
        sys.exit(1)
        
    target_dir = Path(sys.argv[1]).resolve()
    output_json = len(sys.argv) > 2 and sys.argv[2] == '--json'
    
    if not target_dir.exists() or not target_dir.is_dir():
        print(f"Error: Directory {target_dir} does not exist.", file=sys.stderr)
        sys.exit(1)

    result_map: Dict[str, Dict[str, List[str]]] = {}
    
    # Track which files are imported by which (reverse dependency map)
    imported_by: Dict[str, Set[str]] = {}

    for root, dirs, files in os.walk(target_dir):
        # Skip common ignored directories
        dirs[:] = [d for d in dirs if d not in (
            '.git', 'node_modules', '__pycache__', '.next', '.nuxt', 'dist', 'build', 'out',
            '.cache', '.tmp', '.temp', 'vendor', '.venv', 'venv', 'env', '.env',
            '.idea', '.vscode', '.DS_Store', 'coverage', '.nyc_output',
            '.terraform', '.serverless', '.aws-sam',
            'target',  # Rust/Java
            'Pods',    # iOS
            '.run',
        )]
        
        for file in files:
            filepath = Path(root) / file
            rel_path = str(filepath.relative_to(target_dir))
            
            # 巨大なファイルやバンドル済みのファイルは解析スキップ
            if file.endswith('.min.js') or file.endswith('.bundle.js') or 'bundle' in filepath.parts:
                continue
            if filepath.exists() and filepath.stat().st_size > 500 * 1024:
                continue
            
            deps: Set[str] = set()
            if file.endswith('.py'):
                deps = analyze_python_dependencies(filepath)
            elif file.endswith(('.js', '.jsx', '.ts', '.tsx', '.vue')):
                deps = analyze_js_ts_dependencies(filepath)
            elif file.endswith('.java'):
                deps = analyze_java_dependencies(filepath)
            else:
                continue
                
            sorted_deps = sorted(list(deps))
            if rel_path not in result_map:
                result_map[rel_path] = {"imports": [], "imported_by": []}
            result_map[rel_path]["imports"] = sorted_deps
            
            for dep in sorted_deps:
                if dep not in imported_by:
                    imported_by[dep] = set()
                imported_by[dep].add(rel_path)

    # Precompute normalized dependencies
    precomputed_deps = []
    for dep_target, importers in imported_by.items():
        precomputed_deps.append({
            "dep_target": dep_target,
            "normalized_dep": dep_target.replace('.', '/'),
            "importers": importers
        })

    # Populate imported_by for local files
    for filepath_str in result_map.keys():
        matched_importers = set()
        file_stem = Path(filepath_str).stem
        normalized_path = re.sub(r'\.(ts|tsx|js|jsx|py|java)$', '', filepath_str)
        for dep_info in precomputed_deps:
            dep_target = dep_info["dep_target"]
            normalized_dep = dep_info["normalized_dep"]
            importers = dep_info["importers"]
            
            if (
                dep_target == file_stem or 
                dep_target == filepath_str or
                normalized_dep == normalized_path or
                normalized_dep.startswith(normalized_path + '/') or
                normalized_dep.endswith('/' + file_stem) or
                normalized_path.endswith('/' + normalized_dep)
            ):
                matched_importers.update(importers)
        
        result_map[filepath_str]["imported_by"] = sorted(list(matched_importers))

    if output_json:
        print(json.dumps(result_map, indent=2, ensure_ascii=False))
    else:
        print("# 依存関係マップ (Dependency Map)\n")
        for file, data in result_map.items():
            if not data["imports"] and not data["imported_by"]:
                continue
            print(f"### `{file}`")
            if data["imports"]:
                print("**Imports:**")
                for dep in data["imports"]:
                    print(f"- `{dep}`")
            if data["imported_by"]:
                print("**Imported By (推測):**")
                for importer in data["imported_by"]:
                    print(f"- `{importer}`")
            print()

if __name__ == '__main__':
    main()
