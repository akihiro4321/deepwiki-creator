#!/usr/bin/env python3
import sys
import os
import re
import ast
import json
from pathlib import Path
from typing import Dict, List, Any

def extract_python_signatures(filepath: Path) -> List[Dict[str, Any]]:
    signatures = []
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        tree = ast.parse(content)
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                docstring = ast.get_docstring(node)
                signatures.append({
                    "type": "class",
                    "name": node.name,
                    "line": node.lineno,
                    "docstring": docstring.strip() if docstring else ""
                })
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Ignore private/magic methods unless it's __init__
                if node.name.startswith('_') and node.name != '__init__':
                    continue
                    
                docstring = ast.get_docstring(node)
                args = [arg.arg for arg in node.args.args]
                if node.args.vararg:
                    args.append(f"*{node.args.vararg.arg}")
                if node.args.kwarg:
                    args.append(f"**{node.args.kwarg.arg}")
                
                returns = ""
                if node.returns:
                    if isinstance(node.returns, ast.Name):
                        returns = node.returns.id
                    elif isinstance(node.returns, ast.Constant):
                        returns = str(node.returns.value)
                    else:
                        returns = "Any" # Fallback for complex annotations

                signatures.append({
                    "type": "function",
                    "name": node.name,
                    "args": ", ".join(args),
                    "returns": returns,
                    "line": node.lineno,
                    "docstring": docstring.strip() if docstring else ""
                })
    except Exception as e:
        print(f"Warning: Failed to parse Python file {filepath}: {e}", file=sys.stderr)
    return signatures

def extract_js_ts_signatures(filepath: Path) -> List[Dict[str, Any]]:
    signatures = []
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            content = "".join(lines)
            
        # Very basic regex for class and function exports in TS/JS
        # Since we don't have a full AST parser for TS in standard Python, 
        # we will extract exports with basic regex and attempt to capture JSDoc.
        
        # Match "export class ClassName" or "export default class ClassName"
        class_pattern = re.compile(r"(?:\/\*\*[\s\S]*?\*\/\s*)?(?:export\s+|default\s+)*class\s+(\w+)", re.MULTILINE)
        function_pattern = re.compile(r"(?:\/\*\*[\s\S]*?\*\/\s*)?(?:export\s+|default\s+)*(?:async\s+)?function\s+(\w+)\s*\(([^)]{0,500})\)", re.MULTILINE)
        arrow_function_pattern = re.compile(r"(?:\/\*\*[\s\S]*?\*\/\s*)?(?:export\s+|default\s+)*(?:const|let|var)\s+(\w+)(?:\s*:\s*[^=]+)?\s*=\s*(?:async\s+)?\(([^)]{0,500})\)\s*(?::\s*[^=]+)?\s*=>", re.MULTILINE)

        for match in class_pattern.finditer(content):
            doc_candidate = match.group(0)
            docstring = ""
            if "/**" in doc_candidate:
                docstring = doc_candidate[:doc_candidate.find("export")].strip()
            
            # Find line number (approximate)
            line_no = content[:match.end()].count('\n') + 1
            
            signatures.append({
                "type": "class",
                "name": match.group(1),
                "line": line_no,
                "docstring": docstring
            })

        for match in function_pattern.finditer(content):
            doc_candidate = match.group(0)
            docstring = ""
            if "/**" in doc_candidate:
                docstring = doc_candidate[:doc_candidate.find("export")].strip()
                
            name = match.group(1)
            args = match.group(2) or ""
            
            line_no = content[:match.end()].count('\n') + 1
            
            signatures.append({
                "type": "function",
                "name": name,
                "args": args.strip(),
                "returns": "",
                "line": line_no,
                "docstring": docstring
            })

        for match in arrow_function_pattern.finditer(content):
            doc_candidate = match.group(0)
            docstring = ""
            if "/**" in doc_candidate:
                docstring = doc_candidate[:doc_candidate.find("export")].strip()
                
            name = match.group(1)
            args = match.group(2) or ""
            
            line_no = content[:match.end()].count('\n') + 1
            
            signatures.append({
                "type": "function",
                "name": name,
                "args": args.strip(),
                "returns": "",
                "line": line_no,
                "docstring": docstring
            })
    except Exception as e:
        print(f"Warning: Failed to parse JS/TS file {filepath}: {e}", file=sys.stderr)
        
    # Sort by line number
    return sorted(signatures, key=lambda x: x["line"])

def extract_java_signatures(filepath: Path) -> List[Dict[str, Any]]:
    signatures = []
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Match "class ClassName" or "interface InterfaceName"
        class_pattern = re.compile(r"(?:\/\*\*[\s\S]*?\*\/\s*)?(?:public\s+|protected\s+|private\s+)?(?:abstract\s+)?(?:class|interface|enum)\s+(\w+)", re.MULTILINE)
        
        # Match method signatures: public Type methodName(Args)
        # Assuming typical Java formatting
        method_pattern = re.compile(r"(?:\/\*\*[\s\S]*?\*\/\s*)?(?:public\s+|protected\s+|private\s+)?(?:static\s+)?(?:final\s+)?([\w<>,\[\]]+)\s+(\w+)\s*\((.*?)\)\s*(?:throws\s+[\w,\s]+)?\s*[{;]", re.MULTILINE)

        for match in class_pattern.finditer(content):
            doc_candidate = match.group(0)
            docstring = ""
            if "/**" in doc_candidate:
                # Extract up to the end of the doc block
                doc_end = doc_candidate.rfind("*/") + 2
                docstring = doc_candidate[:doc_end].strip()
            
            line_no = content[:match.end()].count('\n') + 1
            
            signatures.append({
                "type": "class",
                "name": match.group(1),
                "line": line_no,
                "docstring": docstring
            })

        for match in method_pattern.finditer(content):
            doc_candidate = match.group(0)
            docstring = ""
            if "/**" in doc_candidate:
                doc_end = doc_candidate.rfind("*/") + 2
                docstring = doc_candidate[:doc_end].strip()
                
            ret_type = match.group(1).strip()
            name = match.group(2).strip()
            args = match.group(3).strip()
            
            # Skip invalid method names / return types that are actually keywords
            if ret_type in ["new", "return", "throw", "if", "while", "for", "catch", "switch", "else", "try", "synchronized", "this", "super"]:
                continue
            
            # Skip constructors (where return type is missing and it looks like a class name, but handled vaguely here)
            # Actually, standard methods have return types.
            
            line_no = content[:match.end()].count('\n') + 1
            
            signatures.append({
                "type": "method",
                "name": name,
                "returns": ret_type,
                "args": args,
                "line": line_no,
                "docstring": docstring
            })

    except Exception as e:
        print(f"Warning: Failed to parse Java file {filepath}: {e}", file=sys.stderr)
        
    return sorted(signatures, key=lambda x: x["line"])

def main():
    if len(sys.argv) < 2:
        print("Usage: python extract_signatures.py <target_directory> [--json]", file=sys.stderr)
        sys.exit(1)
        
    target_dir = Path(sys.argv[1]).resolve()
    output_json = len(sys.argv) > 2 and sys.argv[2] == '--json'
    
    if not target_dir.exists() or not target_dir.is_dir():
        print(f"Error: Directory {target_dir} does not exist.", file=sys.stderr)
        sys.exit(1)

    result_map: Dict[str, List[Dict[str, Any]]] = {}

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
            
            sigs = []
            if file.endswith('.py'):
                sigs = extract_python_signatures(filepath)
            elif file.endswith(('.js', '.jsx', '.ts', '.tsx', '.vue')):
                sigs = extract_js_ts_signatures(filepath)
            elif file.endswith('.java'):
                sigs = extract_java_signatures(filepath)
            else:
                continue
                
            if sigs:
                result_map[rel_path] = sigs

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
                
                if sig_type == "class":
                    print(f"- **Class**: `{name}` (L{line})")
                else:
                    ret_str = f" -> {returns}" if returns else ""
                    print(f"- **{sig_type.capitalize()}**: `{name}({args}){ret_str}` (L{line})")
                
                if docstring:
                    # Print first line of docstring
                    first_line = docstring.split('\n')[0].replace('/**', '').replace('*/', '').replace('"""', '').strip()
                    if first_line:
                        print(f"  - *Doc*: {first_line[:100]}...")
            print()

if __name__ == '__main__':
    main()
