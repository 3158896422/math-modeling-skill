---
name: LaTeX工具
description: 从官方或内置模板创建、编译和校验数学建模 LaTeX 论文项目，并可配合 DOCX 工具把完整 LaTeX 论文转换为 Word。
---

# LaTeX 工具

## 路径与写入

- 当前目录为 `LATEX_TOOL_ROOT`，只读。
- 模板和脚本从本目录读取；论文项目只写入 `PROJECT_ROOT`。
- 官方模板、题目附件和 Skill 文件保持只读；先复制，再填充。
- 默认不覆盖已有输出目录。

## 模板优先级

1. 用户提供的当届官方 LaTeX 模板项目。
2. 从目标竞赛官方网站取得的当届 LaTeX 模板项目。
3. `assets/templates/cumcm/` 或 `assets/templates/mcm-icm/` 构建基线。

内置模板只在没有官方 LaTeX 模板时使用，不替代当届官方规则。复制官方模板目录时保留其 `.cls`、`.sty`、`.bst`、字体和图片资源，不重写导言区或文档类。

## 初始化

```powershell
python "<SKILL_ROOT>/tools/latex/scripts/latex_paper.py" init `
  "<PROJECT_ROOT>/完整论文-LaTeX" `
  --contest cumcm `
  --template "<PROJECT_ROOT>/当届官方LaTeX模板" `
  --main paper.tex
```

没有官方模板时同时省略 `--template` 和 `--main`。官方模板入口为 `main.tex` 或只有一个顶层 `.tex` 时可省略 `--main`；存在多个候选文件时必须按官方说明显式指定，不能猜测。初始化后在复制件中填充正文，并把真实图表与核验后的 BibTeX 条目放入项目；不得修改模板源文件。

## 编译

优先使用 `latexmk` 管理交叉引用和参考文献；未安装时，只对不含外部 BibTeX/BibLaTeX 文献库的项目回退为连续两次运行指定引擎。含外部文献库的完整论文必须安装 `latexmk`。默认使用 XeLaTeX，且不启用 shell escape。

```powershell
python "<SKILL_ROOT>/tools/latex/scripts/latex_paper.py" build `
  "<PROJECT_ROOT>/完整论文-LaTeX/main.tex" `
  --engine xelatex `
  --publish "<PROJECT_ROOT>/完整论文.pdf"
```

若官方模板明确要求 LuaLaTeX 或 pdfLaTeX，再改用 `--engine lualatex` 或 `--engine pdflatex`。缺少宏包时报告环境问题，不自动联网安装，也不擅自替换官方文档类。编译日志中的未解析引用、LaTeX/宏包/文档类预警、Overfull/Underfull box 和字体预警都会使完成门禁失败，必须修正后重编译；只有当届官方规则或用户明确要求允许偏离时，才能记录具体预警和依据后继续。

## 校验

```powershell
python "<SKILL_ROOT>/tools/latex/scripts/latex_paper.py" validate `
  "<PROJECT_ROOT>/完整论文-LaTeX/main.tex" `
  --pdf "<PROJECT_ROOT>/完整论文.pdf" `
  --contest cumcm `
  --quality-checks `
  --max-pages <当届官方上限>
```

校验器递归读取项目内的 `\input` 与 `\include`，并检查：

- 摘要、关键词和未清理占位符；
- 字词单位、公式、图、表和编译后实际页数；
- 图片文件是否存在，`label` 是否重复，图表是否有 `label` 且在正文引用；
- `\cite` 是否能在 BibTeX 或 `\bibitem` 中找到对应条目；
- 手工参考文献是否被正文引用。

CUMCM 的约 15000 字词单位、约 20 页、5 个公式、3 幅图和 3 个表只是可覆盖的完整度质量目标。页数上限等官方硬约束必须从目标届次规则读取后通过参数传入。MCM/ICM 不内置永久页数阈值。

通过静态校验后仍需打开编译 PDF，抽检摘要页、分页、页眉页脚、字体、公式、表格、图片和参考文献。XML/正则检查或一次成功编译都不能替代版面抽检。

## 转换为 DOCX

需要同时交付 Word 时，读取 `../docx/SKILL.md`，调用 `equations.py convert-latex` 或后端 DOCX 工具的 `convert_latex` 动作。LaTeX 源码仍须独立编译 PDF；DOCX 转换不能替代 LaTeX 编译与校验。
