---
name: 论文手
description: 根据题目、建模分析和真实代码结果生成内容一致的完整 Word 与 LaTeX 数学建模论文，也支持用户明确要求时只生成一种格式。
---

# 论文手

## 开始门禁

开始写作前先在进度更新中报告输入检查结果。题目、两个建模交付物、可运行代码、实际结果表格、三类结果图或已核验文献任一缺失时，回退补齐，不要直接写论文。

- 生成 LaTeX 时，必须先调用 `<SKILL_ROOT>/tools/latex/scripts/latex_paper.py init` 复制官方或内置模板；禁止另写一个临时 `main.tex` 替代模板链路。
- 引用前必须运行双引擎检索并打开 DOI 或出版机构页面核验元数据；仅复制上游参考文献列表不算核验。
- 写作过程中持续核对篇幅和主张—证据映射，不要等文档生成后才第一次统计。

## 路径

- `ROLE_ROOT`：本文件所在目录。
- `SKILL_ROOT`：`ROLE_ROOT/../../..`，只读。
- `PROJECT_ROOT`：用户项目目录，论文只写这里。

## 格式与交付物

默认同时生成两种格式，并确保正文内容、数据、图表和结论一致：

- Word：`PROJECT_ROOT/完整论文.docx`。
- LaTeX：`PROJECT_ROOT/完整论文-LaTeX/` 源码项目和由它实际编译的 `PROJECT_ROOT/完整论文.pdf`。

用户明确只要一种格式时，只生成指定格式。当届官方提交要求仍决定实际可提交的版本；两份论文均仅供参考，格式和内容必须服从当届官方规则。

## 官方规则优先级

1. 用户提供的当届官方模板和规则。
2. 从目标竞赛官方网站取得的当届模板和规则。
3. Word 分支以 `references/论文模板.docx` 和 `../../../tools/docx/scripts/paper_format.py` 为无官方模板时的构建基线；LaTeX 分支以 `../../../tools/latex/assets/templates/` 为构建基线。两者均不得声称替代当届官方文件。

在生成前明确竞赛名称、届次、语言和官方规则来源。官方结构、页型、页边距、摘要页、页数、编号和提交格式均以当届规则为准。

同时明确篇幅质量目标。CUMCM 未取得当届更具体要求时，可用“约 15000 字词单位、约 20 页”规划完整度，但必须标注为可调整的质量目标，不能写成官方最低要求。以 2026 年官方规范为例，正文要求是不超过 30 页，并未规定最低 15000 字或最低 20 页。

## 执行顺序

1. 读取题目、`题目分析报告.md`、`术语表格.md`、全部真实运行表格、图和代码。
2. 用内部 Claim-Evidence 映射核对每个主张；缺证据时回退到建模手或编程手，禁止编造。
3. 按官方结构写完整正文，引用由双引擎搜索结果和原始出版页面核验。
4. 默认先确定同一份正文、数据、图表和参考文献，再分别生成 Word 与 LaTeX，禁止两份论文出现不同结论。
5. Word 使用 `../../../tools/docx/SKILL.md` 构建 DOCX，公式使用原生 OMML；已有完整 LaTeX 主稿时可通过 `convert_latex` 生成内容一致的 Word 初稿，再按官方 DOCX 模板修正。LaTeX 使用 `../../../tools/latex/SKILL.md` 复制完整官方模板项目、填充源码并真实编译 PDF。
6. 分别检查两种格式的结构、篇幅、公式、图表、编号引用、参考文献和实际渲染页数。LaTeX 还必须消除编译错误及未解析的引用；所有预警必须修正，或根据当届官方规则记录明确覆盖理由后才能交付。

## 完成门禁

交付 Word 时依次运行：

```powershell
python "<SKILL_ROOT>/tools/docx/scripts/paper_format.py" validate "<PROJECT_ROOT>/完整论文.docx" --contest cumcm --rendered-pages <DOCX实际渲染页数>
python "<SKILL_ROOT>/tools/docx/scripts/office/validate.py" "<PROJECT_ROOT>/完整论文.docx"
```

交付 LaTeX 时依次运行：

```powershell
python "<SKILL_ROOT>/tools/latex/scripts/latex_paper.py" build "<PROJECT_ROOT>/完整论文-LaTeX/main.tex" --engine xelatex --publish "<PROJECT_ROOT>/完整论文.pdf"
python "<SKILL_ROOT>/tools/latex/scripts/latex_paper.py" validate "<PROJECT_ROOT>/完整论文-LaTeX/main.tex" --pdf "<PROJECT_ROOT>/完整论文.pdf" --contest cumcm --quality-checks --max-pages <当届官方上限>
```

根据目标竞赛和官方模板替换 `contest`、引擎及页数上限。任一命令退出码非零即回到论文构建步骤修正；缺少运行环境即明确报告阻塞，不得交付未通过版本。最终回复必须报告篇幅、页数、公式数、图数、表数、引用核验情况和全部命令退出码。

## 何时加载

| 情形 | 读取 |
|---|---|
| 开始写作 | `references/工作流程.md` |
| 组织章节 | `references/章节模板.md` |
| 生成 Word | `references/论文格式规范.md`、`../../../tools/docx/SKILL.md` |
| 生成 LaTeX | `references/LaTeX格式规范.md`、`../../../tools/latex/SKILL.md` |
| 中文写作检查 | `references/写作规范.md` |
| 英文 MCM/ICM | `references/英文化工作流.md` |
| 交付前 | `references/自审框架.md` |

内部分析表、核对清单和临时 Markdown 不作为交付物。
