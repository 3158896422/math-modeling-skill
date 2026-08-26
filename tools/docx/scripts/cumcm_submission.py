#!/usr/bin/env python3
"""2026 CUMCM paper/electronic-submission checks and support packaging.

This tool distinguishes official submission constraints from author-side quality
warnings. It is intentionally conservative: automatic checks report evidence,
not a guarantee that the official committee will accept a submission.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Iterable

MAX_FILE_SIZE = 20 * 1024 * 1024
A4_WIDTH_PT = 595.276
A4_HEIGHT_PT = 841.89
PAGE_TOLERANCE_PT = 3.0
DEFAULT_TERMS = (
    "姓名", "学校", "赛区", "参赛编号", "参赛队", "队员", "指导教师", "学号",
    "name", "university", "school", "region", "contestant", "team member",
    "student id", "student_id", "team member",
)
TOC_TERMS = ("目录", "table of contents", "contents")
APPENDIX_TERMS = ("附录", "支撑材料", "appendix", "supporting material")
COMMITMENT_TERMS = ("承诺书", "commitment")
NUMBER_PAGE_TERMS = ("编号专用页", "编号", "special number")
TEXT_SUFFIXES = {
    ".txt", ".md", ".markdown", ".tex", ".bib", ".csv", ".json", ".yaml", ".yml",
    ".py", ".m", ".r", ".java", ".js", ".ts", ".xml", ".html", ".css", ".log",
}


def _norm(value: str) -> str:
    return re.sub(r"\s+", " ", value).casefold()


def _read_text(path: Path) -> str:
    suffix = path.suffix.casefold()
    if suffix in TEXT_SUFFIXES:
        return path.read_text(encoding="utf-8", errors="replace")
    if suffix == ".docx":
        try:
            from docx import Document
        except ImportError as exc:
            raise RuntimeError("扫描 DOCX 需要 python-docx") from exc
        doc = Document(path)
        parts = [p.text for p in doc.paragraphs]
        for table in doc.tables:
            parts.extend(cell.text for row in table.rows for cell in row.cells)
        return "\n".join(parts)
    if suffix == ".pdf":
        return "\n".join(_pdf_page_texts(path))
    return ""


def _pdf_page_texts(path: Path) -> list[str]:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError("处理 PDF 需要 pypdf") from exc
    reader = PdfReader(path)
    result = []
    for page in reader.pages:
        try:
            result.append(page.extract_text() or "")
        except Exception:
            result.append("")
    return result


def _iter_files(paths: Iterable[Path]) -> Iterable[Path]:
    for supplied in paths:
        path = supplied.resolve()
        if not path.exists():
            raise FileNotFoundError(f"路径不存在：{path}")
        if path.is_file():
            yield path
        else:
            yield from (item for item in path.rglob("*") if item.is_file())


def scan_anonymity(paths: Iterable[Path], terms: Iterable[str] = ()) -> dict:
    needles = tuple(dict.fromkeys(_norm(t) for t in (*DEFAULT_TERMS, *terms) if t.strip()))
    hits = []
    scanned = []
    for path in _iter_files(paths):
        if path.suffix.casefold() == ".zip":
            try:
                with zipfile.ZipFile(path) as archive:
                    for info in archive.infolist():
                        if info.is_dir():
                            continue
                        data = archive.read(info)
                        text = data.decode("utf-8", errors="replace") if Path(info.filename).suffix.casefold() in TEXT_SUFFIXES else ""
                        if text:
                            scanned.append(f"{path}!{info.filename}")
                            hits.extend(_find_hits(f"{path}!{info.filename}", text, needles))
            except zipfile.BadZipFile:
                hits.append({"path": str(path), "term": "<invalid zip>", "line": 0, "excerpt": ""})
            continue
        try:
            text = _read_text(path)
        except (OSError, RuntimeError) as exc:
            hits.append({"path": str(path), "term": "<scan error>", "line": 0, "excerpt": str(exc)})
            continue
        if not text:
            continue
        scanned.append(str(path))
        hits.extend(_find_hits(str(path), text, needles))
    return {"terms": list(needles), "scanned_files": scanned, "hits": hits, "passed": not hits}


def _find_hits(label: str, text: str, needles: Iterable[str]) -> list[dict]:
    result = []
    lines = text.splitlines() or [text]
    for line_no, line in enumerate(lines, 1):
        haystack = _norm(line)
        for term in needles:
            if term and term in haystack:
                result.append({"path": label, "term": term, "line": line_no, "excerpt": line[:240]})
    return result


def _page_marker(text: str, terms: Iterable[str]) -> bool:
    haystack = _norm(text)
    return any(_norm(term) in haystack for term in terms)


def audit_page_texts(page_texts: list[str], *, mode: str = "paper", max_body_pages: int = 30) -> dict:
    """Audit page order using extracted page text; returns issues/warnings/metrics."""
    issues: list[str] = []
    warnings: list[str] = []
    if mode not in {"paper", "electronic"}:
        raise ValueError("mode 必须是 paper 或 electronic")
    pages = len(page_texts)
    if mode == "paper":
        if pages < 4:
            issues.append("纸质版至少需要 4 页：承诺书、编号专用页、摘要页和正文起始页")
        if pages >= 1 and not _page_marker(page_texts[0], COMMITMENT_TERMS):
            issues.append("纸质版第 1 页未检测到承诺书标识")
        if pages >= 2 and not _page_marker(page_texts[1], NUMBER_PAGE_TERMS):
            issues.append("纸质版第 2 页未检测到编号专用页标识")
        abstract_page = 3
        body_start = 4
    else:
        if pages < 2:
            issues.append("电子版至少需要摘要页和正文起始页")
        if pages >= 1 and not _page_marker(page_texts[0], ("摘 要", "摘要", "abstract")):
            issues.append("电子版第 1 页未检测到摘要标识")
        abstract_page = 1
        body_start = 2
    if pages >= abstract_page and not _page_marker(page_texts[abstract_page - 1], ("摘 要", "摘要", "abstract")):
        issues.append(f"第 {abstract_page} 页未检测到摘要标识")
    if pages >= body_start and _page_marker(page_texts[body_start - 1], TOC_TERMS):
        issues.append("论文包含目录；2026 年全国赛规范要求不要目录")
    appendix_candidates = [i + 1 for i, text in enumerate(page_texts) if _page_marker(text, APPENDIX_TERMS)]
    appendix_start = appendix_candidates[0] if appendix_candidates else None
    if appendix_start is not None and appendix_start < body_start:
        issues.append("附录出现在正文起始页之前")
    body_end = appendix_start or pages + 1
    body_pages = max(0, body_end - body_start) if body_start <= body_end else 0
    if body_pages > max_body_pages:
        issues.append(f"正文页数 {body_pages}，超过官方上限 {max_body_pages} 页")
    if pages >= abstract_page + 1 and _page_marker(page_texts[abstract_page], APPENDIX_TERMS):
        issues.append("摘要页之后未检测到正文内容，无法确认正文起始页")
    page_number_hits = []
    for number, text in enumerate(page_texts, 1):
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        found = None
        for line in reversed(lines[-6:]):
            match = re.fullmatch(r"(?:第\s*)?(\d+)(?:\s*页)?", line)
            if match:
                found = int(match.group(1))
                break
        page_number_hits.append(found)
    expected_first = 1 if mode == "electronic" else 1
    numbered_pages = page_number_hits[abstract_page - 1:]
    if numbered_pages and all(value is not None for value in numbered_pages):
        expected = list(range(expected_first, expected_first + len(numbered_pages)))
        if numbered_pages != expected:
            issues.append(f"摘要页起的页码不连续：检测到 {numbered_pages}，期望 {expected}")
    else:
        warnings.append("未能从 PDF 文本稳定识别摘要页起的连续页码；请人工检查页脚")
    return {
        "mode": mode,
        "pages": pages,
        "abstract_page": abstract_page,
        "body_start_page": body_start,
        "appendix_start_page": appendix_start,
        "body_pages": body_pages,
        "issues": issues,
        "warnings": warnings,
        "passed": not issues,
    }


def _audit_pdf(path: Path, mode: str) -> dict:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError("处理 PDF 需要 pypdf") from exc
    reader = PdfReader(path)
    sizes = []
    for page in reader.pages:
        sizes.append((float(page.mediabox.width), float(page.mediabox.height)))
    issues = []
    for number, (width, height) in enumerate(sizes, 1):
        if abs(width - A4_WIDTH_PT) > PAGE_TOLERANCE_PT or abs(height - A4_HEIGHT_PT) > PAGE_TOLERANCE_PT:
            issues.append(f"第 {number} 页不是 A4 尺寸：{width:.1f}×{height:.1f} pt")
    page_report = audit_page_texts(_pdf_page_texts(path), mode=mode)
    issues.extend(page_report["issues"])
    return {
        "path": str(path),
        "size_bytes": path.stat().st_size,
        "page_sizes_pt": sizes,
        "page_report": page_report,
        "issues": issues,
        "warnings": page_report["warnings"],
        "passed": not issues and path.stat().st_size <= MAX_FILE_SIZE,
    }


def _scan_pdf_submission_anonymity(path: Path, mode: str, terms: Iterable[str]) -> dict:
    pages = _pdf_page_texts(path)
    start = 2 if mode == "paper" else 0
    needles = tuple(dict.fromkeys(_norm(t) for t in (*DEFAULT_TERMS, *terms) if t.strip()))
    hits = []
    scanned = []
    for page_number, text in enumerate(pages[start:], start + 1):
        scanned.append(f"{path}#page={page_number}")
        hits.extend(_find_hits(f"{path}#page={page_number}", text, needles))
    return {"terms": list(needles), "scanned_files": scanned, "hits": hits, "passed": not hits}


def validate_paper(path: Path, *, mode: str = "paper", terms: Iterable[str] = ()) -> dict:
    source = path.resolve()
    if not source.is_file() or source.suffix.casefold() != ".pdf":
        raise FileNotFoundError(f"提交论文必须是 PDF 文件：{source}")
    report = _audit_pdf(source, mode)
    if source.stat().st_size > MAX_FILE_SIZE:
        report["issues"].append(f"文件大小 {source.stat().st_size} bytes，超过 20 MB")
    anonymity = _scan_pdf_submission_anonymity(source, mode, terms)
    report["anonymity"] = anonymity
    if anonymity["hits"]:
        report["issues"].append(f"匿名检查命中 {len(anonymity['hits'])} 项敏感信息")
    report["passed"] = not report["issues"]
    return report


def export_electronic(source: Path, output: Path, *, terms: Iterable[str] = (), overwrite: bool = False) -> dict:
    source = source.resolve(); output = output.resolve()
    if source == output:
        raise ValueError("电子版输出不能覆盖输入 PDF")
    if not source.is_file() or source.suffix.casefold() != ".pdf":
        raise FileNotFoundError(f"输入纸质版 PDF 不存在：{source}")
    if output.exists() and not overwrite:
        raise FileExistsError(f"输出已存在，未覆盖：{output}")
    try:
        from pypdf import PdfReader, PdfWriter
    except ImportError as exc:
        raise RuntimeError("导出 PDF 需要 pypdf") from exc
    reader = PdfReader(source)
    if len(reader.pages) < 3:
        raise ValueError("纸质版 PDF 少于 3 页，无法删除前两页")
    writer = PdfWriter()
    for page in reader.pages[2:]:
        writer.add_page(page)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(f".{output.name}.tmp")
    try:
        with temporary.open("wb") as handle:
            writer.write(handle)
        os.replace(temporary, output)
    finally:
        if temporary.exists():
            temporary.unlink()
    report = validate_paper(output, mode="electronic", terms=terms)
    report["removed_pages"] = [1, 2]
    return report


def package_support(inputs: Iterable[Path], output: Path, *, terms: Iterable[str] = (), overwrite: bool = False) -> dict:
    output = output.resolve()
    if output.exists() and not overwrite:
        raise FileExistsError(f"输出已存在，未覆盖：{output}")
    files = []
    for path in _iter_files(inputs):
        if path.resolve() == output:
            continue
        relative = path.name if path.is_file() else path.relative_to(path.parent).as_posix()
        name = path.name.casefold()
        if any(term.casefold() in name for term in (*COMMITMENT_TERMS, *NUMBER_PAGE_TERMS)):
            continue
        files.append((path, relative))
    # Rebuild relative names with stable source-directory prefixes where possible.
    files = [(path, f"{path.parent.name}/{path.name}") for path, _ in files]
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(f".{output.name}.tmp")
    try:
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path, arcname in sorted(files, key=lambda pair: pair[1].casefold()):
                archive.write(path, arcname)
            manifest = "支撑材料文件列表\n" + "\n".join(f"- {arcname}" for _, arcname in files) + "\n"
            archive.writestr("支撑材料文件列表.txt", manifest.encode("utf-8"))
        os.replace(temporary, output)
    finally:
        if temporary.exists():
            temporary.unlink()
    anonymity = scan_anonymity([output], terms)
    issues = []
    if output.stat().st_size > MAX_FILE_SIZE:
        issues.append(f"支撑材料大小 {output.stat().st_size} bytes，超过 20 MB")
    if anonymity["hits"]:
        issues.append(f"支撑材料匿名检查命中 {len(anonymity['hits'])} 项敏感信息")
    return {
        "path": str(output), "size_bytes": output.stat().st_size,
        "files": [arcname for _, arcname in files], "anonymity": anonymity,
        "issues": issues, "passed": not issues,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="2026 CUMCM 论文提交检查工具")
    commands = parser.add_subparsers(dest="action", required=True)
    scan = commands.add_parser("scan-anonymity")
    scan.add_argument("paths", nargs="+", type=Path)
    scan.add_argument("--term", action="append", default=[])
    validate = commands.add_parser("validate-paper")
    validate.add_argument("path", type=Path)
    validate.add_argument("--mode", choices=("paper", "electronic"), default="paper")
    validate.add_argument("--term", action="append", default=[])
    export = commands.add_parser("export-electronic")
    export.add_argument("source", type=Path); export.add_argument("output", type=Path)
    export.add_argument("--term", action="append", default=[]); export.add_argument("--overwrite", action="store_true")
    package = commands.add_parser("package-support")
    package.add_argument("output", type=Path); package.add_argument("inputs", nargs="+", type=Path)
    package.add_argument("--term", action="append", default=[]); package.add_argument("--overwrite", action="store_true")
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        if args.action == "scan-anonymity":
            report = scan_anonymity(args.paths, args.term)
        elif args.action == "validate-paper":
            report = validate_paper(args.path, mode=args.mode, terms=args.term)
        elif args.action == "export-electronic":
            report = export_electronic(args.source, args.output, terms=args.term, overwrite=args.overwrite)
        else:
            report = package_support(args.inputs, args.output, terms=args.term, overwrite=args.overwrite)
    except (OSError, RuntimeError, ValueError) as exc:
        report = {"passed": False, "issues": [str(exc)], "error_type": type(exc).__name__}
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("passed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
