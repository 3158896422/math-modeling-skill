import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "tools" / "docx" / "scripts"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(SCRIPTS))

try:
    import fitz
except ImportError:
    fitz = None

import cumcm_submission as cs
import paper_format as pf


def _write_pdf(path, pages):
    doc = fitz.open()
    for text in pages:
        page = doc.new_page(width=595.276, height=841.89)
        rect = fitz.Rect(72, 72, 523, 770)
        page.insert_htmlbox(rect, f"<p style='font-family: sans-serif;'>{text}</p>")
    doc.save(path)
    doc.close()


@unittest.skipIf(fitz is None, "PyMuPDF is required to build submission fixtures")
class CumcmSubmissionTests(unittest.TestCase):
    def test_paper_page_order_and_body_limit_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pdf = root / "paper.pdf"
            _write_pdf(pdf, [
                "全国大学生数学建模竞赛承诺书",
                "编号专用页 编号：12345",
                "摘 要 关键词：模型",
                "一、问题重述",
                "附录 支撑材料文件列表",
            ])
            report = cs.validate_paper(pdf, mode="paper", terms=["张三", "某某大学"])
            self.assertEqual(report["issues"], [], report["issues"])
            self.assertEqual(report["page_report"]["abstract_page"], 3)
            self.assertEqual(report["page_report"]["body_start_page"], 4)
            self.assertEqual(report["page_report"]["body_pages"], 1)

    def test_wrong_page_order_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            pdf = Path(tmp) / "bad.pdf"
            _write_pdf(pdf, ["摘要", "编号专用页", "承诺书", "正文"])
            report = cs.validate_paper(pdf, mode="paper")
            self.assertFalse(report["passed"])
            self.assertTrue(any("第 1 页未检测到承诺书" in issue for issue in report["issues"]))
            self.assertTrue(any("第 3 页未检测到摘要" in issue for issue in report["issues"]))

    def test_body_more_than_30_pages_fails(self):
        texts = ["承诺书", "编号专用页", "摘要", *(f"正文第{i}页" for i in range(1, 32)), "附录"]
        with tempfile.TemporaryDirectory() as tmp:
            pdf = Path(tmp) / "long.pdf"
            _write_pdf(pdf, texts)
            report = cs.validate_paper(pdf, mode="paper")
        self.assertTrue(any("超过官方上限 30 页" in issue for issue in report["issues"]))

    def test_export_electronic_removes_commitment_and_number_pages(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "纸质版.pdf"
            output = root / "电子版.pdf"
            _write_pdf(source, [
                "承诺书",
                "编号专用页",
                "摘 要 关键词：模型",
                "正文",
            ])
            report = cs.export_electronic(source, output, terms=["李四"])
            self.assertEqual(report["removed_pages"], [1, 2])
            self.assertTrue(report["passed"], report["issues"])
            self.assertEqual(report["page_report"]["pages"], 2)

    def test_support_package_has_manifest_and_excludes_forbidden_fixed_pages(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            code = root / "code"
            code.mkdir()
            (code / "main.py").write_text("print('ok')\n", encoding="utf-8")
            (root / "承诺书.docx").write_bytes(b"not a real docx")
            package = root / "支撑材料.zip"
            report = cs.package_support([code], package, overwrite=False)
            self.assertTrue(report["passed"], report["issues"])
            self.assertIn("code/main.py", report["files"])
            with zipfile.ZipFile(package) as archive:
                names = archive.namelist()
                manifest = archive.read("支撑材料文件列表.txt").decode("utf-8")
            self.assertIn("支撑材料文件列表.txt", names)
            self.assertIn("code/main.py", manifest)
            self.assertFalse(any("承诺书" in name for name in names))

    def test_custom_identity_term_is_detected_in_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "draft.md"
            source.write_text("作者来自自定义大学\n", encoding="utf-8")
            report = cs.scan_anonymity([source], terms=["自定义大学"])
            self.assertFalse(report["passed"])
            self.assertEqual(report["hits"][0]["term"], "自定义大学")


class QualityTargetSemanticsTests(unittest.TestCase):
    def test_profile_separates_official_constraints_from_targets(self):
        constraints = pf.profile_constraints("cumcm")
        self.assertEqual(constraints["abstract_max_pages"], 1)
        self.assertEqual(constraints["body_max_pages"], 30)
        self.assertTrue(constraints["requires_official_template"])
        self.assertFalse(constraints["allow_table_of_contents"])
        self.assertEqual(
            constraints["quality_targets"],
            {"content_units": 15000, "pages": 20, "equations": 5, "figures": 8, "tables": 3},
        )

    def test_quality_gaps_are_warnings_not_official_errors(self):
        doc = pf.new_document(contest="cumcm")
        pf.title(doc, "题目")
        pf.abstract_title(doc)
        pf.body(doc, "短摘要")
        pf.keywords(doc, "关键词")

        issues = pf.validate_paper_structure(
            doc,
            contest="cumcm",
            min_content_units=15000,
            min_equations=5,
            min_figures=8,
            min_tables=3,
            target_pages=20,
            rendered_pages=10,
            require_rendered_pages=False,
        )
        warnings = pf.quality_warnings(issues)
        errors = pf.official_errors(issues)
        self.assertTrue(warnings)
        self.assertFalse(errors)
        self.assertTrue(any("低于 15000" in warning for warning in warnings))
        self.assertTrue(any("公式" in warning for warning in warnings))
        self.assertTrue(any("图" in warning for warning in warnings))
        self.assertTrue(any("表" in warning for warning in warnings))
        self.assertTrue(any("20 页质量目标" in warning for warning in warnings))


if __name__ == "__main__":
    unittest.main()
