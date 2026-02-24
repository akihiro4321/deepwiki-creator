#!/usr/bin/env python3
import sys
import os
import ast
import json
import subprocess
from pathlib import Path
from typing import Dict, List, Any, Optional

try:
    import tree_sitter
    import tree_sitter_javascript
    import tree_sitter_typescript
    import tree_sitter_java
    
    TS_LANG = tree_sitter.Language(tree_sitter_typescript.language_typescript(), "typescript")
    JS_LANG = tree_sitter.Language(tree_sitter_javascript.language(), "javascript")
    JAVA_LANG = tree_sitter.Language(tree_sitter_java.language(), "java")
    
    HAS_TREE_SITTER = True
except ImportError:
    HAS_TREE_SITTER = False

def extract_python_signatures(filepath: Path) -> List[Dict[str, Any]]:
    signatures = []
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        tree = ast.parse(content)
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                docstring = ast.get_docstring(node)
                decorators = [('@' + (n.id if isinstance(n, ast.Name) else getattr(n, 'func', n).id)) for n in node.decorator_list if hasattr(n, 'id') or hasattr(getattr(n, 'func', n), 'id')]
                signatures.append({
                    "type": "class",
                    "name": node.name,
                    "line": node.lineno,
                    "docstring": docstring.strip() if docstring else "",
                    "decorators": decorators
                })
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name.startswith('_') and node.name != '__init__':
                    continue
                    
                docstring = ast.get_docstring(node)
                decorators = []
                for n in node.decorator_list:
                    if isinstance(n, ast.Name):
                        decorators.append('@' + n.id)
                    elif isinstance(n, ast.Call) and isinstance(n.func, ast.Name):
                        decorators.append('@' + n.func.id + '(...)')
                
                args = [arg.arg for arg in node.args.args]
                if node.args.vararg:
                    args.append(f"*{node.args.vararg.arg}")
                if node.args.kwarg:
                    args.append(f"**{node.args.kwarg.arg}")
                
                returns = ""
                if node.returns:
                    if isinstance(node.returns, ast.Name):
                        returns = node.returns.id
                    elif hasattr(node.returns, 'value'):
                        returns = str(node.returns.value)
                    else:
                        returns = "Any"

                signatures.append({
                    "type": "function",
                    "name": node.name,
                    "args": ", ".join(args),
                    "returns": returns,
                    "line": node.lineno,
                    "docstring": docstring.strip() if docstring else "",
                    "decorators": decorators
                })
    except Exception as e:
        print(f"Warning: Failed to parse Python file {filepath}: {e}", file=sys.stderr)
    return signatures

def extract_node_text(node, source_code: bytes) -> str:
    if node is None: return ""
    return source_code[node.start_byte:node.end_byte].decode('utf-8')

def find_children_by_type(node, type_name: str):
    return [n for n in node.children if n.type == type_name]

def get_ts_decorators(node, source_code: bytes):
    decorators = []
    for child in node.children:
        if child.type == 'decorator':
            decorators.append(extract_node_text(child, source_code))
            
    curr = node.prev_named_sibling
    while curr and curr.type == 'decorator':
        decorators.insert(0, extract_node_text(curr, source_code))
        curr = curr.prev_named_sibling
        
    if node.parent and node.parent.type == 'export_statement':
        curr = node.parent.prev_named_sibling
        while curr and curr.type == 'decorator':
            decorators.insert(0, extract_node_text(curr, source_code))
            curr = curr.prev_named_sibling
            
    return decorators

def get_ts_docstring(node, source_code: bytes):
    curr = node.prev_named_sibling
    while curr and curr.type == 'decorator':
        curr = curr.prev_named_sibling
    if curr and curr.type == 'comment':
        text = extract_node_text(curr, source_code)
        if text.startswith('/**'):
            return text.strip()
            
    if node.parent and node.parent.type == 'export_statement':
        curr = node.parent.prev_named_sibling
        while curr and curr.type == 'decorator':
            curr = curr.prev_named_sibling
        if curr and curr.type == 'comment':
            text = extract_node_text(curr, source_code)
            if text.startswith('/**'):
                return text.strip()
    return ""

def extract_js_ts_signatures(filepath: Path, lang) -> List[Dict[str, Any]]:
    signatures = []
    try:
        with open(filepath, 'rb') as f:
            source_code = f.read()
            
        parser = tree_sitter.Parser()
        parser.set_language(lang)
        tree = parser.parse(source_code)
        
        def walk(node):
            if node.type in ('class_declaration', 'function_declaration', 'method_definition', 'lexical_declaration'):
                if node.type == 'lexical_declaration':
                    # Check for exported arrow functions
                    if node.parent and node.parent.type == 'export_statement':
                        for dec in find_children_by_type(node, 'variable_declarator'):
                            value = dec.child_by_field_name('value')
                            if value and value.type == 'arrow_function':
                                name_node = dec.child_by_field_name('name')
                                params_node = value.child_by_field_name('parameters')
                                return_type_node = value.child_by_field_name('return_type')
                                signatures.append({
                                    "type": "function",
                                    "name": extract_node_text(name_node, source_code) if name_node else "",
                                    "args": extract_node_text(params_node, source_code) if params_node else "()",
                                    "returns": extract_node_text(return_type_node, source_code) if return_type_node else "Any",
                                    "line": node.start_point[0] + 1,
                                    "decorators": get_ts_decorators(node, source_code),
                                    "docstring": get_ts_docstring(node, source_code)
                                })
                else:
                    name_node = node.child_by_field_name('name')
                    # allow empty name for default exports, except methods must have names
                    name_text = extract_node_text(name_node, source_code) if name_node else ("default" if node.type != 'method_definition' else "")
                    
                    if name_text and name_text != 'constructor':
                        if node.type == 'class_declaration':
                            signatures.append({
                                "type": "class",
                                "name": name_text,
                                "line": node.start_point[0] + 1,
                                "decorators": get_ts_decorators(node, source_code),
                                "docstring": get_ts_docstring(node, source_code)
                            })
                        else:
                            params_node = node.child_by_field_name('parameters')
                            return_type_node = node.child_by_field_name('return_type')
                            signatures.append({
                                "type": "function" if node.type == 'function_declaration' else "method",
                                "name": name_text,
                                "args": extract_node_text(params_node, source_code) if params_node else "()",
                                "returns": extract_node_text(return_type_node, source_code) if return_type_node else "Any",
                                "line": node.start_point[0] + 1,
                                "decorators": get_ts_decorators(node, source_code),
                                "docstring": get_ts_docstring(node, source_code)
                            })
            
            for child in node.children:
                walk(child)
                
        walk(tree.root_node)
    except Exception as e:
        print(f"Warning: Failed to parse JS/TS file {filepath}: {e}", file=sys.stderr)
        
    return sorted(signatures, key=lambda x: x["line"])

def extract_java_signatures(filepath: Path) -> List[Dict[str, Any]]:
    signatures = []
    try:
        with open(filepath, 'rb') as f:
            source_code = f.read()
            
        parser = tree_sitter.Parser()
        parser.set_language(JAVA_LANG)
        tree = parser.parse(source_code)
        
        def walk(node):
            if node.type in ('class_declaration', 'interface_declaration', 'enum_declaration'):
                name_node = node.child_by_field_name('name')
                if name_node:
                    modifiers = next((c for c in node.children if c.type == 'modifiers'), None)
                    decorators = []
                    if modifiers:
                        for mod in modifiers.children:
                            if mod.type in ['annotation', 'marker_annotation']:
                                decorators.append(extract_node_text(mod, source_code))
                                
                    signatures.append({
                        "type": node.type.split('_')[0],
                        "name": extract_node_text(name_node, source_code),
                        "line": node.start_point[0] + 1,
                        "decorators": decorators,
                        "docstring": get_ts_docstring(node, source_code)
                    })
            elif node.type == 'method_declaration':
                name_node = node.child_by_field_name('name')
                if name_node:
                    modifiers = next((c for c in node.children if c.type == 'modifiers'), None)
                    decorators = []
                    if modifiers:
                        for mod in modifiers.children:
                            if mod.type in ['annotation', 'marker_annotation']:
                                decorators.append(extract_node_text(mod, source_code))
                                
                    params_node = node.child_by_field_name('parameters')
                    type_node = node.child_by_field_name('type')
                    
                    signatures.append({
                        "type": "method",
                        "name": extract_node_text(name_node, source_code),
                        "args": extract_node_text(params_node, source_code) if params_node else "()",
                        "returns": extract_node_text(type_node, source_code) if type_node else "void",
                        "line": node.start_point[0] + 1,
                        "decorators": decorators,
                        "docstring": get_ts_docstring(node, source_code)
                    })
            
            for child in node.children:
                walk(child)
                
        walk(tree.root_node)
    except Exception as e:
        print(f"Warning: Failed to parse Java file {filepath}: {e}", file=sys.stderr)
        
    return sorted(signatures, key=lambda x: x["line"])

def get_git_files(target_dir: Path) -> Optional[List[Path]]:
    """gitリポジトリなら git ls-files で .gitignore 考慮済みのファイルリストを返す。失敗時は None。"""
    try:
        result = subprocess.run(
            ['git', '-C', str(target_dir), 'ls-files', '--cached', '--others', '--exclude-standard'],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            return [target_dir / line for line in result.stdout.splitlines() if line]
    except Exception:
        pass
    return None


def main():
    if len(sys.argv) < 2:
        print("Usage: python extract_signatures.py <target_directory> [--json]", file=sys.stderr)
        sys.exit(1)
        
    if not HAS_TREE_SITTER:
        print("ERROR: tree-sitter packages are not installed.", file=sys.stderr)
        print("To enable robust parsing for JS, TS, React, and Java (Spring Boot), please run:", file=sys.stderr)
        print("    pip install tree-sitter==0.21.3 tree-sitter-javascript==0.21.4 tree-sitter-typescript==0.21.2 tree-sitter-java==0.21.0", file=sys.stderr)
        sys.exit(1)
        
    target_dir = Path(sys.argv[1]).resolve()
    output_json = len(sys.argv) > 2 and sys.argv[2] == '--json'
    
    if not target_dir.exists() or not target_dir.is_dir():
        print(f"Error: Directory {target_dir} does not exist.", file=sys.stderr)
        sys.exit(1)

    result_map: Dict[str, List[Dict[str, Any]]] = {}

    def process_file(filepath: Path) -> None:
        file = filepath.name
        rel_path = str(filepath.relative_to(target_dir))

        if file.endswith('.min.js') or file.endswith('.bundle.js') or 'bundle' in filepath.parts:
            return
        if not filepath.exists() or filepath.stat().st_size > 500 * 1024:
            return

        sigs = []
        if file.endswith('.py'):
            sigs = extract_python_signatures(filepath)
        elif file.endswith(('.js', '.jsx')):
            sigs = extract_js_ts_signatures(filepath, JS_LANG)
        elif file.endswith(('.ts', '.tsx', '.vue')):
            sigs = extract_js_ts_signatures(filepath, TS_LANG)
        elif file.endswith('.java'):
            sigs = extract_java_signatures(filepath)
        else:
            return

        if sigs:
            result_map[rel_path] = sigs

    git_files = get_git_files(target_dir)
    if git_files is not None:
        # gitモード: .gitignore 考慮済みのリストをイテレート
        for filepath in git_files:
            process_file(filepath)
    else:
        # フォールバック: os.walk + ハードコードリスト
        for root, dirs, files in os.walk(target_dir):
            dirs[:] = [d for d in dirs if d not in (
                '.git', 'node_modules', '__pycache__', '.next', '.nuxt', 'dist', 'build', 'out',
                '.cache', '.tmp', '.temp', 'vendor', '.venv', 'venv', 'env', '.env',
                '.idea', '.vscode', '.DS_Store', 'coverage', '.nyc_output',
                '.terraform', '.serverless', '.aws-sam',
                'target', 'Pods', '.run',
            )]
            for file in files:
                process_file(Path(root) / file)

    if output_json:
        print(json.dumps(result_map, indent=2, ensure_ascii=False))
    else:
        print("# エクスポート／主要シグネチャ (Signatures)\n")
        for filepath, signatures in result_map.items():
            print(f"### `{filepath}`")
            for sig in signatures:
                sig_type = sig.get("type", "")
                name = sig.get("name", "")
                line = sig.get("line", "")
                args = sig.get("args", "")
                returns = sig.get("returns", "")
                docstring = sig.get("docstring", "")
                decorators = sig.get("decorators", [])
                
                # Format decorators
                dec_str = " ".join(decorators) + " " if decorators else ""
                
                if sig_type == "class":
                    print(f"- **Class**: {dec_str}`{name}` (L{line})")
                else:
                    ret_str = f" -> {returns}" if returns else ""
                    print(f"- **{sig_type.capitalize()}**: {dec_str}`{name}({args}){ret_str}` (L{line})")
                
                if docstring:
                    first_line = docstring.split('\n')[0].replace('/**', '').replace('*/', '').replace('"""', '').strip()
                    if first_line:
                        print(f"  - *Doc*: {first_line[:100]}...")
            print()

if __name__ == '__main__':
    main()
