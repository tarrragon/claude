#!/usr/bin/env python3
"""
Markdown 連結檢查工具

檢查 Markdown 文件中的內部連結是否有效，預防 DOC-002 錯誤模式。

功能:
- 檢查相對路徑連結是否存在
- 支援錨點處理（忽略純錨點，檢查帶錨點的檔案連結）
- 支援目錄遞迴掃描
- 支援 JSON 輸出

使用方式:
    # 檢查單一文件
    python .claude/lib/markdown_link_checker.py docs/README.md

    # 檢查整個目錄
    python .claude/lib/markdown_link_checker.py --dir .claude/methodologies/

    # JSON 輸出
    python .claude/lib/markdown_link_checker.py --dir docs/ --json

    # 作為模組使用
    from markdown_link_checker import check_markdown_links, check_directory
    result = check_markdown_links("docs/README.md")
"""

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Optional, List, Dict, Tuple


@dataclass
class BrokenLink:
    """失效連結描述"""
    file: str
    line: int
    link_text: str
    link_target: str
    suggestion: str = ""


@dataclass
class LinkCheckResult:
    """單個檔案的連結檢查結果"""
    file_path: str
    total_links: int
    broken_links: List[BrokenLink] = field(default_factory=list)
    is_valid: bool = True

    def __post_init__(self):
        """計算 is_valid 狀態"""
        self.is_valid = len(self.broken_links) == 0


class MarkdownLinkChecker:
    """Markdown 連結檢查器"""

    # Markdown 連結正則表達式
    # 匹配 [text](target) 格式，排除圖片 ![alt](src)
    INLINE_LINK_PATTERN = re.compile(
        r'(?<!!)\[([^\]]+)\]\(([^)]+)\)'
    )

    # 引用式連結定義 [ref]: target
    REFERENCE_DEF_PATTERN = re.compile(
        r'^\s*\[([^\]]+)\]:\s*(.+)$',
        re.MULTILINE
    )

    # 引用式連結使用 [text][ref]
    REFERENCE_USE_PATTERN = re.compile(
        r'\[([^\]]+)\]\[([^\]]+)\]'
    )

    # 外部連結模式
    EXTERNAL_PATTERNS = [
        r'^https?://',
        r'^mailto:',
        r'^tel:',
        r'^ftp://',
    ]

    def __init__(self, project_root: Optional[str] = None):
        """
        初始化檢查器

        Args:
            project_root: 專案根目錄，預設從環境變數或當前目錄
        """
        if project_root is None:
            project_root = os.environ.get(
                "CLAUDE_PROJECT_DIR",
                os.getcwd()
            )
        self.project_root = Path(project_root)

    def check_file(self, file_path: str) -> LinkCheckResult:
        """
        檢查單個 Markdown 檔案的連結

        Args:
            file_path: Markdown 檔案路徑

        Returns:
            LinkCheckResult: 檢查結果
        """
        file_path = self._resolve_path(file_path)

        if not file_path.exists():
            return LinkCheckResult(
                file_path=str(file_path),
                total_links=0,
                broken_links=[
                    BrokenLink(
                        file=str(file_path),
                        line=0,
                        link_text="",
                        link_target="",
                        suggestion=f"檔案不存在: {file_path}"
                    )
                ]
            )

        try:
            content = file_path.read_text(encoding="utf-8")
        except Exception as e:
            return LinkCheckResult(
                file_path=str(file_path),
                total_links=0,
                broken_links=[
                    BrokenLink(
                        file=str(file_path),
                        line=0,
                        link_text="",
                        link_target="",
                        suggestion=f"無法讀取檔案: {e}"
                    )
                ]
            )

        # 解析所有連結
        links = self.parse_markdown_links(content)

        # 過濾出需要檢查的內部連結
        internal_links = self._filter_internal_links(links)

        # 檢查每個連結
        broken_links = []
        for link in internal_links:
            is_valid, suggestion = self._check_link(
                link["target"],
                file_path.parent
            )
            if not is_valid:
                broken_links.append(
                    BrokenLink(
                        file=str(file_path),
                        line=link["line"],
                        link_text=link["text"],
                        link_target=link["target"],
                        suggestion=suggestion
                    )
                )

        return LinkCheckResult(
            file_path=str(file_path),
            total_links=len(internal_links),
            broken_links=broken_links
        )

    def check_directory(
        self,
        dir_path: str,
        recursive: bool = True
    ) -> List[LinkCheckResult]:
        """
        檢查目錄下所有 Markdown 檔案

        Args:
            dir_path: 目錄路徑
            recursive: 是否遞迴檢查子目錄

        Returns:
            list[LinkCheckResult]: 所有檔案的檢查結果
        """
        dir_path = self._resolve_path(dir_path)

        if not dir_path.is_dir():
            return [
                LinkCheckResult(
                    file_path=str(dir_path),
                    total_links=0,
                    broken_links=[
                        BrokenLink(
                            file=str(dir_path),
                            line=0,
                            link_text="",
                            link_target="",
                            suggestion=f"目錄不存在: {dir_path}"
                        )
                    ]
                )
            ]

        # 收集所有 .md 檔案
        if recursive:
            md_files = sorted(dir_path.rglob("*.md"))
        else:
            md_files = sorted(dir_path.glob("*.md"))

        results = []
        for md_file in md_files:
            results.append(self.check_file(str(md_file)))

        return results

    def parse_markdown_links(self, content: str) -> List[Dict]:
        """
        解析 Markdown 內容中的所有連結

        Args:
            content: Markdown 內容

        Returns:
            list[dict]: 連結列表，每個包含 text, target, line
        """
        links = []
        lines = content.split('\n')

        # 首先收集引用式連結定義
        reference_defs = {}
        for match in self.REFERENCE_DEF_PATTERN.finditer(content):
            ref_name = match.group(1).lower()
            ref_target = match.group(2).strip()
            reference_defs[ref_name] = ref_target

        # 追蹤是否在程式碼區塊內
        in_code_block = False

        # 解析行內連結
        for line_num, line in enumerate(lines, start=1):
            # 檢查程式碼區塊開始/結束
            if line.strip().startswith("```"):
                in_code_block = not in_code_block
                continue

            # 跳過程式碼區塊內的連結
            if in_code_block:
                continue

            # 行內連結 [text](target)
            for match in self.INLINE_LINK_PATTERN.finditer(line):
                links.append({
                    "text": match.group(1),
                    "target": match.group(2),
                    "line": line_num
                })

            # 引用式連結 [text][ref]
            for match in self.REFERENCE_USE_PATTERN.finditer(line):
                ref_name = match.group(2).lower()
                if ref_name in reference_defs:
                    links.append({
                        "text": match.group(1),
                        "target": reference_defs[ref_name],
                        "line": line_num
                    })

        return links

    # ===== 私有方法 =====

    def _resolve_path(self, path: str) -> Path:
        """解析路徑為絕對路徑"""
        p = Path(path)
        if p.is_absolute():
            return p
        return self.project_root / p

    def _filter_internal_links(self, links: List[Dict]) -> List[Dict]:
        """
        過濾出需要檢查的內部連結

        排除:
        - 外部連結 (http://, https://, mailto:, etc.)
        - 純錨點連結 (#section)
        """
        internal_links = []

        for link in links:
            target = link["target"]

            # 跳過純錨點連結
            if target.startswith("#"):
                continue

            # 跳過外部連結
            if self._is_external_link(target):
                continue

            internal_links.append(link)

        return internal_links

    def _is_external_link(self, target: str) -> bool:
        """檢查是否為外部連結"""
        return any(
            re.match(pattern, target)
            for pattern in self.EXTERNAL_PATTERNS
        )

    def _check_link(
        self,
        target: str,
        base_dir: Path
    ) -> Tuple[bool, str]:
        """
        檢查單個連結是否有效

        Args:
            target: 連結目標
            base_dir: 基準目錄（連結所在檔案的目錄）

        Returns:
            tuple[bool, str]: (是否有效, 建議)
        """
        # 移除錨點後綴
        target_path = target.split("#")[0]

        # 如果移除錨點後為空，表示是純錨點連結
        if not target_path:
            return True, ""

        # 解析相對路徑
        resolved = (base_dir / target_path).resolve()

        if resolved.exists():
            return True, ""
        else:
            # 提供建議
            suggestion = f"檔案不存在: {target_path}"

            # 嘗試找到可能的替代檔案
            parent = resolved.parent
            if parent.exists():
                similar = self._find_similar_files(
                    resolved.name,
                    parent
                )
                if similar:
                    suggestion += f"\n可能是: {', '.join(similar[:3])}"

            return False, suggestion

    def _find_similar_files(
        self,
        filename: str,
        directory: Path
    ) -> List[str]:
        """尋找相似的檔案名稱"""
        if not directory.exists():
            return []

        # 取得目錄中的所有 .md 檔案
        existing_files = [f.name for f in directory.glob("*.md")]

        # 簡單的相似度比較（包含部分字串）
        base_name = Path(filename).stem.lower()
        similar = [
            f for f in existing_files
            if base_name in f.lower() or f.lower() in base_name
        ]

        return similar


# ===== 公開 API =====

def check_markdown_links(
    file_path: str,
    project_root: Optional[str] = None
) -> LinkCheckResult:
    """
    檢查單個 Markdown 檔案的連結

    Args:
        file_path: Markdown 檔案路徑
        project_root: 專案根目錄

    Returns:
        LinkCheckResult: 檢查結果

    Example:
        result = check_markdown_links("docs/README.md")
        if not result.is_valid:
            for link in result.broken_links:
                print(f"Line {link.line}: {link.link_target}")
    """
    checker = MarkdownLinkChecker(project_root)
    return checker.check_file(file_path)


def check_directory(
    dir_path: str,
    project_root: Optional[str] = None,
    recursive: bool = True
) -> Dict[str, List[BrokenLink]]:
    """
    檢查目錄下所有 Markdown 檔案的連結

    Args:
        dir_path: 目錄路徑
        project_root: 專案根目錄
        recursive: 是否遞迴檢查

    Returns:
        dict: 檔案路徑到失效連結列表的映射

    Example:
        broken = check_directory("docs/")
        for file_path, links in broken.items():
            print(f"{file_path}: {len(links)} broken links")
    """
    checker = MarkdownLinkChecker(project_root)
    results = checker.check_directory(dir_path, recursive)

    # 轉換為字典格式
    return {
        result.file_path: result.broken_links
        for result in results
        if result.broken_links  # 只包含有失效連結的檔案
    }


def format_check_report(results: List[LinkCheckResult]) -> str:
    """
    格式化檢查報告為可讀的文字格式

    Args:
        results: 檢查結果列表

    Returns:
        str: 格式化的報告
    """
    lines = []
    lines.append("=" * 70)
    lines.append("Markdown 連結檢查報告")
    lines.append("=" * 70)

    # 統計
    total = len(results)
    valid = sum(1 for r in results if r.is_valid)
    invalid = total - valid
    total_links = sum(r.total_links for r in results)
    total_broken = sum(len(r.broken_links) for r in results)

    lines.append(f"\n概括:")
    lines.append(f"  總計: {total} 個檔案")
    lines.append(f"  有效: {valid}")
    lines.append(f"  有問題: {invalid}")
    lines.append(f"  總連結數: {total_links}")
    lines.append(f"  失效連結: {total_broken}")

    # 詳細結果（只顯示有問題的）
    if invalid > 0:
        lines.append(f"\n失效連結詳情:")

        for result in results:
            if not result.is_valid:
                lines.append(f"\n  {result.file_path}:")
                for link in result.broken_links:
                    lines.append(f"    Line {link.line}: [{link.link_text}]({link.link_target})")
                    if link.suggestion:
                        lines.append(f"      {link.suggestion}")

    lines.append("\n" + "=" * 70)
    return "\n".join(lines)


def main():
    """命令行介面"""
    parser = argparse.ArgumentParser(
        description="Markdown 連結檢查工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用範例:
  # 檢查單一文件
  python .claude/lib/markdown_link_checker.py docs/README.md

  # 檢查整個目錄
  python .claude/lib/markdown_link_checker.py --dir .claude/methodologies/

  # JSON 輸出
  python .claude/lib/markdown_link_checker.py --dir docs/ --json

  # 只檢查當前目錄（不遞迴）
  python .claude/lib/markdown_link_checker.py --dir docs/ --no-recursive
        """
    )

    parser.add_argument(
        "file_path",
        nargs="?",
        help="Markdown 檔案路徑"
    )
    parser.add_argument(
        "--dir",
        help="要檢查的目錄路徑"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="輸出 JSON 格式"
    )
    parser.add_argument(
        "--no-recursive",
        action="store_true",
        help="不遞迴檢查子目錄"
    )

    args = parser.parse_args()

    # 確定工作模式
    checker = MarkdownLinkChecker()

    if args.dir:
        results = checker.check_directory(
            args.dir,
            recursive=not args.no_recursive
        )
    elif args.file_path:
        results = [checker.check_file(args.file_path)]
    else:
        parser.print_help()
        sys.exit(1)

    # 輸出結果
    if args.json:
        output = {
            "total_files": len(results),
            "valid_files": sum(1 for r in results if r.is_valid),
            "invalid_files": sum(1 for r in results if not r.is_valid),
            "total_links": sum(r.total_links for r in results),
            "total_broken": sum(len(r.broken_links) for r in results),
            "results": [
                {
                    "file_path": r.file_path,
                    "is_valid": r.is_valid,
                    "total_links": r.total_links,
                    "broken_links": [asdict(link) for link in r.broken_links]
                }
                for r in results
            ]
        }
        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        print(format_check_report(results))

    # 決定 exit code
    all_valid = all(r.is_valid for r in results)
    sys.exit(0 if all_valid else 1)


if __name__ == "__main__":
    main()
