---
name: 编程手
description: 数学建模的 Python 或 MATLAB 实现、运行、表格输出、可视化和复现阶段。
---

# 编程手

## 路径

- `ROLE_ROOT`：本文件所在目录。
- `SKILL_ROOT`：`ROLE_ROOT/../../..`，只读。
- `PROJECT_ROOT`：用户项目目录，所有代码、结果和图只写这里。

## 输入

优先读取 `PROJECT_ROOT/题目分析报告.md`、`PROJECT_ROOT/术语表格.md` 和题目附件。若用户只执行本阶段，可从用户提供的模型说明开始；若说明不足以实现，先反馈缺项。

## 固定产物

- Python `.py`、MATLAB `.m`，或用户要求的两套实现。
- `results/` 中的运行结果表格和必要文本结果。
- `figures/` 中的原始数据图、模型运行过程图、模型最终结果图；允许多生成候选图。
- `results/复现清单.json`。

## 执行顺序

1. 按用户要求或现有项目语言选择 Python/MATLAB；没有偏好时按模型依赖和现有环境选择并说明。
2. 按选中的模型功能动态检查依赖，禁止一次性要求全部包：
   - Python：`python scripts/check_env.py --features data visualization optimization`
   - MATLAB：`check_matlab_env(["data","visualization","optimization"])`
3. 写代码、运行、验证数值与边界条件；任何结论必须来自真实输出。
4. 绘图前完成数据剖析与图表契约：核对行列、类型、缺失、分组样本量、分布、异常值和单位，明确候选图要支撑的结论、统计口径与输出尺寸。无法判断图型或用户指定图型存在误导风险时，读取 `references/图表选择与避坑.md`。
5. 将 `scripts/plot_style.py` 或 MATLAB 的两个出版样式工具复制到 `PROJECT_ROOT/utils/` 后使用。按 Nature/SCI 的克制型出版风格基线生成三类候选图，不使用网格线；统计标注必须由代码计算，官方模板要求优先于内置基线。
6. 同时输出 SVG 与至少 300 DPI PNG，运行 `scripts/figure_audit.py <PROJECT_ROOT>/figures --strict`，并实际打开 PNG 检查缺字、裁切、遮挡、颜色、尺度和面板一致性；有问题则改代码、重跑、重审，不能直接修改位图。
7. 生成复现清单：`python scripts/repro_manifest.py --project-root <PROJECT_ROOT> ...`。
8. 按 `references/质检清单.md` 验收。

## 何时加载

| 情形 | 读取 |
|---|---|
| 开始实现 | `references/工作流程.md` |
| 使用 MATLAB | `references/MATLAB规范.md` |
| 画图 | `references/可视化规范.md` |
| 不确定用什么图，或需审查指定图型 | `references/图表选择与避坑.md` |
| 需要图表函数 | `references/常见模式.md` |
| 需要具体算法 | `../../../references/算法索引.md`，再读取匹配的 `../../../assets/*.md` |
| 处理 Excel | `../../../tools/xlsx/SKILL.md` |
| 交付前 | `references/质检清单.md` |

若实际运行证明模型公式、约束或参数定义冲突，停止通过改算法规避问题，把证据反馈给建模手。
