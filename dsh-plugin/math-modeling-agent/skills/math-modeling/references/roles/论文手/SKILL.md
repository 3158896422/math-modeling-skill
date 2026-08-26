---
name: 论文手
description: 根据题目、建模分析和真实代码结果生成完整 Word 数学建模论文，用户显式要求时同时生成 LaTeX 论文。
---

# 论文手

## 开始门禁

开始写作前先在进度更新中报告输入检查结果。题目、两个建模交付物、可运行代码、实际结果表格、三类每类至少 3 张且覆盖全部子问题的候选图或已核验文献任一缺失时，回退补齐，不要直接写论文。

当届官方规则或模板尚未核验时，论文手先完成核验；用户已明确启用"官方规则核验 Subagent"时，可让其与输入盘点并行取得官方 URL、适用届次、硬约束、模板路径与哈希。无论是否启用可选 Subagent，论文构建都必须等待规则核验完成。

- 用户显式要求 LaTeX 时，必须先调用 `<SKILL_ROOT>/tools/latex/scripts/latex_paper.py init` 复制官方或内置模板；禁止另写一个临时 `main.tex` 替代模板链路。
- 写正文前先调用 `latex_paper.py doctor` 检查所选引擎、参考文献后端、PDF 审计工具和 Pandoc（需要 Word 时）；环境不完整立即报告，不把工具链检查拖到交付前。
- 引用前必须运行双引擎检索并打开 DOI 或出版机构页面核验元数据；仅复制上游参考文献列表不算核验。
- 写作过程中持续核对篇幅和主张—证据映射，不要等文档生成后才第一次统计。

## 路径

- `ROLE_ROOT`：本文件所在目录。
- `SKILL_ROOT`：`ROLE_ROOT/../../..`，只读。
- `PROJECT_ROOT`：用户项目目录，论文只写这里。

## 格式与交付物

默认只生成 Word 论文；用户显式要求时同时生成 LaTeX 论文，确保正文内容、数据、图表和结论一致。

- Word：`PROJECT_ROOT/完整论文.docx`。
- LaTeX（可选）：`PROJECT_ROOT/完整论文-LaTeX/` 源码项目和由它实际编译的 `PROJECT_ROOT/完整论文.pdf`。

用户明确只要 Word 时，只生成 Word。当届官方提交要求仍决定实际可提交的版本；论文仅供参考，格式和内容必须服从当届官方规则。

## 官方规则优先级

1. 用户提供的当届官方模板和规则。
2. 从目标竞赛官方网站取得的当届模板和规则。
3. Word 分支以 `references/论文模板.docx` 和 `../../../tools/docx/scripts/paper_format.py` 为无官方模板时的构建基线；LaTeX 分支以 `../../../tools/latex/assets/templates/` 为构建基线。两者均不得声称替代当届官方文件。

在生成前明确竞赛名称、届次、语言和官方规则来源。官方结构、页型、页边距、摘要页、页数、编号和提交格式均以当届规则为准。

同时明确两类要求：官方硬约束与可调整质量目标。摘要页、纸质版固定页面、电子版删页、文件大小、匿名和官方正文页数口径必须按当届规则核验；本 Skill 另外设置完整渲染 PDF 总页数不超过 30 页的默认输出门槛，正文页数仍单独记录为诊断指标。约 15000 字词单位、约 20 页、5 公式、8 图、3 表只是可按题目调整的质量目标，低于目标只能作为完整度预警，不能写成官方最低数量或冒充官方违规。全国赛必须使用当届官方模板；没有模板时报告阻塞。

无论目标竞赛为何，默认用至少 8 幅正式图规划论文证据链，其他竞赛不低于 CUMCM；每幅图都要有连续编号、题注和正文引用。当届官方规则或用户明确要求与此冲突时，以其要求为准并记录依据。

## 执行顺序

1. 读取题目、`题目分析报告.md`、`术语表格.md`、全部真实运行表格、图和代码。
2. 建立内部 Claim-Evidence 映射和论文大纲，为每个子问题列出核心主张、公式、结果表位置、至少 1 幅拟入文正式图、代码输出或已核验文献；不得只集中使用问题一的图。缺证据时回退到建模手或编程手，禁止编造。
3. 在开始长篇正文和双格式排版前，派发独立质检 Subagent 执行 `W1` 证据大纲门禁；未返回 `PASS` 不得先写后补。
4. 按官方结构写完整正文，引用由双引擎搜索结果和原始出版页面核验。
5. 默认先确定同一份正文、数据、图表和参考文献，再生成 Word；用户显式要求 LaTeX 时同时生成 LaTeX，禁止两份论文出现不同结论。
6. Word 使用 `../../../tools/docx/SKILL.md` 构建 DOCX，公式使用原生 OMML；已有完整 LaTeX 主稿时可通过 `convert_latex` 生成内容一致的 Word 初稿，再按官方 DOCX 模板修正。LaTeX（可选）使用 `../../../tools/latex/SKILL.md` 复制完整官方模板项目、填充源码并真实编译 PDF。
7. 检查 Word 的结构、篇幅、公式、图表、全部子问题覆盖、编号引用、参考文献和实际渲染页数。用户显式要求 LaTeX 时，还必须消除编译错误及未解析的引用，核对权威资源—源码—PDF 哈希、PDF 总页数、正文页数、附录边界、字体嵌入、空白页、页面尺寸和图片 DPI；所有预警必须修正，或根据当届官方规则记录明确覆盖理由后才能继续。
8. 完成下列确定性门禁后，派发独立质检 Subagent 执行 `W2` 论文终检；未返回 `PASS` 不得宣称完成或交付论文。

## 阶段内独立门禁

- `W1`：质检 Subagent 核对每个必须回答的结论类型都有精确证据路径，摘要拟用关键数值与结果表一致，图表、公式和引用都有章节落点。用户显式要求 LaTeX 时，Word 与 LaTeX 共用同一证据源。证据大纲只保留在内部检查中，不新增固定交付物。
- `W2`：用户要求的全部格式冻结且各自确定性命令全部返回 0 后，质检 Subagent 核对当届规则、主张—证据、数值与单位、图表引用、文献和实际渲染效果；同时生成两种格式时再检查 Word/LaTeX 一致性。失败时精确到页码、章节、命令或来源并返回对应角色。

两次门禁均按 `../../../references/Subagent调度.md` 返回证据；正文、数据、图表或规则发生实质变化时重跑受影响门禁。

## 完成门禁

交付 Word 时依次运行：

```powershell
python "<SKILL_ROOT>/tools/docx/scripts/paper_format.py" validate "<PROJECT_ROOT>/完整论文.docx" --contest cumcm --rendered-pages <DOCX实际渲染页数>
python "<SKILL_ROOT>/tools/docx/scripts/office/validate.py" "<PROJECT_ROOT>/完整论文.docx"
python "<SKILL_ROOT>/tools/docx/scripts/equations.py" verify-conversion "<PROJECT_ROOT>/完整论文.docx"
```

最后一条仅适用于由 `equations.py generate/convert-latex` 生成的 DOCX；若 Word 由 `paper_format.py` 直接构建，则改为核对其自身质量报告和复现清单。交付 LaTeX 时依次运行：

```powershell
python "<SKILL_ROOT>/tools/latex/scripts/latex_paper.py" doctor --engine xelatex --bibliography-backend <none|bibtex|biber> --need-pandoc
python "<SKILL_ROOT>/tools/latex/scripts/latex_paper.py" build "<PROJECT_ROOT>/完整论文-LaTeX/main.tex" --engine xelatex --publish "<PROJECT_ROOT>/完整论文.pdf"
python "<SKILL_ROOT>/tools/latex/scripts/latex_paper.py" validate "<PROJECT_ROOT>/完整论文-LaTeX/main.tex" --pdf "<PROJECT_ROOT>/完整论文.pdf" --contest cumcm --quality-checks --questions q1 q2 q3 --min-image-dpi 300 --max-pages 30 --body-start-page <正文起始页> --appendix-start-page <附录起始页>
```

根据目标竞赛、实际子问题和官方模板替换 `contest`、`--questions`、引擎、参考文献后端、正文起始页、附录起始页及页数参数；CUMCM 的 `--max-pages` 默认使用完整渲染 PDF 总页数门槛 30，若当届规则或用户要求不同则显式传入并记录依据；没有附录时省略 `--appendix-start-page`。

上述命令只完成作者侧技术校验，不替代 `W2` 独立验收。

## CUMCM 最终提交门禁

全国赛在 DOCX/LaTeX 渲染为完整纸质版 PDF 后，必须运行：

```powershell
python "<SKILL_ROOT>/tools/docx/scripts/cumcm_submission.py" validate-paper "<PROJECT_ROOT>/完整论文-纸质版.pdf" --mode paper --term "<真实姓名>" --term "<真实学校>" --term "<真实赛区>"
python "<SKILL_ROOT>/tools/docx/scripts/cumcm_submission.py" export-electronic "<PROJECT_ROOT>/完整论文-纸质版.pdf" "<PROJECT_ROOT>/完整论文.pdf" --term "<真实姓名>" --term "<真实学校>" --term "<真实赛区>" --overwrite
python "<SKILL_ROOT>/tools/docx/scripts/cumcm_submission.py" package-support "<PROJECT_ROOT>/支撑材料.zip" "<PROJECT_ROOT>/code" "<PROJECT_ROOT>/results" --term "<真实姓名>" --term "<真实学校>" --term "<真实赛区>" --overwrite
```

第一条检查纸质版第 1–3 页固定页面、第 4 页正文起始、摘要≤1页、完整渲染 PDF 总页数≤30页（Skill 输出门槛；正文页数另按官方规则核对）、摘要页起连续页码、A4 和匿名；第二条只有在纸质版通过后才删除前两页，并复核电子版首页摘要、A4、正文边界、匿名和 20 MB；第三条生成保留相对路径的 ZIP 文件清单，并扫描文件名、文本、DOCX/PDF/XLSX 成员的敏感信息和 20 MB 大小。若确实无支撑材料，允许不生成 ZIP，但附录必须明确注明“本论文没有支撑材料”。自动文本抽取或页码识别失败时报告阻塞，不能把人工未核验的文件声称为通过。

## 何时加载

| 情形 | 读取 |
|---|---|
| 开始写作 | `references/工作流程.md` |
| 组织章节 | `references/章节模板.md` |
| 生成 Word | `references/论文格式规范.md`、`../../../tools/docx/SKILL.md` |
| 生成 LaTeX | `references/LaTeX格式规范.md`、`../../../tools/latex/SKILL.md` |
| 中文写作检查 | `references/写作规范.md` |
| 抓分检查（摘要/结论/图表） | `references/写作规范.md`（第二节 评阅人抓分方法论） |
| 英文 MCM/ICM | `references/英文化工作流.md` |
| 交付前 | `references/自审框架.md` |
| 阶段内独立验收 | `../../../references/Subagent调度.md` |

内部分析表、核对清单和临时 Markdown 不作为交付物。

## Markdown 公式写法

论文草稿、证据大纲和其他 Markdown 中的数学公式统一使用 VS Code 预览兼容的
`$...$`（行内）或单独成行的 `$$...$$`（行间）。禁止使用 `\(...\)`、`\[...\]`
作为 Markdown 公式分隔符；仅在复制到 `.tex` 源码时按 LaTeX 模板要求使用原生语法。

## 本 Skill 的输出页数与代码归档门槛

- **总页数门槛**：完成 DOCX/LaTeX 渲染后，以实际 PDF 页数为准，CUMCM 默认要求完整论文总页数不超过 30 页。纸质版检查包含承诺书、编号专用页、摘要、正文和附录；电子版删除前两页后，按实际电子版 PDF 再检查。正文页数仍单独记录，用于与当届官方规则核对和诊断，不得把“正文页数”替换成默认总页数门槛的文字表述。
- **代码归档**：完整编程代码不粘贴到论文末尾，也不在论文附录中逐文件展开。将可运行源程序、运行环境/依赖、运行命令、输入输出清单和必要中间结果放入一个不超过 20 MB 的支撑材料 ZIP（需要 RAR 时可用外部工具生成）；论文附录只保留支撑材料文件列表、复现说明和必要中间结果。
- **规则边界**：上述 30 页总页数和代码归档方式是本 Skill/用户指定的输出策略，严格于或不同于部分竞赛官方规则。正式参赛前必须人工核对当届官方公告、模板和提交须知；若官方要求不同，以当届官方要求为准并记录调整依据。
