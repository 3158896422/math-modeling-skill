#!/usr/bin/env python3
"""CUMCM 2026 paper/electronic-submission checks and support packaging.

The checker separates official submission constraints from author-side quality
warnings.  It is deliberately conservative: a PASS is evidence that the
machine-checkable rules were satisfied, not a guarantee of committee acceptance.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import zipfile
from pathlib import Path
from typing import Iterable

MAX_FILE_SIZE = 20 * 1024 * 1024
A4_WIDTH_PT = 595.276
A4_HEIGHT_PT = 841.89
PAGE_TOLERANCE_PT = 3.0

# Do not include the bare English word ``name``: it occurs frequently in source
# code and would make an anonymity scan unusably noisy.  Real names/schools/
# regions must be supplied with --term.
DEFAULT_TERMS = (
    "姓名", "学校", "赛区", "参赛编号", "参赛队", "队员", "指导教师", "学号",
    "university", "school", "region", "contestant", "team member",
    "student id", "student_id",
)
TOC_TERMS = ("目录", "table of contents", "contents")
APPENDIX_TERMS = ("附录", "支撑材料", "appendix", "supporting material")
COMMITMENT_TERMS = ("承诺书", "commitment")
NUMBER_PAGE_TERMS = ("编号专用页", "special number")
ABSTRACT_TERMS = ("摘 要", "摘要", "abstract")
BODY_START_TERMS = (
    "正文", "问题重述", "问题分析", "模型假设", "模型建立", "符号说明",
    "problem restatement", "model assumptions", "model formulation",
)
TEXT_SUFFIXES = {
    ".txt", ".md", ".markdown", ".tex", ".bib", ".csv", ".json", ".yaml", ".yml",
    ".py", ".m", ".r", ".java", ".js", ".ts", ".xml", ".html", ".css", ".log",
}
DOCUMENT_SUFFIXES = {".docx", ".pdf"}
SPREADSHEET_SUFFIXES = {".xlsx", ".xlsm", ".xltx", ".xltm"}


def _norm(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().casefold()


def _term_is_ascii(term: str) -> bool:
    return bool(re.fullmatch(r"[a-z0-9][a-z0-9 _-]*", term.casefold()))


def _term_in_text(text: str, term: str) -> bool:
    """Match Chinese terms by substring and English terms by word boundary."""
    if not term:
        return False
    if _term_is_ascii(term):
        pattern = rf"(?<![a-z0-9_]){re.escape(term)}(?![a-z0-9_])"
        return re.search(pattern, text.casefold()) is not None
    return term in text


def _read_docx_bytes(data: bytes) -> str:
    try:
        from docx import Document
    except ImportError as exc:
        raise RuntimeError("扫描 DOCX 需要 python-docx") from exc
    doc = Document(io.BytesIO(data))
    parts = [p.text for p in doc.paragraphs]
    for table in doc.tables:
        parts.extend(cell.text for row in table.rows for cell in row.cells)
    for section in doc.sections:
        parts.extend(p.text for p in section.header.paragraphs)
        parts.extend(p.text for p in section.footer.paragraphs)
    return "\n".join(parts)


def _pdf_page_texts_from_bytes(data: bytes) -> list[str]:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError("处理 PDF 需要 pypdf") from exc
    reader = PdfReader(io.BytesIO(data))
    result = []
    for page in reader.pages:
        try:
            result.append(page.extract_text() or "")
        except Exception:
            result.append("")
    return result


def _read_spreadsheet_bytes(data: bytes) -> str:
    """Extract XML text from OOXML spreadsheets without requiring openpyxl."""
    parts = []
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            for info in archive.infolist():
                if info.is_dir() or Path(info.filename).suffix.casefold() != ".xml":
                    continue
                parts.append(archive.read(info).decode("utf-8", errors="replace"))
    except zipfile.BadZipFile as exc:
        raise ValueError("无效的 OOXML 表格文件") from exc
    return "\n".join(parts)


def _read_bytes(path: Path) -> bytes:
    return path.read_bytes()


def _read_text(path: Path) -> str:
    suffix = path.suffix.casefold()
    if suffix in TEXT_SUFFIXES:
        return _read_bytes(path).decode("utf-8", errors="replace")
    if suffix == ".docx":
        return _read_docx_bytes(_read_bytes(path))
    if suffix == ".pdf":
        return "\n".join(_pdf_page_texts_from_bytes(_read_bytes(path)))
    if suffix in SPREADSHEET_SUFFIXES:
        return _read_spreadsheet_bytes(_read_bytes(path))
    return ""


def _iter_files(paths: Iterable[Path]) -> Iterable[Path]:
    for supplied in paths:
        path = supplied.resolve()
        if not path.exists():
            raise FileNotFoundError(f"路径不存在：{path}")
        if path.is_file():
            yield path
        else:
            yield from (item for item in path.rglob("*") if item.is_file())


def _find_hits(label: str, text: str, needles: Iterable[str]) -> list[dict]:
    result = []
    lines = text.splitlines() or [text]
    for line_no, line in enumerate(lines, 1):
        haystack = _norm(line)
        for term in needles:
            if _term_in_text(haystack, term):
                result.append({"path": label, "term": term, "line": line_no, "excerpt": line[:240]})
    return result


def _archive_member_text(name: str, data: bytes) -> str:
    suffix = Path(name).suffix.casefold()
    if suffix in TEXT_SUFFIXES:
        return data.decode("utf-8", errors="replace")
    if suffix == ".docx":
        return _read_docx_bytes(data)
    if suffix == ".pdf":
        return "\n".join(_pdf_page_texts_from_bytes(data))
    if suffix in SPREADSHEET_SUFFIXES:
        return _read_spreadsheet_bytes(data)
    return ""


def _scan_zip(path: Path, needles: tuple[str, ...]) -> tuple[list[str], list[dict]]:
    scanned: list[str] = []
    hits: list[dict] = []
    try:
        with zipfile.ZipFile(path) as archive:
            for info in archive.infolist():
                if info.is_dir():
                    continue
                label = f"{path}!{info.filename}"
                # File names are part of the submitted material and must also
                # be anonymous, even when the member is binary.
                hits.extend(_find_hits(f"{label}!filename", info.filename, needles))
                try:
                    text = _archive_member_text(info.filename, archive.read(info))
                except (OSError, RuntimeError, ValueError) as exc:
                    hits.append({"path": label, "term": "<scan error>", "line": 0, "excerpt": str(exc)})
                    continue
                if text:
                    scanned.append(label)
                    hits.extend(_find_hits(label, text, needles))
    except zipfile.BadZipFile:
        hits.append({"path": str(path), "term": "<invalid zip>", "line": 0, "excerpt": ""})
    return scanned, hits


def scan_anonymity(paths: Iterable[Path], terms: Iterable[str] = ()) -> dict:
    raw_terms = [str(t) for t in (*DEFAULT_TERMS, *terms) if str(t).strip()]
    needles = tuple(dict.fromkeys(_norm(t) for t in raw_terms))
    hits: list[dict] = []
    scanned: list[str] = []
    for path in _iter_files(paths):
        if path.suffix.casefold() == ".zip":
            zip_scanned, zip_hits = _scan_zip(path, needles)
            scanned.extend(zip_scanned)
            hits.extend(zip_hits)
            continue
        try:
            text = _read_text(path)
        except (OSError, RuntimeError, ValueError) as exc:
            hits.append({"path": str(path), "term": "<scan error>", "line": 0, "excerpt": str(exc)})
            continue
        # Binary files with identity-bearing filenames must still be caught.
        hits.extend(_find_hits(f"{path}!filename", path.name, needles))
        if not text:
            continue
        scanned.append(str(path))
        hits.extend(_find_hits(str(path), text, needles))
    return {"terms": list(needles), "scanned_files": scanned, "hits": hits, "passed": not hits}


def _page_marker(text: str, terms: Iterable[str]) -> bool:
    haystack = _norm(text)
    return any(_term_in_text(haystack, _norm(term)) for term in terms)


def _has_body_start_marker(text: str) -> bool:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for line in lines[:24]:
        normalized = _norm(line)
        if _page_marker(normalized, BODY_START_TERMS):
            return True
        if re.match(r"^(?:[一二三四五六七八九十]+\s*[、.]|第\s*\d+\s*[问、.]|\d+\s*[.、)])", normalized):
            return True
    return False


def _extract_page_number(text: str) -> int | None:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for line in reversed(lines[-10:]):
        match = re.fullmatch(r"(?:第\s*)?(\d{1,3})(?:\s*页)?", line)
        if match:
            return int(match.group(1))
        match = re.search(r"(?:^|\s)(\d{1,3})(?:\s*页)?$", line)
        if match:
            return int(match.group(1))
    return None


def audit_page_texts(
    page_texts: list[str],
    *,
    mode: str = "paper",
    max_body_pages: int | None = None,
    max_total_pages: int = 30,
) -> dict:
    """Audit fixed pages, total-page limit, appendix boundary and page numbering.

    The total-page limit is a Skill output gate and is intentionally stricter
    than the 2026 official body-only wording.
    """
    issues: list[str] = []
    warnings: list[str] = []
    if mode not in {"paper", "electronic"}:
        raise ValueError("mode 必须是 paper 或 electronic")
    pages = len(page_texts)
    if max_total_pages is not None and pages > max_total_pages:
        issues.append(
            f"论文总页数 {pages}，超过 Skill 当前总页数上限 {max_total_pages} 页"
        )
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
        if pages >= 1 and not _page_marker(page_texts[0], ABSTRACT_TERMS):
            issues.append("电子版第 1 页未检测到摘要标识")
        abstract_page = 1
        body_start = 2

    if pages >= abstract_page and not _page_marker(page_texts[abstract_page - 1], ABSTRACT_TERMS):
        issues.append(f"第 {abstract_page} 页未检测到摘要标识")
    if pages < body_start:
        issues.append(f"未找到正文起始页（应为第 {body_start} 页）")
    elif not _has_body_start_marker(page_texts[body_start - 1]):
        issues.append(
            f"第 {body_start} 页未检测到正文起始标识；无法确认摘要原则上不超过 1 页"
        )
    elif _page_marker(page_texts[body_start - 1], ("关键词：", "keywords:")):
        issues.append(f"第 {body_start} 页仍包含摘要/关键词内容，摘要可能超过 1 页")

    if pages >= body_start and _page_marker(page_texts[body_start - 1], TOC_TERMS):
        issues.append("论文包含目录；2026 年全国赛规范要求不要目录")

    appendix_candidates = [
        i + 1 for i, text in enumerate(page_texts)
        if _page_marker(text, APPENDIX_TERMS)
    ]
    appendix_start = appendix_candidates[0] if appendix_candidates else None
    if appendix_start is not None and appendix_start < body_start:
        issues.append("附录出现在正文起始页之前")
    body_end = appendix_start or pages + 1
    body_pages = max(0, body_end - body_start) if body_start <= body_end else 0
    if max_body_pages is not None and body_pages > max_body_pages:
        issues.append(f"正文页数 {body_pages}，超过配置上限 {max_body_pages} 页")

    page_numbers = [_extract_page_number(text) for text in page_texts]
    numbered_pages = page_numbers[abstract_page - 1:]
    if not numbered_pages or any(value is None for value in numbered_pages):
        issues.append("无法确认摘要页起的连续页码；请确保页脚从 1 开始连续编号")
    else:
        expected = list(range(1, len(numbered_pages) + 1))
        if numbered_pages != expected:
            issues.append(f"摘要页起的页码不连续：检测到 {numbered_pages}，期望 {expected}")

    return {
        "mode": mode,
        "pages": pages,
        "total_pages": pages,
        "max_total_pages": max_total_pages,
        "abstract_page": abstract_page,
        "body_start_page": body_start,
        "appendix_start_page": appendix_start,
        "body_pages": body_pages,
        "page_numbers": page_numbers,
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
    sizes = [(float(page.mediabox.width), float(page.mediabox.height)) for page in reader.pages]
    issues = []
    for number, (width, height) in enumerate(sizes, 1):
        if abs(width - A4_WIDTH_PT) > PAGE_TOLERANCE_PT or abs(height - A4_HEIGHT_PT) > PAGE_TOLERANCE_PT:
            issues.append(f"第 {number} 页不是 A4 尺寸：{width:.1f}×{height:.1f} pt")
    page_report = audit_page_texts(_pdf_page_texts_from_bytes(path.read_bytes()), mode=mode)
    issues.extend(page_report["issues"])
    return {
        "path": str(path),
        "size_bytes": path.stat().st_size,
        "page_sizes_pt": sizes,
        "page_report": page_report,
        "issues": issues,
        "warnings": page_report["warnings"],
        "passed": not issues,
    }


def _scan_pdf_submission_anonymity(path: Path, mode: str, terms: Iterable[str]) -> dict:
    pages = _pdf_page_texts_from_bytes(path.read_bytes())
    start = 2 if mode == "paper" else 0
    raw_terms = [str(t) for t in (*DEFAULT_TERMS, *terms) if str(t).strip()]
    needles = tuple(dict.fromkeys(_norm(t) for t in raw_terms))
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
    # The 20 MB limit is an electronic-submission limit.  The paper PDF is an
    # intermediate rendering and may be larger before PDF optimization.
    if mode == "electronic" and source.stat().st_size > MAX_FILE_SIZE:
        report["issues"].append(f"电子版文件大小 {source.stat().st_size} bytes，超过 20 MB")
    anonymity = _scan_pdf_submission_anonymity(source, mode, terms)
    report["anonymity"] = anonymity
    if anonymity["hits"]:
        report["issues"].append(f"匿名检查命中 {len(anonymity['hits'])} 项敏感信息")
    report["passed"] = not report["issues"]
    return report


def export_electronic(source: Path, output: Path, *, terms: Iterable[str] = (), overwrite: bool = False) -> dict:
    source = source.resolve()
    output = output.resolve()
    if source == output:
        raise ValueError("电子版输出不能覆盖输入 PDF")
    if not source.is_file() or source.suffix.casefold() != ".pdf":
        raise FileNotFoundError(f"输入纸质版 PDF 不存在：{source}")
    if output.exists() and not overwrite:
        raise FileExistsError(f"输出已存在，未覆盖：{output}")
    source_report = validate_paper(source, mode="paper", terms=terms)
    if not source_report["passed"]:
        raise ValueError("纸质版 PDF 未通过导出前检查：" + "；".join(source_report["issues"]))
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
    if not report["passed"] and output.exists():
        output.unlink()
    return report


def _support_arcname(path: Path, supplied: Path) -> str:
    supplied = supplied.resolve()
    if supplied.is_file():
        return supplied.name
    return f"{supplied.name}/{path.relative_to(supplied).as_posix()}"


def package_support(inputs: Iterable[Path], output: Path, *, terms: Iterable[str] = (), overwrite: bool = False) -> dict:
    """Create a ZIP support package with a stable relative-path manifest."""
    output = output.resolve()
    if output.suffix.casefold() != ".zip":
        raise ValueError("当前实现生成 ZIP；请将支撑材料输出文件命名为 .zip")
    if output.exists() and not overwrite:
        raise FileExistsError(f"输出已存在，未覆盖：{output}")

    files: list[tuple[Path, str]] = []
    seen: set[str] = set()
    for supplied in inputs:
        supplied = supplied.resolve()
        for path in _iter_files([supplied]):
            if path == output:
                continue
            if any(term.casefold() in path.name.casefold() for term in (*COMMITMENT_TERMS, *NUMBER_PAGE_TERMS)):
                continue
            arcname = _support_arcname(path, supplied)
            if arcname in seen:
                raise ValueError(f"支撑材料归档路径冲突：{arcname}")
            seen.add(arcname)
            files.append((path, arcname))

    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(f".{output.name}.tmp")
    try:
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path, arcname in sorted(files, key=lambda pair: pair[1].casefold()):
                archive.write(path, arcname)
            manifest_lines = ["支撑材料文件列表", ""]
            manifest_lines.extend(f"- {arcname}" for _, arcname in sorted(files, key=lambda pair: pair[1].casefold()))
            if not files:
                manifest_lines.append("- （无；如确实无支撑材料，可不提交本 ZIP）")
            archive.writestr("支撑材料文件列表.txt", ("\n".join(manifest_lines) + "\n").encode("utf-8"))
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
        "path": str(output),
        "size_bytes": output.stat().st_size,
        "files": [arcname for _, arcname in sorted(files, key=lambda pair: pair[1].casefold())],
        "anonymity": anonymity,
        "issues": issues,
        "passed": not issues,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="2026 CUMCM 论文提交检查工具")
    commands = parser.add_subparsers(dest="action", required=True)
    scan = commands.add_parser("scan-anonymity", help="扫描论文、代码、数据或 ZIP 中的身份信息")
    scan.add_argument("paths", nargs="+", type=Path)
    scan.add_argument("--term", action="append", default=[])
    validate = commands.add_parser("validate-paper", help="检查纸质版或电子版 PDF")
    validate.add_argument("path", type=Path)
    validate.add_argument("--mode", choices=("paper", "electronic"), default="paper")
    validate.add_argument("--term", action="append", default=[])
    export = commands.add_parser("export-electronic", help="删除纸质版 PDF 前两页并检查电子版")
    export.add_argument("source", type=Path)
    export.add_argument("output", type=Path)
    export.add_argument("--term", action="append", default=[])
    export.add_argument("--overwrite", action="store_true")
    package = commands.add_parser("package-support", help="生成 ≤20 MB 的 ZIP 支撑材料包")
    package.add_argument("output", type=Path)
    package.add_argument("inputs", nargs="+", type=Path)
    package.add_argument("--term", action="append", default=[])
    package.add_argument("--overwrite", action="store_true")
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
