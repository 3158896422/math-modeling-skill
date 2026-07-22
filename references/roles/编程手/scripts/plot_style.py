#!/usr/bin/env python3
"""数学建模论文图的统一样式与导出工具。"""

from __future__ import annotations

import warnings
import logging
from pathlib import Path
from typing import Iterable, Sequence


SKILL_ROOT = Path(__file__).resolve().parents[4]

# 以色觉可达性为先，颜色名称表达用途而不是绑定具体模型。
PALETTE = {
    "primary": "#0072B2",
    "secondary": "#E69F00",
    "positive": "#009E73",
    "contrast": "#D55E00",
    "accent": "#CC79A7",
    "sky": "#56B4E9",
    "neutral": "#6B7280",
    "dark": "#222222",
}

COLOR_SEQUENCE = tuple(PALETTE[name] for name in (
    "primary",
    "secondary",
    "positive",
    "contrast",
    "accent",
    "sky",
    "neutral",
))

WIDTHS_IN = {
    "single": 3.5,
    "double": 7.2,
    "report": 6.3,
}

_CJK_SANS = (
    "Noto Sans CJK SC",
    "Source Han Sans SC",
    "Microsoft YaHei",
    "SimHei",
    "PingFang SC",
)


def _available_fonts() -> set[str]:
    from matplotlib import font_manager

    return {item.name for item in font_manager.fontManager.ttflist}


def choose_font(language: str = "zh") -> str:
    """选择可用字体；中文字体缺失时给出警告并安全回退。"""

    if language not in {"zh", "en"}:
        raise ValueError("language 只能是 'zh' 或 'en'")
    available = _available_fonts()
    if language == "zh":
        for name in _CJK_SANS:
            if name in available:
                return name
        warnings.warn(
            "未检测到常用中文字体，已回退到 DejaVu Sans；导出前必须检查中文和特殊符号是否缺字。",
            RuntimeWarning,
            stacklevel=2,
        )
    for name in ("Arial", "Helvetica", "DejaVu Sans"):
        if name in available:
            return name
    return "DejaVu Sans"


def figure_size(width: str = "report", aspect: float = 0.62) -> tuple[float, float]:
    """按最终使用宽度返回英寸尺寸，避免在论文中二次大幅缩放。"""

    if width not in WIDTHS_IN:
        raise ValueError(f"未知宽度方案: {width}")
    if aspect <= 0:
        raise ValueError("aspect 必须大于 0")
    width_in = WIDTHS_IN[width]
    return width_in, width_in * aspect


def apply_publication_style(language: str = "zh", width: str = "report") -> dict:
    """应用适合数学建模论文的克制型出版样式。"""

    import matplotlib as mpl
    from cycler import cycler

    font_name = choose_font(language)
    size = figure_size(width)
    mpl.rcParams.update({
        "figure.figsize": size,
        "figure.constrained_layout.use": True,
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "font.family": "sans-serif",
        "font.sans-serif": [font_name, "Arial", "Helvetica", "DejaVu Sans"],
        "font.size": 8.0,
        "axes.titlesize": 9.0,
        "axes.labelsize": 8.5,
        "xtick.labelsize": 7.5,
        "ytick.labelsize": 7.5,
        "legend.fontsize": 7.5,
        "axes.linewidth": 0.8,
        "lines.linewidth": 1.4,
        "lines.markersize": 4.5,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": False,
        "legend.frameon": False,
        "axes.unicode_minus": False,
        "axes.prop_cycle": cycler(color=COLOR_SEQUENCE),
        "svg.fonttype": "none",
        "pdf.fonttype": 42,
        "savefig.facecolor": "white",
        "savefig.dpi": 300,
    })
    return {"font": font_name, "size_inches": size, "colors": COLOR_SEQUENCE}


def add_panel_labels(
    axes: Iterable,
    labels: Sequence[str] | None = None,
    *,
    x_offset_pt: float = -16.0,
    y_offset_pt: float = 2.0,
) -> None:
    """以固定物理偏移为多面板图添加统一标签。"""

    axes_list = list(axes)
    panel_labels = list(labels) if labels is not None else [chr(97 + i) for i in range(len(axes_list))]
    if len(panel_labels) != len(axes_list):
        raise ValueError("labels 数量必须与 axes 数量一致")
    for axis, label in zip(axes_list, panel_labels):
        axis.annotate(
            label,
            xy=(0, 1),
            xycoords="axes fraction",
            xytext=(x_offset_pt, y_offset_pt),
            textcoords="offset points",
            ha="right",
            va="bottom",
            fontsize=9,
            fontweight="bold",
            annotation_clip=False,
        )


class _GlyphHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.messages: list[str] = []

    def emit(self, record) -> None:
        message = record.getMessage()
        if "Glyph" in message and "missing from font" in message:
            self.messages.append(message)


def _labels_overlap(labels, renderer, axis: str) -> bool:
    boxes = [
        label.get_window_extent(renderer)
        for label in labels
        if label.get_visible() and label.get_text().strip()
    ]
    boxes.sort(key=(lambda box: box.x0) if axis == "x" else (lambda box: box.y0))
    if axis == "x":
        return any(left.x1 > right.x0 + 1 for left, right in zip(boxes, boxes[1:]))
    return any(lower.y1 > upper.y0 + 1 for lower, upper in zip(boxes, boxes[1:]))


def audit_layout(fig) -> list[str]:
    """在导出前检查缺字、画布外文字和相邻刻度重叠。"""

    import matplotlib.text as mtext

    handler = _GlyphHandler()
    logger = logging.getLogger("matplotlib")
    logger.addHandler(handler)
    try:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            fig.canvas.draw()
    finally:
        logger.removeHandler(handler)

    messages = handler.messages + [
        str(item.message)
        for item in caught
        if "Glyph" in str(item.message) and "missing from font" in str(item.message)
    ]
    issues = [f"缺字：{message}" for message in dict.fromkeys(messages)]
    renderer = fig.canvas.get_renderer()
    width, height = fig.bbox.width, fig.bbox.height
    tick_ids = {
        id(label)
        for axis in fig.axes
        for label in (*axis.get_xticklabels(), *axis.get_yticklabels())
    }
    clipped = []
    for text in fig.findobj(mtext.Text):
        if id(text) in tick_ids or not text.get_visible() or not text.get_text().strip():
            continue
        box = text.get_window_extent(renderer)
        if box.x0 < -1 or box.y0 < -1 or box.x1 > width + 1 or box.y1 > height + 1:
            clipped.append(text.get_text().replace("\n", " ")[:24])
    if clipped:
        issues.append("文字可能超出画布：" + "、".join(dict.fromkeys(clipped)))
    for index, axis in enumerate(fig.axes, start=1):
        if _labels_overlap(axis.get_xticklabels(), renderer, "x"):
            issues.append(f"第 {index} 个坐标轴的 x 刻度标签重叠")
        if _labels_overlap(axis.get_yticklabels(), renderer, "y"):
            issues.append(f"第 {index} 个坐标轴的 y 刻度标签重叠")
    return issues


def resolve_output_stem(output_stem: str | Path) -> Path:
    """解析导出路径，并禁止把任务产物写回 Skill 目录。"""

    stem = Path(output_stem).expanduser().resolve()
    if stem.suffix.lower() in {".svg", ".png", ".pdf"}:
        stem = stem.with_suffix("")
    try:
        stem.relative_to(SKILL_ROOT)
    except ValueError:
        pass
    else:
        raise ValueError("图形产物必须写入 PROJECT_ROOT，不能写入 SKILL_ROOT")
    return stem


def _save_grayscale_preview(png_path: Path, dpi: int) -> Path:
    import matplotlib.image as image_io
    import numpy as np

    pixels = image_io.imread(png_path)
    rgb = pixels[..., :3]
    if pixels.shape[-1] == 4:
        alpha = pixels[..., 3:4]
        rgb = rgb * alpha + (1 - alpha)
    grayscale = np.dot(rgb, (0.2126, 0.7152, 0.0722))
    output = png_path.parent / "_qa" / f"{png_path.stem}_grayscale.png"
    output.parent.mkdir(parents=True, exist_ok=True)
    image_io.imsave(output, grayscale, cmap="gray", vmin=0, vmax=1, dpi=dpi)
    return output


def export_figure(
    fig,
    output_stem: str | Path,
    *,
    dpi: int = 300,
    grayscale_preview: bool = True,
    strict_layout: bool = True,
) -> dict[str, str]:
    """按固定物理尺寸导出 SVG、PNG 和可选灰度质检图。"""

    if dpi < 300:
        raise ValueError("论文图 PNG 的 dpi 不能低于 300")
    layout_issues = audit_layout(fig)
    if strict_layout and layout_issues:
        raise ValueError("版面预检未通过：" + "；".join(layout_issues))
    stem = resolve_output_stem(output_stem)
    stem.parent.mkdir(parents=True, exist_ok=True)
    svg_path = stem.with_suffix(".svg")
    png_path = stem.with_suffix(".png")
    # 不使用 bbox_inches='tight'，否则会改变图表契约中的最终物理尺寸。
    fig.savefig(svg_path)
    fig.savefig(png_path, dpi=dpi)
    outputs = {"svg": str(svg_path), "png": str(png_path)}
    if grayscale_preview:
        outputs["grayscale"] = str(_save_grayscale_preview(png_path, dpi))
    return outputs


__all__ = [
    "COLOR_SEQUENCE",
    "PALETTE",
    "WIDTHS_IN",
    "add_panel_labels",
    "apply_publication_style",
    "audit_layout",
    "choose_font",
    "export_figure",
    "figure_size",
    "resolve_output_stem",
]
