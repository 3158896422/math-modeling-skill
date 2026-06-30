#!/usr/bin/env python3
"""Tiny python-docx helpers for the default math-modeling paper format."""

import re
import sys
import uuid
from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt
from lxml import etree


def set_run_font(run, font="宋体", size=12, bold=False):
    run.font.name = font
    run.font.size = Pt(size)
    run.font.bold = bold
    r_fonts = run._element.get_or_add_rPr().get_or_add_rFonts()
    r_fonts.set(qn("w:ascii"), "Times New Roman")
    r_fonts.set(qn("w:hAnsi"), "Times New Roman")
    r_fonts.set(qn("w:eastAsia"), font)
    return run


def setup_page(doc):
    section = doc.sections[0]
    section.page_width = Cm(21)
    section.page_height = Cm(29.7)
    section.top_margin = Cm(2.54)
    section.bottom_margin = Cm(2.54)
    section.left_margin = Cm(3.18)
    section.right_margin = Cm(3.18)


def paragraph(doc, text="", align=None, first_line=False, line_spacing=1.25):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(0)
    p.paragraph_format.line_spacing = line_spacing
    if first_line:
        p.paragraph_format.first_line_indent = Pt(24)
    if align is not None:
        p.alignment = align
    if text:
        set_run_font(p.add_run(text))
    return p


def title(doc, text):
    p = paragraph(doc, align=WD_ALIGN_PARAGRAPH.CENTER)
    set_run_font(p.add_run(text), "黑体", 14, False)
    return p


def abstract_title(doc):
    return title(doc, "摘 要")


def body(doc, text):
    return paragraph(doc, text, first_line=True)


def _latex2omml(latex):
    try:
        from .equations import latex2omml
    except ImportError:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from equations import latex2omml
    return latex2omml(latex)


def equation(doc, latex):
    p = paragraph(doc, align=WD_ALIGN_PARAGRAPH.CENTER)
    math_para = OxmlElement("m:oMathPara")
    math = OxmlElement("m:oMath")
    for child in etree.fromstring(_latex2omml(latex)):
        math.append(child)
    math_para.append(math)
    p._element.append(math_para)
    return p


def equation_placeholder(doc, latex, prefix="EQ"):
    placeholder = f"{prefix}_{uuid.uuid4().hex[:8].upper()}"
    body(doc, placeholder)
    return placeholder, latex


def keywords(doc, text):
    paragraph(doc)
    p = paragraph(doc)
    set_run_font(p.add_run("关键词："), bold=True)
    set_run_font(p.add_run(text))
    return p


def heading1(doc, text):
    p = paragraph(doc, align=WD_ALIGN_PARAGRAPH.CENTER)
    p.paragraph_format.page_break_before = True
    set_run_font(p.add_run(text), size=16, bold=True)
    return p


def heading2(doc, text):
    p = paragraph(doc)
    set_run_font(p.add_run(text), size=14, bold=False)
    return p


def heading3(doc, text):
    p = paragraph(doc, align=WD_ALIGN_PARAGRAPH.JUSTIFY)
    set_run_font(p.add_run(text), size=12, bold=True)
    return p


def page_break(doc):
    doc.add_page_break()


def section_break(doc):
    doc.add_section(WD_SECTION.NEW_PAGE)


def image(doc, path, width_cm=12):
    p = paragraph(doc, align=WD_ALIGN_PARAGRAPH.CENTER)
    with open(path, "rb") as image_file:
        p.add_run().add_picture(image_file, width=Cm(width_cm))
    return p


def figure_caption(doc, text):
    p = paragraph(doc, align=WD_ALIGN_PARAGRAPH.CENTER)
    set_run_font(p.add_run(text), size=10)
    return p


def count_chinese_chars(doc):
    text = "\n".join(p.text for p in doc.paragraphs)
    return len(re.findall(r"[\u4e00-\u9fff]", text))


def _border(val="nil", size="0"):
    elem = OxmlElement("w:bottom")
    elem.set(qn("w:val"), val)
    elem.set(qn("w:sz"), size)
    elem.set(qn("w:space"), "0")
    elem.set(qn("w:color"), "000000" if val != "nil" else "auto")
    return elem


def _set_cell_bottom(cell, val="nil", size="0"):
    tc_pr = cell._tc.get_or_add_tcPr()
    borders = tc_pr.find(qn("w:tcBorders"))
    if borders is None:
        borders = OxmlElement("w:tcBorders")
        tc_pr.append(borders)
    for old in list(borders):
        if old.tag == qn("w:bottom"):
            borders.remove(old)
    borders.append(_border(val, size))


def _set_table_borders(table):
    tbl_pr = table._tbl.tblPr
    borders = tbl_pr.find(qn("w:tblBorders"))
    if borders is not None:
        tbl_pr.remove(borders)
    borders = OxmlElement("w:tblBorders")
    for name, val, size in [
        ("top", "single", "12"),
        ("start", "nil", "0"),
        ("left", "nil", "0"),
        ("bottom", "single", "12"),
        ("end", "nil", "0"),
        ("right", "nil", "0"),
        ("insideH", "nil", "0"),
        ("insideV", "nil", "0"),
    ]:
        elem = OxmlElement(f"w:{name}")
        elem.set(qn("w:val"), val)
        elem.set(qn("w:sz"), size)
        elem.set(qn("w:space"), "0")
        elem.set(qn("w:color"), "000000" if val != "nil" else "auto")
        borders.append(elem)
    tbl_look = tbl_pr.find(qn("w:tblLook"))
    if tbl_look is None:
        tbl_pr.append(borders)
    else:
        tbl_pr.insert(tbl_pr.index(tbl_look), borders)


def three_line_table(doc, rows):
    table = doc.add_table(rows=len(rows), cols=len(rows[0]))
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    _set_table_borders(table)
    for row_i, row in enumerate(rows):
        for col_i, text in enumerate(row):
            cell = table.cell(row_i, col_i)
            cell.text = ""
            p = cell.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            set_run_font(p.add_run(str(text)), size=12, bold=(row_i == 0))
            if row_i == 0:
                _set_cell_bottom(cell, "single", "4")
    return table


def new_document():
    doc = Document()
    zoom = doc.settings.element.find(qn("w:zoom"))
    if zoom is not None and zoom.get(qn("w:percent")) is None:
        zoom.set(qn("w:percent"), "100")
    setup_page(doc)
    return doc


if __name__ == "__main__":
    doc = new_document()
    title(doc, "论文题目")
    abstract_title(doc)
    body(doc, "总体介绍")
    keywords(doc, "优化；预测；评价")
    heading1(doc, "一、问题重述")
    heading2(doc, "1.1 问题背景")
    heading3(doc, "问题一的建立")
    three_line_table(doc, [["符号", "说明", "单位"], ["x", "变量", "-"]])
    doc.save("paper_format_demo.docx")
