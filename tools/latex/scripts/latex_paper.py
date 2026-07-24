"""Prepare, build, and validate template-driven LaTeX modeling papers."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path

TEMPLATE_ROOT = Path(__file__).resolve().parents[1] / "assets" / "templates"
SKILL_ROOT = Path(__file__).resolve().parents[3]
CONTESTS = {"cumcm", "mcm-icm"}
ENGINES = {"xelatex", "lualatex", "pdflatex"}
GRAPHIC_SUFFIXES = (".pdf", ".png", ".jpg", ".jpeg", ".eps", ".svg")
GENERATED_SUFFIXES = {
    ".aux", ".log", ".out", ".toc", ".bbl", ".blg", ".bcf", ".fls",
    ".fdb_latexmk", ".synctex.gz", ".run.xml", ".lof", ".lot", ".nav",
    ".snm", ".vrb", ".xdv", ".dvi", ".ps",
}
DANGEROUS_TEX = re.compile(
    r"\\(?:immediate\s*)?write18\b|\\(?:openin|openout|read|write)\b|"
    r"\\usepackage\s*\{(?:minted|shellesc)\}",
    re.I,
)
QUALITY_DEFAULTS = {
    "cumcm": {
        "min_content_units": 15_000,
        "min_pages": 20,
        "min_equations": 5,
        "min_figures": 8,
        "min_tables": 3,
    },
    "mcm-icm": {
        "min_content_units": 0,
        "min_pages": 0,
        "min_equations": 0,
        "min_figures": 8,
        "min_tables": 0,
    },
}


def _inside(path: Path, root: Path) -> Path:
    resolved = path.resolve()
    if resolved != root and root not in resolved.parents:
        raise ValueError(f"路径超出 LaTeX 项目：{path}")
    return resolved


def _writable(path: Path) -> Path:
    resolved = path.resolve()
    if resolved == SKILL_ROOT or SKILL_ROOT in resolved.parents:
        raise ValueError("拒绝向 SKILL_ROOT 写入 LaTeX 产物")
    return resolved


def _reject_symlinks(root: Path) -> None:
    if root.is_symlink() or any(path.is_symlink() for path in root.rglob("*")):
        raise ValueError("LaTeX 项目包含符号链接，拒绝处理")


def _entry(directory: Path, main_file: str | None = None) -> Path:
    if main_file:
        relative = Path(main_file)
        if relative.is_absolute() or relative.parent != Path("."):
            raise ValueError("主入口必须是模板根目录内的 .tex 文件名")
        selected = _inside(directory / relative, directory.resolve())
        if not selected.is_file() or selected.suffix.casefold() != ".tex":
            raise FileNotFoundError(f"指定的 LaTeX 主入口不存在：{main_file}")
        return selected
    preferred = directory / "main.tex"
    if preferred.is_file():
        return preferred
    candidates = sorted(directory.glob("*.tex"))
    if len(candidates) != 1:
        raise ValueError("未确定 LaTeX 主入口：请提供 main.tex、唯一顶层 .tex 或显式 --main")
    return candidates[0]


def prepare_project(
    output_dir: Path,
    *,
    contest: str = "cumcm",
    template_path: Path | None = None,
    main_file: str | None = None,
) -> dict:
    """Copy an official or bundled template into a new project directory."""
    if contest not in CONTESTS:
        raise ValueError(f"不支持的竞赛配置：{contest}")
    output = _writable(output_dir)
    if output.exists():
        raise FileExistsError(f"输出目录已存在，拒绝覆盖：{output}")
    source = (template_path or (TEMPLATE_ROOT / contest)).resolve()
    if not source.exists():
        raise FileNotFoundError(f"LaTeX 模板不存在：{source}")
    items = [source] if source.is_file() else [source, *source.rglob("*")]
    if any(item.is_symlink() for item in items):
        raise ValueError("模板中包含符号链接，拒绝复制")
    if source.is_file() and source.suffix.casefold() != ".tex":
        raise ValueError("单文件模板必须是 .tex 文件")
    selected = _entry(source, main_file) if source.is_dir() else None
    if source.is_file() and main_file:
        raise ValueError("单文件模板不需要指定主入口")

    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.parent / f".{output.name}.tmp-{uuid.uuid4().hex}"
    try:
        if source.is_dir():
            shutil.copytree(source, temporary)
        else:
            temporary.mkdir()
            shutil.copy2(source, temporary / "main.tex")
        os.replace(temporary, output)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
    entry = (
        output / selected.relative_to(source)
        if selected is not None
        else output / "main.tex"
    )
    return {
        "project_dir": str(output),
        "main_tex": str(entry),
        "template": str(source),
        "contest": contest,
    }


def _strip_comments(text: str) -> str:
    cleaned = []
    for line in text.splitlines():
        cut = len(line)
        for index, character in enumerate(line):
            if character != "%":
                continue
            backslashes = 0
            cursor = index - 1
            while cursor >= 0 and line[cursor] == "\\":
                backslashes += 1
                cursor -= 1
            if backslashes % 2 == 0:
                cut = index
                break
        cleaned.append(line[:cut])
    return "\n".join(cleaned)


def _collect_sources(main_tex: Path) -> tuple[str, list[Path], list[str]]:
    main = main_tex.resolve()
    root = main.parent
    seen: set[Path] = set()
    files: list[Path] = []
    issues: list[str] = []

    def load(path: Path) -> str:
        current = _inside(path, root)
        if current in seen:
            return ""
        if not current.is_file():
            issues.append(f"缺少 LaTeX 子文件：{current.relative_to(root).as_posix()}")
            return ""
        seen.add(current)
        files.append(current)
        text = _strip_comments(current.read_text(encoding="utf-8"))
        chunks = [text]
        for raw in re.findall(r"\\(?:input|include)\s*\{([^}]+)\}", text):
            included = Path(raw.strip())
            if not included.suffix:
                included = included.with_suffix(".tex")
            chunks.append(load(root / included))
        return "\n".join(chunks)

    return load(main), files, issues


def _bibliography_keys(source: str, root: Path, issues: list[str]) -> tuple[set[str], set[str]]:
    manual = set(re.findall(r"\\bibitem(?:\[[^]]*\])?\{([^}]+)\}", source))
    keys = set(manual)
    raw_files = re.findall(r"\\bibliography\s*\{([^}]+)\}", source)
    raw_files += re.findall(r"\\addbibresource(?:\[[^]]*\])?\s*\{([^}]+)\}", source)
    for group in raw_files:
        for raw in group.split(","):
            path = Path(raw.strip())
            if not path.suffix:
                path = path.with_suffix(".bib")
            try:
                bibliography = _inside(root / path, root)
            except ValueError as error:
                issues.append(str(error))
                continue
            if not bibliography.is_file():
                issues.append(f"缺少参考文献库：{path.as_posix()}")
                continue
            content = _strip_comments(bibliography.read_text(encoding="utf-8"))
            keys.update(re.findall(r"@\w+\s*\{\s*([^,\s]+)\s*,", content))
    return keys, manual


def _graphic_roots(source: str, root: Path) -> list[Path]:
    directories = [root]
    for group in re.findall(
        r"\\graphicspath\s*\{((?:\s*\{[^{}]*\}\s*)+)\}", source
    ):
        for raw in re.findall(r"\{([^{}]*)\}", group):
            directories.append(_inside(root / raw.strip(), root))
    return directories


def _graphic_exists(root: Path, directories: list[Path], raw: str) -> bool:
    for directory in directories:
        candidate = _inside(directory / raw.strip(), root)
        if candidate.is_file():
            return True
        if not candidate.suffix and any(
            candidate.with_suffix(suffix).is_file() for suffix in GRAPHIC_SUFFIXES
        ):
            return True
    return False


def _pdf_pages(path: Path) -> int:
    try:
        from pypdf import PdfReader
    except ImportError as error:
        raise RuntimeError("缺少 pypdf，无法读取编译后 PDF 的实际页数") from error
    return len(PdfReader(path).pages)


def source_bundle_sha256(main_tex: Path) -> str:
    if main_tex.is_symlink():
        raise ValueError("LaTeX 主入口不能是符号链接")
    root = main_tex.resolve().parent
    _reject_symlinks(root)
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root)
        if relative.parts[0] == "build":
            continue
        suffix = path.suffix.casefold()
        compound_suffix = "".join(path.suffixes[-2:]).casefold()
        if suffix in GENERATED_SUFFIXES or compound_suffix in GENERATED_SUFFIXES:
            continue
        if path == root / f"{main_tex.stem}.pdf":
            continue
        digest.update(relative.as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def inspect_paper(
    main_tex: Path,
    *,
    contest: str = "cumcm",
    pdf_path: Path | None = None,
    quality_checks: bool = False,
    min_content_units: int | None = None,
    min_pages: int | None = None,
    max_pages: int | None = None,
    min_equations: int | None = None,
    min_figures: int | None = None,
    min_tables: int | None = None,
    require_pdf: bool | None = None,
) -> dict:
    """Inspect LaTeX source, references, figures, and an optional rendered PDF."""
    if contest not in CONTESTS:
        raise ValueError(f"不支持的竞赛配置：{contest}")
    main = main_tex.resolve()
    if not main.is_file() or main.suffix.casefold() != ".tex":
        raise FileNotFoundError(f"LaTeX 入口不存在：{main}")
    source, source_files, issues = _collect_sources(main)
    root = main.parent
    _reject_symlinks(root)
    if DANGEROUS_TEX.search(source):
        issues.append("源码包含被禁用的 TeX 文件或命令执行指令")
    if "\\begin{document}" not in source or "\\end{document}" not in source:
        issues.append("LaTeX 入口缺少完整的 document 环境")
    if not re.search(r"\\begin\s*\{abstract\}", source):
        issues.append("缺少摘要环境")
    if not re.search(r"\\(?:keywords|keyword)\s*\{", source, re.I):
        issues.append("缺少关键词命令")

    placeholders = sorted(set(re.findall(
        r"LATEX_TEMPLATE_[A-Z_]+|\bTODO\b|待补充|请填写|PLACEHOLDER",
        source,
        re.I,
    )))
    if placeholders:
        issues.append("仍含模板占位符：" + "、".join(placeholders[:8]))

    equation_count = len(re.findall(
        r"\\begin\s*\{(?:equation\*?|align\*?|alignat\*?|gather\*?|multline\*?|displaymath|eqnarray\*?)\}",
        source,
    )) + len(re.findall(r"\\\[|\$\$", source))
    figure_blocks = re.findall(
        r"\\begin\s*\{figure\*?\}(.*?)\\end\s*\{figure\*?\}", source, re.S
    )
    table_blocks = re.findall(
        r"\\begin\s*\{(?:table\*?|longtable)\}(.*?)"
        r"\\end\s*\{(?:table\*?|longtable)\}",
        source,
        re.S,
    )
    references: set[str] = set()
    for group in re.findall(
        r"\\(?:ref|pageref|autoref|cref|Cref|eqref)\*?\s*\{([^}]+)\}", source
    ):
        references.update(label.strip() for label in group.split(",") if label.strip())
    all_labels = re.findall(r"\\label\s*\{([^}]+)\}", source)
    duplicate_labels = sorted({label for label in all_labels if all_labels.count(label) > 1})
    if duplicate_labels:
        issues.append("重复 label：" + "、".join(duplicate_labels))
    for kind, blocks in (("图", figure_blocks), ("表", table_blocks)):
        for index, block in enumerate(blocks, 1):
            labels = re.findall(r"\\label\s*\{([^}]+)\}", block)
            if not labels:
                issues.append(f"第 {index} 个{kind}环境缺少 label")
            elif not any(label in references for label in labels):
                issues.append(f"孤儿{kind}：{labels[0]} 未在正文引用")

    graphic_roots = _graphic_roots(source, root)
    for raw in re.findall(r"\\includegraphics(?:\[[^]]*\])?\s*\{([^}]+)\}", source):
        try:
            exists = _graphic_exists(root, graphic_roots, raw)
        except ValueError as error:
            issues.append(str(error))
            continue
        if not exists:
            issues.append(f"图片文件不存在：{raw}")

    citations: set[str] = set()
    for group in re.findall(
        r"\\(?:cite|citep|citet|parencite|textcite|autocite)\*?(?:\[[^]]*\]){0,2}\s*\{([^}]+)\}",
        source,
    ):
        citations.update(key.strip() for key in group.split(",") if key.strip())
    bibliography, manual_bibliography = _bibliography_keys(source, root, issues)
    missing_citations = sorted(citations - bibliography)
    if missing_citations:
        issues.append("正文引用缺少参考文献条目：" + "、".join(missing_citations))
    unused_manual = sorted(manual_bibliography - citations)
    if unused_manual:
        issues.append("手工参考文献未被正文引用：" + "、".join(unused_manual))

    document = source.split("\\begin{document}", 1)[-1]
    document = re.sub(r"\\begin\s*\{[^}]+\}|\\end\s*\{[^}]+\}", " ", document)
    document = re.sub(r"\\[A-Za-z@]+\*?(?:\[[^]]*\])?", " ", document)
    document = re.sub(r"[{}$^_&~#]", " ", document)
    content_units = len(re.findall(
        r"[\u3400-\u9fff]|[A-Za-z]+(?:[-'][A-Za-z]+)*|\d+(?:\.\d+)?",
        document,
    ))

    rendered_pages = None
    pdf = pdf_path.resolve() if pdf_path else None
    must_have_pdf = quality_checks if require_pdf is None else require_pdf
    if pdf is not None and pdf.is_file():
        try:
            rendered_pages = _pdf_pages(pdf)
        except Exception as error:
            issues.append(f"PDF 页数检查失败：{error}")
    elif must_have_pdf:
        issues.append("缺少编译后的 PDF，无法执行实际页数和版面检查")

    defaults = QUALITY_DEFAULTS[contest] if quality_checks else {}
    thresholds = {
        "min_content_units": min_content_units if min_content_units is not None else defaults.get("min_content_units", 0),
        "min_pages": min_pages if min_pages is not None else defaults.get("min_pages", 0),
        "min_equations": min_equations if min_equations is not None else defaults.get("min_equations", 0),
        "min_figures": min_figures if min_figures is not None else defaults.get("min_figures", 0),
        "min_tables": min_tables if min_tables is not None else defaults.get("min_tables", 0),
    }
    metrics = {
        "content_units": content_units,
        "equations": equation_count,
        "figures": len(figure_blocks),
        "tables": len(table_blocks),
        "citations": len(citations),
        "source_files": len(source_files),
    }
    labels = {
        "content_units": "字词单位",
        "equations": "公式",
        "figures": "图",
        "tables": "表",
    }
    for key, metric_key in (
        ("min_content_units", "content_units"),
        ("min_equations", "equations"),
        ("min_figures", "figures"),
        ("min_tables", "tables"),
    ):
        minimum = int(thresholds[key] or 0)
        if minimum and metrics[metric_key] < minimum:
            issues.append(f"预警：{labels[metric_key]} {metrics[metric_key]}，低于质量目标 {minimum}")
    minimum_pages = int(thresholds["min_pages"] or 0)
    if rendered_pages is not None and minimum_pages and rendered_pages < minimum_pages:
        issues.append(f"预警：实际页数 {rendered_pages}，低于质量目标 {minimum_pages}")
    if rendered_pages is not None and max_pages is not None and rendered_pages > max_pages:
        issues.append(f"实际页数 {rendered_pages}，超过官方上限 {max_pages}")

    return {
        "main_tex": str(main),
        "pdf_path": str(pdf) if pdf else None,
        "source_sha256": source_bundle_sha256(main),
        "rendered_pages": rendered_pages,
        "metrics": metrics,
        "issues": issues,
        "passed": not issues,
    }


def build_paper(
    main_tex: Path,
    *,
    engine: str = "xelatex",
    output_dir: Path | None = None,
    publish_path: Path | None = None,
) -> dict:
    """Compile a LaTeX project without enabling shell escape."""
    if engine not in ENGINES:
        raise ValueError(f"不支持的 LaTeX 引擎：{engine}")
    if main_tex.is_symlink():
        raise ValueError("LaTeX 主入口不能是符号链接")
    main = _writable(main_tex)
    if not main.is_file() or main.suffix.casefold() != ".tex":
        raise FileNotFoundError(f"LaTeX 入口不存在：{main}")
    root = main.parent
    _reject_symlinks(root)
    source, _, source_issues = _collect_sources(main)
    if source_issues:
        raise ValueError("；".join(source_issues))
    if DANGEROUS_TEX.search(source):
        raise ValueError("源码包含被禁用的 TeX 文件或命令执行指令")
    graphic_roots = _graphic_roots(source, root)
    for raw in re.findall(r"\\includegraphics(?:\[[^]]*\])?\s*\{([^}]+)\}", source):
        for directory in graphic_roots:
            _inside(directory / raw.strip(), root)
    output = _inside((output_dir or (root / "build")), root)
    output_argument = output.relative_to(root).as_posix() or "."
    publish_target = None
    if publish_path is not None:
        publish_target = _writable(publish_path)
        if publish_target.parent not in {root, root.parent}:
            raise ValueError("发布 PDF 必须位于 LaTeX 项目目录或其直接父目录")
        if publish_target.suffix.casefold() != ".pdf":
            raise ValueError("发布路径必须使用 .pdf 扩展名")
    latexmk = shutil.which("latexmk")
    executable = shutil.which(engine)
    if latexmk:
        mode = {"xelatex": "-xelatex", "lualatex": "-lualatex", "pdflatex": "-pdf"}[engine]
        commands = [[
            latexmk,
            "-norc",
            mode,
            "-e",
            f"${engine} = '{engine} -no-shell-escape %O %S'",
            "-interaction=nonstopmode",
            "-halt-on-error",
            "-file-line-error",
            f"-outdir={output_argument}",
            main.name,
        ]]
    elif executable:
        if re.search(r"\\(?:bibliography|addbibresource)\b", source):
            raise RuntimeError("未找到 latexmk，含外部参考文献的论文无法完成可靠编译")
        command = [
            executable,
            "-no-shell-escape",
            "-interaction=nonstopmode",
            "-halt-on-error",
            "-file-line-error",
            f"-output-directory={output_argument}",
            main.name,
        ]
        commands = [command, command]
    else:
        raise RuntimeError(f"未找到 latexmk 或 {engine}，无法编译 LaTeX 论文")

    output.mkdir(parents=True, exist_ok=True)
    outputs: list[str] = []
    for command in commands:
        completed = subprocess.run(
            command,
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
            errors="replace",
            env={**os.environ, "openin_any": "p", "openout_any": "p"},
            timeout=180,
        )
        outputs.append((completed.stdout or "") + (completed.stderr or ""))
        if completed.returncode != 0:
            detail = outputs[-1].strip()[-2000:]
            raise RuntimeError(f"LaTeX 编译失败：{detail or completed.returncode}")
    pdf = output / f"{main.stem}.pdf"
    if not pdf.is_file():
        raise RuntimeError("LaTeX 命令执行成功但没有生成 PDF")
    log_path = output / f"{main.stem}.log"
    log = log_path.read_text(encoding="utf-8", errors="replace") if log_path.is_file() else "\n".join(outputs)
    build_issues = []
    if re.search(r"undefined references|Citation .+ undefined|There were undefined citations", log, re.I):
        build_issues.append("编译日志仍有未解析的引用或文献")
    if re.search(r"Undefined control sequence|! LaTeX Error", log, re.I):
        build_issues.append("编译日志包含 LaTeX 错误")
    warning_lines = []
    for line in log.splitlines():
        stripped = line.strip()
        if re.search(
            r"(?:LaTeX|Package .+|Class .+) Warning:|"
            r"(?:Over|Under)full \\[hv]box|font warning",
            stripped,
            re.I,
        ):
            warning_lines.append(stripped)
    for warning in dict.fromkeys(warning_lines):
        build_issues.append(f"编译预警：{warning}")
    if publish_target is not None:
        publish_target.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(
                "wb", dir=publish_target.parent, delete=False, suffix=".tmp"
            ) as handle:
                handle.write(pdf.read_bytes())
                handle.flush()
                os.fsync(handle.fileno())
                temporary = Path(handle.name)
            os.replace(temporary, publish_target)
        finally:
            if temporary is not None and temporary.exists():
                temporary.unlink()
    return {
        "main_tex": str(main),
        "pdf_path": str(pdf),
        "published_pdf": str(publish_target) if publish_target else None,
        "log_path": str(log_path),
        "engine": engine,
        "issues": build_issues,
        "passed": not build_issues,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="action", required=True)
    init = commands.add_parser("init", help="从官方或内置模板初始化 LaTeX 项目")
    init.add_argument("output_dir", type=Path)
    init.add_argument("--contest", choices=sorted(CONTESTS), default="cumcm")
    init.add_argument("--template", type=Path)
    init.add_argument("--main", dest="main_file")
    build = commands.add_parser("build", help="编译 LaTeX 项目")
    build.add_argument("main_tex", type=Path)
    build.add_argument("--engine", choices=sorted(ENGINES), default="xelatex")
    build.add_argument("--output-dir", type=Path)
    build.add_argument("--publish", type=Path)
    validate = commands.add_parser("validate", help="校验 LaTeX 源码和编译结果")
    validate.add_argument("main_tex", type=Path)
    validate.add_argument("--contest", choices=sorted(CONTESTS), default="cumcm")
    validate.add_argument("--pdf", type=Path)
    validate.add_argument("--quality-checks", action="store_true")
    validate.add_argument("--min-content-units", type=int)
    validate.add_argument("--min-pages", type=int)
    validate.add_argument("--max-pages", type=int)
    validate.add_argument("--min-equations", type=int)
    validate.add_argument("--min-figures", type=int)
    validate.add_argument("--min-tables", type=int)
    return parser


def main() -> int:
    arguments = _parser().parse_args()
    if arguments.action == "init":
        result = prepare_project(
            arguments.output_dir,
            contest=arguments.contest,
            template_path=arguments.template,
            main_file=arguments.main_file,
        )
    elif arguments.action == "build":
        result = build_paper(
            arguments.main_tex,
            engine=arguments.engine,
            output_dir=arguments.output_dir,
            publish_path=arguments.publish,
        )
    else:
        result = inspect_paper(
            arguments.main_tex,
            contest=arguments.contest,
            pdf_path=arguments.pdf,
            quality_checks=arguments.quality_checks,
            min_content_units=arguments.min_content_units,
            min_pages=arguments.min_pages,
            max_pages=arguments.max_pages,
            min_equations=arguments.min_equations,
            min_figures=arguments.min_figures,
            min_tables=arguments.min_tables,
        )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("passed", True) else 1


if __name__ == "__main__":
    raise SystemExit(main())
