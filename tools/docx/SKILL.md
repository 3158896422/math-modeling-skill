---
name: docx
description: "Use this skill whenever the user wants to create, read, edit, or manipulate Word documents (.docx files). Triggers include: any mention of \"Word doc\", \"word document\", \".docx\", or requests to produce professional documents with formatting like tables of contents, headings, page numbers, or letterheads. Also use when extracting or reorganizing content from .docx files, inserting or replacing images in documents, performing find-and-replace in Word files, working with tracked changes or comments, or converting content into a polished Word document. If the user asks for a \"report\", \"memo\", \"letter\", \"template\", or similar deliverable as a Word or .docx file, use this skill. Do NOT use for PDFs, spreadsheets, Google Docs, or general coding tasks unrelated to document generation."
license: Proprietary. LICENSE.txt has complete terms
---

# DOCX creation, editing, and analysis

## Overview

A .docx file is a ZIP archive containing XML files.

## Quick Reference

| Task | Approach |
|------|----------|
| Read/analyze content | `pandoc` or unpack for raw XML |
| Create new document | Use `python-docx` - see Creating New Documents below |
| Create math-modeling paper | Use `scripts/paper_format.py`; use `scripts/equations.py replace` only for existing placeholders |
| Check environment/output | Run `scripts/check_env.py` and `scripts/self_check.py` |
| Edit existing document | Unpack → edit XML → repack - see Editing Existing Documents below |

### Converting .doc to .docx

Legacy `.doc` files must be converted before editing:

```bash
python scripts/office/soffice.py --headless --convert-to docx document.doc
```

### Reading Content

```bash
# Text extraction with tracked changes
pandoc --track-changes=all document.docx -o output.md

# Raw XML access
python scripts/office/unpack.py document.docx unpacked/
```

### Converting to Images

```bash
python scripts/office/soffice.py --headless --convert-to pdf document.docx
pdftoppm -jpeg -r 150 document.pdf page
```

### Accepting Tracked Changes

To produce a clean document with all tracked changes accepted (requires LibreOffice):

```bash
python scripts/accept_changes.py input.docx output.docx
```

---

## Creating New Documents

> **📌 推荐方案：python-docx（首选）** — 文档创建、公式处理、验证全流程 Python 完成，无需切换语言。
>
> **备选方案：docx-js（次选）** — 如遇 python-docx 不支持的场景（如复杂 OMML 公式原生注入），可回退到 npm docx + Python 后处理。

数学建模论文优先复用 `scripts/paper_format.py`，格式依据 `references/roles/论文手/references/论文格式规范.md`。LaTeX 只用于公式，不用于整篇论文排版。

---

### 🐍 python-docx（推荐）

Install: `pip install python-docx lxml`

```python
from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING, WD_BREAK
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn, nsdecls
from docx.oxml import parse_xml

doc = Document()
# ... add content ...
doc.save("output.docx")
```

#### Page Size
```python
section = doc.sections[0]
section.page_width = Inches(8.5)
section.page_height = Inches(11)
section.left_margin = Inches(1)
section.right_margin = Inches(1)
section.top_margin = Inches(1)
section.bottom_margin = Inches(1)
```

| Paper | Width | Height | Content (cm margins) |
|-------|-------|--------|---------------------|
| US Letter | 8.5" | 11" | 6.5" (1" margins) |
| A4 | 8.27" / 21cm | 11.69" / 29.7cm | 14.66cm (3.17cm margins) |

**国赛中文论文（从 论文模板.docx 提取）：**
```python
section = doc.sections[0]
section.page_width  = Cm(21)
section.page_height = Cm(29.7)
section.left_margin   = Cm(3.17)
section.right_margin  = Cm(3.17)
section.top_margin    = Cm(2.54)
section.bottom_margin = Cm(2.54)
```

Landscape:
```python
section.page_width = Inches(11)
section.page_height = Inches(8.5)
```

#### Styles & Fonts

**⚠️ 关键：必须显式设置东亚字体，否则 Word 回退为 MS 明朝/ＭＳ 明朝。**

python-docx 默认使用文档主题引用字体（theme reference），当系统无对应主题时回退到日文字体。必须移除 theme 属性，显式指定 `w:eastAsia`。

```python
def set_ea_font(element, latin='Times New Roman', ea='宋体'):
    """显式设置英文字体和东亚字体，移除 theme 引用（避免 MS 明朝回退）。"""
    rPr = element.find(qn('w:rPr'))
    if rPr is None:
        rPr = parse_xml('<w:rPr ' + nsdecls('w') + '/>')
        element.insert(0, rPr)
    rFonts = rPr.find(qn('w:rFonts'))
    if rFonts is None:
        rFonts = parse_xml('<w:rFonts ' + nsdecls('w') + '/>')
        rPr.insert(0, rFonts)
    rFonts.set(qn('w:ascii'), latin)
    rFonts.set(qn('w:hAnsi'), latin)
    rFonts.set(qn('w:eastAsia'), ea)
    for attr in ['w:asciiTheme', 'w:hAnsiTheme', 'w:eastAsiaTheme', 'w:cstheme']:
        try:
            del rFonts.attrib[qn(attr)]
        except KeyError:
            pass

# Normal 样式：全文默认
normal = doc.styles['Normal']
normal.font.size = Pt(12)
set_ea_font(normal, 'Times New Roman', '宋体')

# 一级标题
hs = doc.styles['Heading 1']
hs.font.size = Pt(16); hs.font.bold = True
set_ea_font(hs, '黑体', '黑体')

# 使用
def make_run(p, text, latin='Times New Roman', ea='宋体', size=None, bold=None):
    """添加 run 时自动设置东亚字体。"""
    r = p.add_run(text)
    if size: r.font.size = size
    if bold is not None: r.font.bold = bold
    set_ea_font(r, latin, ea)
    return r
```

**数学建模论文格式速查表（从 论文模板.docx 提取）：**

| 元素 | 字体 | 字号 | 行距 | 首行缩进 | 段前段后 |
|------|------|------|------|----------|---------|
| 论文题目 | 黑体 | 四号/14pt | 1.25x | 无 | 0 |
| 摘 要(标题) | 黑体 | 四号/14pt | 1.25x | 无 | 0 |
| 摘要正文 | 宋体 | 小四/12pt | 1.25x | 2字符/304800EMU | 0 |
| 关键词 | 宋体 | 小四/12pt | 1.25x | **顶格无缩进** | 0 |
| 一级标题 | — | 三号/16pt | 1.25x | 无 | 0 |
| 二级标题 | — | 四号/14pt | 1.25x | 无 | 0 |
| 正文 | 宋体 | 小四/12pt | 1.25x | 2字符/304800EMU | 0 |
| 附录 | 宋体 | 三号/16pt | 1.25x | 无 | 0 |

#### Paragraphs & Text Runs

使用 `make_run` 替代直接 `p.add_run()` 以确保东亚字体正确。

```python
def add_body(doc, text):
    """正文段落辅助函数：宋体 小四 首行缩进2字符 1.25x行距"""
    p = doc.add_paragraph()
    p.paragraph_format.line_spacing = 1.25
    p.paragraph_format.first_line_indent = 304800  # 2字符缩进 (EMU)
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(0)
    make_run(p, text, ea='宋体', size=Pt(12))
    return p

def add_heading1(doc, text):
    """一级标题：三号(16pt) 加粗 1.25x 无缩进"""
    p = doc.add_paragraph()
    p.paragraph_format.line_spacing = 1.25
    make_run(p, text, ea='黑体', size=Pt(16), bold=True)
    return p

def add_heading2(doc, text):
    """二级标题：四号(14pt) 1.25x 无缩进"""
    p = doc.add_paragraph()
    p.paragraph_format.line_spacing = 1.25
    make_run(p, text, ea='黑体', size=Pt(14))
    return p

# 使用
add_heading1(doc, '一、问题重述')
add_heading2(doc, '1.1 问题背景')
add_body(doc, '随着城市化进程加快，应急设施选址问题...')
```

#### Lists — 通过 XML 注入实现

**⚠️ python-docx 创建文档时会自动生成默认编号定义。必须先清除再添加自定义定义，否则编号会冲突。**

**⚠️ `numPr` 必须插入在 `ind`/`spacing` 之前（OOXML 元素顺序要求）。**

```python
NSP = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'

def init_numbering(doc):
    """清除默认编号，添加自定义定义。先加所有 abstractNum，再加所有 num（schema 顺序）。"""
    np = doc.part.numbering_part._element
    for child in list(np):
        np.remove(child)
    # abstractNum 0 (bullet)
    np.append(parse_xml(
        f'<w:abstractNum w:abstractNumId="0" xmlns:w="{NSP}">'
        f'  <w:multiLevelType w:val="hybridMultilevel"/>'
        f'  <w:lvl w:ilvl="0">'
        f'    <w:start w:val="1"/><w:numFmt w:val="bullet"/>'
        f'    <w:lvlText w:val="●"/><w:lvlJc w:val="left"/>'
        f'    <w:pPr><w:ind w:left="720" w:hanging="360"/></w:pPr>'
        f'  </w:lvl></w:abstractNum>'))
    # abstractNum 1 (decimal)
    np.append(parse_xml(
        f'<w:abstractNum w:abstractNumId="1" xmlns:w="{NSP}">'
        f'  <w:multiLevelType w:val="hybridMultilevel"/>'
        f'  <w:lvl w:ilvl="0">'
        f'    <w:start w:val="1"/><w:numFmt w:val="decimal"/>'
        f'    <w:lvlText w:val="%1."/><w:lvlJc w:val="left"/>'
        f'    <w:pPr><w:ind w:left="720" w:hanging="360"/></w:pPr>'
        f'  </w:lvl></w:abstractNum>'))
    # num 1 → abstractNum 0 (bullet)
    np.append(parse_xml(
        f'<w:num w:numId="1" xmlns:w="{NSP}"><w:abstractNumId w:val="0"/></w:num>'))
    # num 2 → abstractNum 1 (decimal)
    np.append(parse_xml(
        f'<w:num w:numId="2" xmlns:w="{NSP}"><w:abstractNumId w:val="1"/></w:num>'))

def list_item(doc, text, num_id=1, level=0):
    p = doc.add_paragraph(text)
    # 先设置格式，再插入 numPr
    pPr = p._element.get_or_add_pPr()
    numPr = parse_xml(
        f'<w:numPr xmlns:w="{NSP}">'
        f'  <w:ilvl w:val="{level}"/><w:numId w:val="{num_id}"/>'
        f'</w:numPr>')
    # CRITICAL: numPr 必须在 ind/spacing 之前
    refs = [pPr.find(qn('w:ind')), pPr.find(qn('w:spacing'))]
    refs = [r for r in refs if r is not None]
    if refs:
        pPr.insert(min(pPr.index(r) for r in refs), numPr)
    else:
        pPr.append(numPr)
    return p
```

#### Tables

**⚠️ 使用 `type=auto` 宽度（而非固定 DXA），由列宽度自动撑开。OOXML 元素顺序要求：`tblW` 必须在所有其他 `tblPr` 子元素之前。**

```python
def _set_cell_border(cell, **edges):
    parts = ''.join(
        f'<w:{e} w:val="single" w:sz="{a.get("sz",4)}" '
        f'w:color="{a.get("color","000000")}" xmlns:w="{NSP}"/>'
        for e, a in edges.items())
    cell._tc.get_or_add_tcPr().append(parse_xml(
        f'<w:tcBorders xmlns:w="{NSP}">{parts}</w:tcBorders>'))

def set_table_auto_width(tblPr):
    """移除已有 tblW，设为 auto 宽度。"""
    existing = tblPr.find(qn('w:tblW'))
    if existing is not None:
        tblPr.remove(existing)
    tblPr.insert(0, parse_xml(
        f'<w:tblW w:w="0" w:type="auto" xmlns:w="{NSP}"/>'))

table = doc.add_table(rows=3, cols=2)
table.alignment = WD_TABLE_ALIGNMENT.CENTER
set_table_auto_width(table._tbl.tblPr)

for i, h in enumerate(["A", "B"]):
    c = table.rows[0].cells[i]; c.text = h
    c.width = Inches(2)  # 列宽决定表格实际宽度
    c._tc.get_or_add_tcPr().append(parse_xml(
        f'<w:shd w:fill="D5E8F0" w:val="clear" xmlns:w="{NSP}"/>'))
    _set_cell_border(c, top={"sz":8,"color":"000000"}, bottom={"sz":4,"color":"000000"})
```

#### Three-Line Tables（三线表）

**⚠️ 关键：必须先设置 auto 宽度，再插入 `tblBorders`。`tblBorders` 必须在 `tblLook` 之前（OOXML 扩展类型顺序）。tblBorders 子元素顺序：`top → start → left → bottom → end → right → insideH → insideV`。**

```python
def three_line_table(doc, headers, data, col_widths_dxa=None):
    """三线表：自动宽度 + 按列宽设定 + 元素顺序严格遵循 schema。"""
    n = len(headers)
    table = doc.add_table(rows=1 + len(data), cols=n)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    tblPr = table._tbl.tblPr

    # Step 1: 设置 auto 宽度（必须为 tblPr 第一个子元素）
    set_table_auto_width(tblPr)

    # Step 2: 插入 tblBorders（必须在 tblLook 之前）
    tbl_borders = parse_xml(
        f'<w:tblBorders xmlns:w="{NSP}">'
        f'  <w:top w:val="none"/><w:start w:val="none"/>'
        f'  <w:left w:val="none"/><w:bottom w:val="none"/>'
        f'  <w:end w:val="none"/><w:right w:val="none"/>'
        f'  <w:insideH w:val="none"/><w:insideV w:val="none"/>'
        f'</w:tblBorders>')
    look = tblPr.find(qn('w:tblLook'))
    if look is not None:
        tblPr.insert(tblPr.index(look), tbl_borders)
    else:
        tblPr.append(tbl_borders)

    # Header row: 粗顶线 + 细底线段
    for i, h in enumerate(headers):
        c = table.rows[0].cells[i]; c.text = h
        if col_widths_dxa: c.width = col_widths_dxa[i]
        _set_cell_border(c, top={"sz":12,"color":"000000"},
                         bottom={"sz":8,"color":"000000"})
        for p in c.paragraphs:
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.paragraph_format.line_spacing = 1.25
    # Body rows: 仅最后一行有粗底线
    for ri, row in enumerate(data):
        last = ri == len(data) - 1
        for ci, val in enumerate(row):
            c = table.rows[ri+1].cells[ci]; c.text = str(val)
            if col_widths_dxa: c.width = col_widths_dxa[ci]
            if last:
                _set_cell_border(c, bottom={"sz":12,"color":"000000"})
            for p in c.paragraphs:
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                p.paragraph_format.line_spacing = 1.25

# 使用
three_line_table(doc,
    ['符号', '说明', '单位'],
    [['n', '样本总数', '个'], ['N', '样本数', '个']],
    col_widths_dxa=[1800, 4800, 1400])
```
            for p in c.paragraphs: p.alignment = WD_ALIGN_PARAGRAPH.CENTER

three_line_table(doc, ["符号", "说明", "单位"],
    [["x_i", "第 i 个样本", "-"], ["N", "样本总数", "个"]])
```

三线表规范：仅顶线（粗）→ 表头底线（细）→ 表末底线（粗），无左右/竖线。

#### Images
```python
p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
p.add_run().add_picture("figure.png", width=Inches(4.5))
```

#### References / Citations

**⚠️ 交叉引用要求**：正文中的引用标注 `[1]` 必须与参考文献列表严格对应。由于 python-docx 不支持 Word 的原生交叉引用域，采用纯文本编号方案：

```python
# 参考文献列表（按正文首次出现顺序编号）
references = [
    '[1] Daskin M S. Network and Discrete Location[M]. New York: John Wiley & Sons, 1995.',
    '[2] Deb K, et al. A fast NSGA-II[J]. IEEE Trans. on Evolutionary Computation, 2002, 6(2): 182-197.',
    '[3] Snyder L V. Facility location under uncertainty: a review[J]. IIE Trans., 2006, 38(7): 547-564.',
]

def add_citation(doc, ref_num):
    """在正文中添加引用标记 [n]。"""
    p = doc.add_paragraph()
    r = p.add_run(f'[{ref_num}]')
    r.font.size = Pt(12)
    return p

def add_references_section(doc, title, refs):
    """在文末生成参考文献章节。"""
    add_heading1(doc, title)
    for ref in refs:
        p = doc.add_paragraph()
        p.paragraph_format.line_spacing = 1.25
        r = p.add_run(ref)
        r.font.size = Pt(12)
```

**撰写时的引用流程**：
1. 正文中首次引用文献时标注 `[1]`、`[2]`...
2. 再次引用同一文献时复用首次编号
3. 参考文献列表按 `[1]`, `[2]`, `[3]`... 顺序排列（非字母顺序）
4. 自审时逐条核验：正文章有标，参考文献有引

> **注意**：Word 的原生交叉引用（插入→引用→交叉引用）需要手动操作，不适合自动化生成。
> 纯文本 `[n]` 方案在数学建模论文中可接受且广泛使用。

#### Page Breaks
```python
doc.add_page_break()                      # 方式一
p = doc.add_paragraph()
p.add_run().add_break(WD_BREAK.PAGE)     # 方式二
p2 = doc.add_paragraph("新页内容")
p2.paragraph_format.page_break_before = True  # 方式三
```

#### Table of Contents（目录 — 须 XML 注入）
```python
def add_toc(doc):
    p = doc.add_paragraph()
    toc = f'''<w:p xmlns:w="{NSP}">
      <w:r><w:fldChar w:fldCharType="begin"/></w:r>
      <w:r><w:instrText> TOC \\o "1-3" \\h \\z \\u </w:instrText></w:r>
      <w:r><w:fldChar w:fldCharType="separate"/></w:r>
      <w:r><w:t>[在 Word 中右击 → 更新域]</w:t></w:r>
      <w:r><w:fldChar w:fldCharType="end"/></w:r>
    </w:p>'''
    doc.element.findall(qn('w:body'))[0].append(parse_xml(toc))

add_toc(doc)
```

#### Headers/Footers
```python
section = doc.sections[0]
header = section.header
header.is_linked_to_previous = False
header.paragraphs[0].add_run('论文标题')

footer = section.footer
footer.is_linked_to_previous = False
fp = footer.paragraphs[0]
fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
fp._element.append(parse_xml(
    f'<w:p xmlns:w="{NSP}">'
    f'  <w:r><w:t>第 </w:t></w:r>'
    f'  <w:r><w:fldChar w:fldCharType="begin"/></w:r>'
    f'  <w:r><w:instrText> PAGE </w:instrText></w:r>'
    f'  <w:r><w:fldChar w:fldCharType="separate"/></w:r>'
    f'  <w:r><w:fldChar w:fldCharType="end"/></w:r>'
    f'  <w:r><w:t> 页</w:t></w:r>'
    f'</w:p>'))
```

#### python-docx 关键规则
- **东亚字体必须显式设置** — 设置 `w:eastAsia` 并移除 `w:eastAsiaTheme`，否则 Word 回退为 MS 明朝
- **页尺寸即时设置** — 创建 Document 后立即修改 `section.page_width/height`
- **横排：手动互换** width/height；python-docx 不会自动调换
- **A4 纸张** — `page_width=Cm(21)`, `page_height=Cm(29.7)`, margins=`Cm(3.17)`/`Cm(2.54)`
- **不要使用 `\\n`** — 用多个 `add_paragraph()`
- **不要用 Unicode 序号字符** — 用 `init_numbering()` + `list_item()`
- **`numPr` 元素顺序** — 必须插入在 `ind`/`spacing` 之前，否则 XSD 验证报错
- **表格：用 `type=auto`** — 不要设置固定 DXA 宽度，由列宽自动撑开
- **表格：逐个设 cell.width** — 否则跨平台可能失效
- **`tblW` 必须为 `tblPr` 第一个子元素** — 用 `insert(0, ...)` 而非 `append()`
- **`tblBorders` 必须在 `tblLook` 之前** — OOXML 扩展类型顺序要求
- **`tblBorders` 子元素顺序固定** — `top → start → left → bottom → end → right → insideH → insideV`
- **编号定义：先清除默认** — python-docx 默认添加了 8 组 abstractNum/num，必须清空再自定义
- **三线表：先清除 `tblBorders`**，再逐格添加 `tcBorders`
- **公式：优先用 `paper_format.equation()`** — 只有已有占位符文档才用 `equations.py replace`
- **始终 `doc.save()`** — python-docx 内存操作，不 save 不写入

---

### 📜 docx-js（备选）

当 python-docx 无法满足需求时（如需要原生 OMML 公式直接注入），可使用 npm docx 生成再由 `equations.py` 后处理。

Install: `npm install -g docx`

#### Setup
```javascript
const { Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell, ImageRun,
        Header, Footer, AlignmentType, PageOrientation, LevelFormat, ExternalHyperlink,
        TableOfContents, HeadingLevel, BorderStyle, WidthType, ShadingType,
        VerticalAlign, PageNumber, PageBreak } = require('docx');

const doc = new Document({ sections: [{ children: [/* content */] }] });
Packer.toBuffer(doc).then(buffer => fs.writeFileSync("doc.docx", buffer));
```

#### Validation
After creating the file, validate it. If validation fails, unpack, fix the XML, and repack.
```bash
python scripts/office/validate.py doc.docx
```

#### Page Size

```javascript
// CRITICAL: docx-js defaults to A4, not US Letter
// Always set page size explicitly for consistent results
sections: [{
  properties: {
    page: {
      size: {
        width: 12240,   // 8.5 inches in DXA
        height: 15840   // 11 inches in DXA
      },
      margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 } // 1 inch margins
    }
  },
  children: [/* content */]
}]
```

**Common page sizes (DXA units, 1440 DXA = 1 inch):**

| Paper | Width | Height | Content Width (1" margins) |
|-------|-------|--------|---------------------------|
| US Letter | 12,240 | 15,840 | 9,360 |
| A4 (default) | 11,906 | 16,838 | 9,026 |

**Landscape orientation:** docx-js swaps width/height internally, so pass portrait dimensions and let it handle the swap:
```javascript
size: {
  width: 12240,   // Pass SHORT edge as width
  height: 15840,  // Pass LONG edge as height
  orientation: PageOrientation.LANDSCAPE  // docx-js swaps them in the XML
},
// Content width = 15840 - left margin - right margin (uses the long edge)
```

#### Styles (Override Built-in Headings)

Use Arial as the default font (universally supported). Keep titles black for readability.

```javascript
const doc = new Document({
  styles: {
    default: { document: { run: { font: "Arial", size: 24 } } }, // 12pt default
    paragraphStyles: [
      // IMPORTANT: Use exact IDs to override built-in styles
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 32, bold: true, font: "Arial" },
        paragraph: { spacing: { before: 240, after: 240 }, outlineLevel: 0 } }, // outlineLevel required for TOC
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 28, bold: true, font: "Arial" },
        paragraph: { spacing: { before: 180, after: 180 }, outlineLevel: 1 } },
    ]
  },
  sections: [{
    children: [
      new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun("Title")] }),
    ]
  }]
});
```

#### Lists (NEVER use unicode bullets)

```javascript
// ❌ WRONG - never manually insert bullet characters
new Paragraph({ children: [new TextRun("• Item")] })  // BAD
new Paragraph({ children: [new TextRun("\u2022 Item")] })  // BAD

// ✅ CORRECT - use numbering config with LevelFormat.BULLET
const doc = new Document({
  numbering: {
    config: [
      { reference: "bullets",
        levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 720, hanging: 360 } } } }] },
      { reference: "numbers",
        levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 720, hanging: 360 } } } }] },
    ]
  },
  sections: [{
    children: [
      new Paragraph({ numbering: { reference: "bullets", level: 0 },
        children: [new TextRun("Bullet item")] }),
      new Paragraph({ numbering: { reference: "numbers", level: 0 },
        children: [new TextRun("Numbered item")] }),
    ]
  }]
});

// ⚠️ Each reference creates INDEPENDENT numbering
// Same reference = continues (1,2,3 then 4,5,6)
// Different reference = restarts (1,2,3 then 1,2,3)
```

#### Tables

**CRITICAL: Tables need dual widths** - set both `columnWidths` on the table AND `width` on each cell. Without both, tables render incorrectly on some platforms.

```javascript
// CRITICAL: Always set table width for consistent rendering
// CRITICAL: Use ShadingType.CLEAR (not SOLID) to prevent black backgrounds
const border = { style: BorderStyle.SINGLE, size: 1, color: "CCCCCC" };
const borders = { top: border, bottom: border, left: border, right: border };

new Table({
  width: { size: 9360, type: WidthType.DXA }, // Always use DXA (percentages break in Google Docs)
  columnWidths: [4680, 4680], // Must sum to table width (DXA: 1440 = 1 inch)
  rows: [
    new TableRow({
      children: [
        new TableCell({
          borders,
          width: { size: 4680, type: WidthType.DXA }, // Also set on each cell
          shading: { fill: "D5E8F0", type: ShadingType.CLEAR }, // CLEAR not SOLID
          margins: { top: 80, bottom: 80, left: 120, right: 120 }, // Cell padding (internal, not added to width)
          children: [new Paragraph({ children: [new TextRun("Cell")] })]
        })
      ]
    })
  ]
})
```

**Table width calculation:**

Always use `WidthType.DXA` — `WidthType.PERCENTAGE` breaks in Google Docs.

```javascript
// Table width = sum of columnWidths = content width
// US Letter with 1" margins: 12240 - 2880 = 9360 DXA
width: { size: 9360, type: WidthType.DXA },
columnWidths: [7000, 2360]  // Must sum to table width
```

**Width rules:**
- **Always use `WidthType.DXA`** — never `WidthType.PERCENTAGE` (incompatible with Google Docs)
- Table width must equal the sum of `columnWidths`
- Cell `width` must match corresponding `columnWidth`
- Cell `margins` are internal padding - they reduce content area, not add to cell width
- For full-width tables: use content width (page width minus left and right margins)

#### Academic Three-Line Tables

For Chinese math-modeling papers, use proper three-line tables: top border, header-bottom border, and bottom border only. Do not draw left/right borders or internal vertical borders.

```javascript
const noBorder = { style: BorderStyle.NONE, size: 0, color: "FFFFFF" };
const strongBorder = { style: BorderStyle.SINGLE, size: 12, color: "000000" };
const thinBorder = { style: BorderStyle.SINGLE, size: 8, color: "000000" };

function threeLineCell(text, width, { header = false, lastRow = false } = {}) {
  return new TableCell({
    width: { size: width, type: WidthType.DXA },
    margins: { top: 80, bottom: 80, left: 120, right: 120 },
    borders: {
      top: header ? strongBorder : noBorder,
      bottom: header ? thinBorder : (lastRow ? strongBorder : noBorder),
      left: noBorder,
      right: noBorder,
    },
    children: [
      new Paragraph({
        alignment: AlignmentType.CENTER,
        children: [new TextRun({ text, bold: header, font: "SimSun", size: 24 })],
      }),
    ],
  });
}

new Table({
  width: { size: 9360, type: WidthType.DXA },
  columnWidths: [3120, 3120, 3120],
  borders: {
    top: noBorder,
    bottom: noBorder,
    left: noBorder,
    right: noBorder,
    insideHorizontal: noBorder,
    insideVertical: noBorder,
  },
  rows: [
    new TableRow({
      children: ["符号", "说明", "单位"].map(text =>
        threeLineCell(text, 3120, { header: true })
      ),
    }),
    new TableRow({
      children: [
        threeLineCell("x_i", 3120),
        threeLineCell("第 i 个样本", 3120),
        threeLineCell("-", 3120),
      ],
    }),
    new TableRow({
      children: [
        threeLineCell("N", 3120, { lastRow: true }),
        threeLineCell("样本总数", 3120, { lastRow: true }),
        threeLineCell("个", 3120, { lastRow: true }),
      ],
    }),
  ],
});
```

Three-line table checklist:
- Top border exists only on header cells or table top.
- Header row has a bottom border.
- Last row has the bottom border.
- Left/right/inside vertical borders are `NONE`.
- Body rows do not have internal horizontal lines unless the user template explicitly requires them.

#### Images

```javascript
// CRITICAL: type parameter is REQUIRED
new Paragraph({
  children: [new ImageRun({
    type: "png", // Required: png, jpg, jpeg, gif, bmp, svg
    data: fs.readFileSync("image.png"),
    transformation: { width: 200, height: 150 },
    altText: { title: "Title", description: "Desc", name: "Name" } // All three required
  })]
})
```

#### Equations / Math Formulas

The `npm docx` package does not natively support mathematical equations. Use the Python post-processing script to insert proper Word equations (OMML format) into generated .docx files. Equations will be editable in Word.

**Method 1 — Replace placeholders in existing .docx (推荐):**

```bash
# 安装依赖
pip install lxml python-docx

# 单条公式替换
python scripts/equations.py replace paper.docx ^
    --replace "EQ_LOSS" "\\min L(\\theta) = \\frac{1}{n}\\sum_{i=1}^{n} (y_i - \\hat{y}_i)^2" ^
    --replace "EQ_CONSTRAINT" "\\sum_{j=1}^{m} a_{ij}x_j \\leq b_i, \\quad i=1,\\ldots,p" ^
    -o paper_final.docx

# 批量替换（从 JSON 文件）
python scripts/equations.py replace paper.docx --mapping equations.json -o paper_final.docx
```

JSON 映射文件格式:
```json
{
    "EQ_LOSS": "\\min L(\\theta) = \\frac{1}{n}\\sum_{i=1}^{n} (y_i - \\hat{y}_i)^2",
    "EQ_CONSTRAINT": "\\sum_{j=1}^{m} a_{ij}x_j \\leq b_i, \\quad i=1,\\ldots,p"
}
```

**Method 2 — 从 Markdown 生成 (pandoc 后端，非论文手主流程):**

仅在用户明确要求 Markdown 全文转换时使用。数学建模论文手默认使用 `paper_format.py` 生成 Word，LaTeX 只用于公式占位符替换。

```bash
# 需要安装 pandoc: https://pandoc.org/installing.html
python scripts/equations.py generate paper.md -o paper.docx --template template.docx
```

在 Markdown 中写公式:
```markdown
损失函数定义为：

$$
\min L(\theta) = \frac{1}{n}\sum_{i=1}^{n} (y_i - \hat{y}_i)^2
$$

其中 $y_i$ 为真实值，$\hat{y}_i$ 为预测值。
```

**Preview OMML output (debug):**
```bash
python scripts/equations.py replace dummy.docx --replace "x" "E = mc^2" --show-omml
```

---

#### Page Breaks

```javascript
// CRITICAL: PageBreak must be inside a Paragraph
new Paragraph({ children: [new PageBreak()] })

// Or use pageBreakBefore
new Paragraph({ pageBreakBefore: true, children: [new TextRun("New page")] })
```

#### Table of Contents

```javascript
// CRITICAL: Headings must use HeadingLevel ONLY - no custom styles
new TableOfContents("Table of Contents", { hyperlink: true, headingStyleRange: "1-3" })
```

#### Headers/Footers

```javascript
sections: [{
  properties: {
    page: { margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 } } // 1440 = 1 inch
  },
  headers: {
    default: new Header({ children: [new Paragraph({ children: [new TextRun("Header")] })] })
  },
  footers: {
    default: new Footer({ children: [new Paragraph({
      children: [new TextRun("Page "), new TextRun({ children: [PageNumber.CURRENT] })]
    })] })
  },
  children: [/* content */]
}]
```

#### docx-js Critical Rules

- **Set page size explicitly** - docx-js defaults to A4; use US Letter (12240 x 15840 DXA) for US documents
- **Landscape: pass portrait dimensions** - docx-js swaps width/height internally; pass short edge as `width`, long edge as `height`, and set `orientation: PageOrientation.LANDSCAPE`
- **Never use `\n`** - use separate Paragraph elements
- **Never use unicode bullets** - use `LevelFormat.BULLET` with numbering config
- **PageBreak must be in Paragraph** - standalone creates invalid XML
- **ImageRun requires `type`** - always specify png/jpg/etc
- **Always set table `width` with DXA** - never use `WidthType.PERCENTAGE` (breaks in Google Docs)
- **Tables need dual widths** - `columnWidths` array AND cell `width`, both must match
- **Table width = sum of columnWidths** - for DXA, ensure they add up exactly
- **Always add cell margins** - use `margins: { top: 80, bottom: 80, left: 120, right: 120 }` for readable padding
- **Use `ShadingType.CLEAR`** - never SOLID for table shading
- **TOC requires HeadingLevel only** - no custom styles on heading paragraphs
- **Override built-in styles** - use exact IDs: "Heading1", "Heading2", etc.
- **Include `outlineLevel`** - required for TOC (0 for H1, 1 for H2, etc.)

---

## Editing Existing Documents

**Follow all 3 steps in order.**

### Step 1: Unpack
```bash
python scripts/office/unpack.py document.docx unpacked/
```
Extracts XML, pretty-prints, merges adjacent runs, and converts smart quotes to XML entities (`&#x201C;` etc.) so they survive editing. Use `--merge-runs false` to skip run merging.

### Step 2: Edit XML

Edit files in `unpacked/word/`. See XML Reference below for patterns.

**Use "Claude" as the author** for tracked changes and comments, unless the user explicitly requests use of a different name.

**Use the Edit tool directly for string replacement. Do not write Python scripts.** Scripts introduce unnecessary complexity. The Edit tool shows exactly what is being replaced.

**CRITICAL: Use smart quotes for new content.** When adding text with apostrophes or quotes, use XML entities to produce smart quotes:
```xml
<!-- Use these entities for professional typography -->
<w:t>Here&#x2019;s a quote: &#x201C;Hello&#x201D;</w:t>
```
| Entity | Character |
|--------|-----------|
| `&#x2018;` | ‘ (left single) |
| `&#x2019;` | ’ (right single / apostrophe) |
| `&#x201C;` | “ (left double) |
| `&#x201D;` | ” (right double) |

**Adding comments:** Use `comment.py` to handle boilerplate across multiple XML files (text must be pre-escaped XML):
```bash
python scripts/comment.py unpacked/ 0 "Comment text with &amp; and &#x2019;"
python scripts/comment.py unpacked/ 1 "Reply text" --parent 0  # reply to comment 0
python scripts/comment.py unpacked/ 0 "Text" --author "Custom Author"  # custom author name
```
Then add markers to document.xml (see Comments in XML Reference).

### Step 3: Pack
```bash
python scripts/office/pack.py unpacked/ output.docx --original document.docx
```
Validates with auto-repair, condenses XML, and creates DOCX. Use `--validate false` to skip.

**Auto-repair will fix:**
- `durableId` >= 0x7FFFFFFF (regenerates valid ID)
- Missing `xml:space="preserve"` on `<w:t>` with whitespace

**Auto-repair won't fix:**
- Malformed XML, invalid element nesting, missing relationships, schema violations

### Common Pitfalls

- **Replace entire `<w:r>` elements**: When adding tracked changes, replace the whole `<w:r>...</w:r>` block with `<w:del>...<w:ins>...` as siblings. Don't inject tracked change tags inside a run.
- **Preserve `<w:rPr>` formatting**: Copy the original run's `<w:rPr>` block into your tracked change runs to maintain bold, font size, etc.

---

## XML Reference

### Schema Compliance

- **Element order in `<w:pPr>`**: `<w:pStyle>`, `<w:numPr>`, `<w:spacing>`, `<w:ind>`, `<w:jc>`, `<w:rPr>` last
- **Whitespace**: Add `xml:space="preserve"` to `<w:t>` with leading/trailing spaces
- **RSIDs**: Must be 8-digit hex (e.g., `00AB1234`)

### Tracked Changes

**Insertion:**
```xml
<w:ins w:id="1" w:author="Claude" w:date="2025-01-01T00:00:00Z">
  <w:r><w:t>inserted text</w:t></w:r>
</w:ins>
```

**Deletion:**
```xml
<w:del w:id="2" w:author="Claude" w:date="2025-01-01T00:00:00Z">
  <w:r><w:delText>deleted text</w:delText></w:r>
</w:del>
```

**Inside `<w:del>`**: Use `<w:delText>` instead of `<w:t>`, and `<w:delInstrText>` instead of `<w:instrText>`.

**Minimal edits** - only mark what changes:
```xml
<!-- Change "30 days" to "60 days" -->
<w:r><w:t>The term is </w:t></w:r>
<w:del w:id="1" w:author="Claude" w:date="...">
  <w:r><w:delText>30</w:delText></w:r>
</w:del>
<w:ins w:id="2" w:author="Claude" w:date="...">
  <w:r><w:t>60</w:t></w:r>
</w:ins>
<w:r><w:t> days.</w:t></w:r>
```

**Deleting entire paragraphs/list items** - when removing ALL content from a paragraph, also mark the paragraph mark as deleted so it merges with the next paragraph. Add `<w:del/>` inside `<w:pPr><w:rPr>`:
```xml
<w:p>
  <w:pPr>
    <w:numPr>...</w:numPr>  <!-- list numbering if present -->
    <w:rPr>
      <w:del w:id="1" w:author="Claude" w:date="2025-01-01T00:00:00Z"/>
    </w:rPr>
  </w:pPr>
  <w:del w:id="2" w:author="Claude" w:date="2025-01-01T00:00:00Z">
    <w:r><w:delText>Entire paragraph content being deleted...</w:delText></w:r>
  </w:del>
</w:p>
```
Without the `<w:del/>` in `<w:pPr><w:rPr>`, accepting changes leaves an empty paragraph/list item.

**Rejecting another author's insertion** - nest deletion inside their insertion:
```xml
<w:ins w:author="Jane" w:id="5">
  <w:del w:author="Claude" w:id="10">
    <w:r><w:delText>their inserted text</w:delText></w:r>
  </w:del>
</w:ins>
```

**Restoring another author's deletion** - add insertion after (don't modify their deletion):
```xml
<w:del w:author="Jane" w:id="5">
  <w:r><w:delText>deleted text</w:delText></w:r>
</w:del>
<w:ins w:author="Claude" w:id="10">
  <w:r><w:t>deleted text</w:t></w:r>
</w:ins>
```

### Comments

After running `comment.py` (see Step 2), add markers to document.xml. For replies, use `--parent` flag and nest markers inside the parent's.

**CRITICAL: `<w:commentRangeStart>` and `<w:commentRangeEnd>` are siblings of `<w:r>`, never inside `<w:r>`.**

```xml
<!-- Comment markers are direct children of w:p, never inside w:r -->
<w:commentRangeStart w:id="0"/>
<w:del w:id="1" w:author="Claude" w:date="2025-01-01T00:00:00Z">
  <w:r><w:delText>deleted</w:delText></w:r>
</w:del>
<w:r><w:t> more text</w:t></w:r>
<w:commentRangeEnd w:id="0"/>
<w:r><w:rPr><w:rStyle w:val="CommentReference"/></w:rPr><w:commentReference w:id="0"/></w:r>

<!-- Comment 0 with reply 1 nested inside -->
<w:commentRangeStart w:id="0"/>
  <w:commentRangeStart w:id="1"/>
  <w:r><w:t>text</w:t></w:r>
  <w:commentRangeEnd w:id="1"/>
<w:commentRangeEnd w:id="0"/>
<w:r><w:rPr><w:rStyle w:val="CommentReference"/></w:rPr><w:commentReference w:id="0"/></w:r>
<w:r><w:rPr><w:rStyle w:val="CommentReference"/></w:rPr><w:commentReference w:id="1"/></w:r>
```

### Images

1. Add image file to `word/media/`
2. Add relationship to `word/_rels/document.xml.rels`:
```xml
<Relationship Id="rId5" Type=".../image" Target="media/image1.png"/>
```
3. Add content type to `[Content_Types].xml`:
```xml
<Default Extension="png" ContentType="image/png"/>
```
4. Reference in document.xml:
```xml
<w:drawing>
  <wp:inline>
    <wp:extent cx="914400" cy="914400"/>  <!-- EMUs: 914400 = 1 inch -->
    <a:graphic>
      <a:graphicData uri=".../picture">
        <pic:pic>
          <pic:blipFill><a:blip r:embed="rId5"/></pic:blipFill>
        </pic:pic>
      </a:graphicData>
    </a:graphic>
  </wp:inline>
</w:drawing>
```

---

## Dependencies

- **python-docx**: `pip install python-docx` — **首选方案**，完整的 .docx 创建、编辑、公式后处理
- **docx** (npm): `npm install -g docx` — **备选方案**，python-docx 不支持的场景下回退使用
- **pandoc**: Text extraction, Markdown→docx equation conversion
- **LibreOffice**: PDF conversion, accepting tracked changes (auto-configured for sandboxed environments via `scripts/office/soffice.py`)
- **Poppler**: `pdftoppm` for images
- **lxml**: `pip install lxml` — XML processing for equation insertion and validation
