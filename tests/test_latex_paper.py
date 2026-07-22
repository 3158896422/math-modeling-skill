import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


SCRIPTS = Path(__file__).resolve().parents[1] / "tools" / "latex" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from latex_paper import build_paper, inspect_paper, prepare_project


class LatexPaperTests(unittest.TestCase):
    def test_prepares_bundled_template_without_overwriting(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "完整论文-LaTeX"
            result = prepare_project(output, contest="cumcm")

            self.assertEqual(Path(result["main_tex"]), output / "main.tex")
            self.assertTrue((output / "references.bib").is_file())
            with self.assertRaises(FileExistsError):
                prepare_project(output, contest="cumcm")

    def test_copies_complete_official_template_project(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            template = root / "official"
            template.mkdir()
            (template / "paper.tex").write_text(
                "\\documentclass{official}\\begin{document}x\\end{document}",
                encoding="utf-8",
            )
            (template / "cover.tex").write_text("cover", encoding="utf-8")
            (template / "official.cls").write_text("official class", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "主入口"):
                prepare_project(root / "ambiguous", template_path=template)
            result = prepare_project(
                root / "paper",
                template_path=template,
                main_file="paper.tex",
            )

            self.assertEqual(Path(result["main_tex"]).name, "paper.tex")
            self.assertTrue((root / "paper" / "official.cls").is_file())
            self.assertTrue((root / "paper" / "cover.tex").is_file())

    def test_inspects_nested_sources_figures_tables_and_bibliography(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "sections").mkdir()
            (root / "figures").mkdir()
            (root / "figures" / "result.png").write_bytes(b"png")
            (root / "sections" / "model.tex").write_text(
                r"""
\section{模型}
正文引用图表~\cref{fig:result,tab:result}和文献~\cite{smith2026}。
\begin{equation} y=ax+b \end{equation}
\begin{figure}\includegraphics{result}\caption{结果}\label{fig:result}\end{figure}
\begin{longtable}{cc}\caption{参数}\label{tab:result}a&b\end{longtable}
""",
                encoding="utf-8",
            )
            (root / "references.bib").write_text(
                "@article{smith2026, title={Verified model}}",
                encoding="utf-8",
            )
            main = root / "main.tex"
            main.write_text(
                r"""
\documentclass{article}
\newcommand{\keywords}[1]{#1}
\graphicspath{{figures/}}
\begin{document}
\begin{abstract}摘要\keywords{模型；验证}\end{abstract}
\input{sections/model}
\bibliography{references}
\end{document}
""",
                encoding="utf-8",
            )

            report = inspect_paper(main)

            self.assertTrue(report["passed"], report["issues"])
            self.assertEqual(report["metrics"]["source_files"], 2)
            self.assertEqual(report["metrics"]["equations"], 1)
            self.assertEqual(report["metrics"]["figures"], 1)
            self.assertEqual(report["metrics"]["tables"], 1)
            self.assertEqual(report["metrics"]["citations"], 1)

    def test_reports_placeholders_orphans_and_missing_citations(self):
        with tempfile.TemporaryDirectory() as temporary:
            main = Path(temporary) / "main.tex"
            main.write_text(
                r"""
\documentclass{article}\newcommand{\keywords}[1]{#1}
\begin{document}
\begin{abstract}LATEX_TEMPLATE_ABSTRACT\keywords{test}\end{abstract}
\begin{figure}\caption{result}\label{fig:orphan}\end{figure}
See \cite{missing}.\end{document}
""",
                encoding="utf-8",
            )

            issues = inspect_paper(main)["issues"]

            self.assertTrue(any("模板占位符" in item for item in issues))
            self.assertTrue(any("孤儿图" in item for item in issues))
            self.assertTrue(any("缺少参考文献条目" in item for item in issues))

    def test_reports_duplicate_labels(self):
        with tempfile.TemporaryDirectory() as temporary:
            main = Path(temporary) / "main.tex"
            main.write_text(
                r"""
\documentclass{article}\newcommand{\keywords}[1]{#1}
\begin{document}\begin{abstract}summary\keywords{test}\end{abstract}
\section{A}\label{sec:duplicate}\section{B}\label{sec:duplicate}
\end{document}
""",
                encoding="utf-8",
            )

            issues = inspect_paper(main)["issues"]

            self.assertTrue(any("重复 label" in item for item in issues))

    def test_rejects_sources_outside_project_and_missing_engine(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            main = root / "paper" / "main.tex"
            main.parent.mkdir()
            main.write_text(
                "\\documentclass{article}\\begin{document}\\input{../secret}\\end{document}",
                encoding="utf-8",
            )
            (root / "secret.tex").write_text("secret", encoding="utf-8")
            with self.assertRaises(ValueError):
                inspect_paper(main)

            main.write_text(
                "\\documentclass{article}\\begin{document}ok\\end{document}",
                encoding="utf-8",
            )
            with patch("latex_paper.shutil.which", return_value=None):
                with self.assertRaisesRegex(RuntimeError, "未找到"):
                    build_paper(main)

    def test_latexmk_build_uses_relative_output_and_disables_shell_escape(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            main = root / "main.tex"
            main.write_text(
                "\\documentclass{article}\\begin{document}ok\\end{document}",
                encoding="utf-8",
            )
            observed = {}

            def fake_run(command, **kwargs):
                observed.update({"command": command, **kwargs})
                build = Path(kwargs["cwd"]) / "build"
                (build / "main.pdf").write_bytes(b"pdf")
                (build / "main.log").write_text("clean build", encoding="utf-8")
                return SimpleNamespace(returncode=0, stdout="", stderr="")

            with patch(
                "latex_paper.shutil.which",
                side_effect=lambda name: "latexmk" if name == "latexmk" else None,
            ), patch("latex_paper.subprocess.run", side_effect=fake_run):
                report = build_paper(main)

            self.assertTrue(report["passed"])
            self.assertIn("-norc", observed["command"])
            self.assertIn("-outdir=build", observed["command"])
            self.assertTrue(any("-no-shell-escape" in item for item in observed["command"]))
            self.assertEqual(observed["env"]["openin_any"], "p")
            self.assertEqual(observed["env"]["openout_any"], "p")

    def test_build_gate_rejects_layout_and_font_warnings(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            main = root / "main.tex"
            main.write_text(
                "\\documentclass{article}\\begin{document}ok\\end{document}",
                encoding="utf-8",
            )

            def fake_run(_command, **kwargs):
                build = Path(kwargs["cwd"]) / "build"
                (build / "main.pdf").write_bytes(b"pdf")
                (build / "main.log").write_text(
                    "Overfull \\hbox (2.0pt too wide)\n"
                    "LaTeX Font Warning: Font shape unavailable",
                    encoding="utf-8",
                )
                return SimpleNamespace(returncode=0, stdout="", stderr="")

            with patch(
                "latex_paper.shutil.which",
                side_effect=lambda name: "latexmk" if name == "latexmk" else None,
            ), patch("latex_paper.subprocess.run", side_effect=fake_run):
                report = build_paper(main)

        self.assertFalse(report["passed"])
        self.assertTrue(any("Overfull" in issue for issue in report["issues"]))
        self.assertTrue(any("Font Warning" in issue for issue in report["issues"]))

    def test_external_bibliography_requires_latexmk(self):
        with tempfile.TemporaryDirectory() as temporary:
            main = Path(temporary) / "main.tex"
            main.write_text(
                r"\documentclass{article}\begin{document}\cite{x}"
                r"\bibliography{references}\end{document}",
                encoding="utf-8",
            )
            (Path(temporary) / "references.bib").write_text(
                "@article{x,title={x}}",
                encoding="utf-8",
            )

            with patch(
                "latex_paper.shutil.which",
                side_effect=lambda name: None if name == "latexmk" else name,
            ):
                with self.assertRaisesRegex(RuntimeError, "latexmk"):
                    build_paper(main)


if __name__ == "__main__":
    unittest.main()
