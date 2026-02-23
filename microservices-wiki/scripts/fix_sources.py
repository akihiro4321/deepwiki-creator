#!/usr/bin/env python3
"""
全WikiページのSources行にある file:/// リンクを指定形式に変換するスクリプト。

使用方法:
    # GitHub/GitLab URL形式（リモートURLを自動取得）
    python3 scripts/fix_sources.py $OUTPUT_DIR/outline.json --link-style github

    # GitHub/GitLab URL形式（URLを明示指定）
    python3 scripts/fix_sources.py $OUTPUT_DIR/outline.json --link-style github --remote-url https://github.com/org/repo

    # vscode:// 形式（ローカルのVSCodeで直接開く）
    python3 scripts/fix_sources.py $OUTPUT_DIR/outline.json --link-style vscode
"""
import os
import sys
import json
import re
import argparse
import subprocess
from typing import Optional, Tuple


def get_git_remote_url(target_dir: str) -> Optional[str]:
    """git remote get-url origin でリモートURLを取得して HTTPS 形式に正規化する。"""
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            cwd=target_dir,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return None

        url = result.stdout.strip()
        if not url:
            return None

        # SSH形式を HTTPS に変換
        # git@github.com:org/repo.git → https://github.com/org/repo
        ssh_match = re.match(r"git@([^:]+):(.+?)(?:\.git)?$", url)
        if ssh_match:
            host = ssh_match.group(1)
            path = ssh_match.group(2)
            return f"https://{host}/{path}"

        # HTTPS 形式の .git を除去
        if url.endswith(".git"):
            url = url[:-4]

        return url
    except Exception:
        return None


def get_git_branch(target_dir: str) -> str:
    """現在のブランチ名を取得する。失敗した場合は 'main' を返す。"""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=target_dir,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            branch = result.stdout.strip()
            if branch and branch != "HEAD":
                return branch
    except Exception:
        pass
    return "main"


def build_github_url(remote_url: str, branch: str, rel_path: str, anchor: str) -> str:
    """GitHub / GitLab の blob URL を組み立てる。"""
    if "gitlab" in remote_url:
        # GitLab は /-/blob/ 形式
        return f"{remote_url}/-/blob/{branch}/{rel_path}{anchor}"
    else:
        # GitHub / Gitea / その他
        return f"{remote_url}/blob/{branch}/{rel_path}{anchor}"


def build_vscode_url(abs_path: str, start_line: Optional[str]) -> str:
    """vscode://file/ 形式の URL を組み立てる。行番号はジャンプ先の開始行のみ使用。"""
    line_suffix = f":{start_line}" if start_line else ""
    return f"vscode://file/{abs_path}{line_suffix}"


def convert_links_github(
    content: str, target_dir: str, remote_url: str, branch: str
) -> Tuple[str, int]:
    """file:/// リンクを GitHub/GitLab URL に変換する。"""
    target_dir = target_dir.rstrip("/")
    count = 0

    def replace(m: re.Match) -> str:
        nonlocal count
        abs_path = m.group(1)
        anchor = m.group(2) or ""

        if abs_path.startswith(target_dir + "/"):
            rel_path = abs_path[len(target_dir) + 1:]
        elif abs_path.startswith(target_dir):
            rel_path = abs_path[len(target_dir):].lstrip("/")
        else:
            return m.group(0)

        count += 1
        return f"({build_github_url(remote_url, branch, rel_path, anchor)})"

    # file:// の後の / をパスの先頭として含める → group(1) が /absolute/path 形式になる
    pattern = r"\(file://(/[^#)\s]+)(#L[\d\-L]+)?\)"
    return re.sub(pattern, replace, content), count


def convert_links_vscode(content: str) -> Tuple[str, int]:
    """file:/// リンクを vscode://file/ 形式に変換する。"""
    count = 0

    def replace(m: re.Match) -> str:
        nonlocal count
        abs_path = m.group(1)
        anchor = m.group(2) or ""

        # #L100-L200 から開始行番号を抽出
        start_line = None
        if anchor:
            line_match = re.search(r"L(\d+)", anchor)
            if line_match:
                start_line = line_match.group(1)

        count += 1
        return f"({build_vscode_url(abs_path, start_line)})"

    # file:// の後の / をパスの先頭として含める → group(1) が /absolute/path 形式になる
    pattern = r"\(file://(/[^#)\s]+)(#L[\d\-L]+)?\)"
    return re.sub(pattern, replace, content), count


def process_file(
    file_path: str,
    link_style: str,
    target_dir: str,
    remote_url: Optional[str],
    branch: Optional[str],
) -> Tuple[bool, int]:
    """単一ファイルのリンクを変換して上書き保存する。"""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        print(f"    [Error] Could not read: {e}")
        return False, 0

    if "file:///" not in content:
        return False, 0

    if link_style == "github":
        new_content, count = convert_links_github(content, target_dir, remote_url, branch)
    else:  # vscode
        new_content, count = convert_links_vscode(content)

    if count == 0:
        return False, 0

    try:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(new_content)
    except Exception as e:
        print(f"    [Error] Could not write: {e}")
        return False, 0

    return True, count


def scan_and_fix(outline_path: str, link_style: str, remote_url_arg: Optional[str]) -> None:
    """outline.json の全 done ページを走査してリンクを変換する。"""
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

    remote_url = None
    branch = None

    if link_style == "github":
        # リモートURL の解決（引数 → git remote → outline.json の順）
        if remote_url_arg:
            remote_url = remote_url_arg
            source = "--remote-url 引数"
        else:
            remote_url = get_git_remote_url(target_dir)
            source = "git remote"
            if not remote_url:
                remote_url = outline_data.get("remoteBaseUrl")
                source = "outline.json の remoteBaseUrl"

        if not remote_url:
            print("  ❌ リモートURL が取得できませんでした。")
            print("     以下のいずれかで対処してください:")
            print("       --remote-url https://github.com/org/repo  を引数に追加する")
            print("       outline.json に \"remoteBaseUrl\": \"https://...\" を追加する")
            sys.exit(1)

        branch = get_git_branch(target_dir)
        print(f"  Remote URL : {remote_url}  (取得元: {source})")
        print(f"  Branch     : {branch}")
        print(f"  Style      : github → {build_github_url(remote_url, branch, 'path/file.ts', '#L1-L10')}")
    else:
        print(f"  Style      : vscode → vscode://file//absolute/path.ts:LINE")

    print(f"\nScanning {len(done_pages)} pages...\n")

    total_converted = 0
    changed_files = 0

    for page in done_pages:
        page_id = page.get("id", "?")
        filename = page.get("filename")
        if not filename:
            continue

        file_path = os.path.join(output_dir, filename)
        if not os.path.exists(file_path):
            print(f"  [{page_id}] ⚠️  File not found: {filename}")
            continue

        changed, count = process_file(file_path, link_style, target_dir, remote_url, branch)

        if not changed:
            print(f"  [{page_id}] -  No file:/// links.")
        else:
            print(f"  [{page_id}] ✅ {count} link(s) converted.")
            total_converted += count
            changed_files += 1

    print(f"\n{'=' * 50}")
    print(f"Sources link conversion complete.")
    print(f"  Files modified  : {changed_files}")
    print(f"  Links converted : {total_converted}")


def main() -> None:
    parser = argparse.ArgumentParser(description="DeepWiki Sources link converter")
    parser.add_argument("outline_json", help="Path to the outline.json file")
    parser.add_argument(
        "--link-style",
        choices=["github", "vscode"],
        required=True,
        help="変換後のリンク形式: github（GitHub/GitLab URL）または vscode（vscode:// URL）",
    )
    parser.add_argument(
        "--remote-url",
        help="GitHub/GitLab のリポジトリベースURL（例: https://github.com/org/repo）。"
             "省略時は git remote から自動取得する。--link-style github 時のみ使用。",
    )
    args = parser.parse_args()

    outline_path = os.path.abspath(args.outline_json)
    if not os.path.exists(outline_path):
        print(f"Error: outline.json not found at {outline_path}")
        sys.exit(1)

    scan_and_fix(outline_path, args.link_style, args.remote_url)


if __name__ == "__main__":
    main()
