import importlib.util
import struct
import sys
import tempfile
import unittest
import zlib
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "references" / "roles" / "编程手" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import figure_audit
import plot_style


def _png_chunk(kind: bytes, data: bytes) -> bytes:
    payload = kind + data
    return struct.pack(">I", len(data)) + payload + struct.pack(">I", zlib.crc32(payload) & 0xFFFFFFFF)


def _write_png(path: Path, dpi: int) -> None:
    pixels_per_meter = round(dpi / 0.0254)
    content = [
        figure_audit.PNG_SIGNATURE,
        _png_chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 0)),
        _png_chunk(b"pHYs", struct.pack(">IIB", pixels_per_meter, pixels_per_meter, 1)),
        _png_chunk(b"IDAT", zlib.compress(b"\x00\x00\x00\x00\x00")),
        _png_chunk(b"IEND", b""),
    ]
    path.write_bytes(b"".join(content))


def _write_svg(path: Path, with_text: bool = True) -> None:
    body = '<text x="1" y="8">label</text>' if with_text else '<path d="M0 0 L1 1"/>'
    path.write_text(f'<svg xmlns="http://www.w3.org/2000/svg">{body}</svg>', encoding="utf-8")


class PlotStyleTests(unittest.TestCase):
    def test_palette_is_unique_and_colorblind_oriented(self):
        self.assertEqual(len(plot_style.COLOR_SEQUENCE), len(set(plot_style.COLOR_SEQUENCE)))
        self.assertEqual(plot_style.PALETTE["primary"], "#0072B2")
        width, height = plot_style.figure_size("report")
        self.assertEqual(width, 6.3)
        self.assertAlmostEqual(height, 3.906)

    def test_refuses_output_inside_skill_root(self):
        with self.assertRaisesRegex(ValueError, "PROJECT_ROOT"):
            plot_style.resolve_output_stem(plot_style.SKILL_ROOT / "figures" / "result_demo")

    @unittest.skipUnless(importlib.util.find_spec("matplotlib"), "需要 matplotlib")
    def test_real_export_passes_file_audit(self):
        import matplotlib

        matplotlib.use("Agg", force=True)
        import matplotlib.pyplot as plt

        with tempfile.TemporaryDirectory() as tmp:
            plot_style.apply_publication_style(language="en", width="single")
            fig, axis = plt.subplots()
            axis.plot([0, 1], [0, 1])
            axis.set(xlabel="Time (s)", ylabel="Value")
            outputs = plot_style.export_figure(fig, Path(tmp) / "result_demo")
            plt.close(fig)

            report = figure_audit.audit_figure_directory(tmp, require_categories=False)

        self.assertTrue(report["ok"], report["issues"])
        self.assertTrue(Path(outputs["grayscale"]).name.endswith("_grayscale.png"))
        metadata = report["files"]["result_demo.png"]
        self.assertEqual(metadata["width_px"], 1050)
        self.assertEqual(metadata["height_px"], 651)
        self.assertAlmostEqual(metadata["width_in"], 3.5, places=3)

    @unittest.skipUnless(importlib.util.find_spec("matplotlib"), "需要 matplotlib")
    def test_layout_audit_detects_overlapping_ticks(self):
        import matplotlib

        matplotlib.use("Agg", force=True)
        import matplotlib.pyplot as plt

        fig, axis = plt.subplots(figsize=(2, 1.5), constrained_layout=False)
        axis.set_xticks(range(8), [f"very-long-category-{index}" for index in range(8)])
        issues = plot_style.audit_layout(fig)
        plt.close(fig)

        self.assertTrue(any("x 刻度标签重叠" in issue for issue in issues), issues)


class FigureAuditTests(unittest.TestCase):
    def test_accepts_three_categories_with_svg_png_pairs(self):
        with tempfile.TemporaryDirectory() as tmp:
            figures = Path(tmp)
            for stem in ("raw_data", "process_loss", "result_solution"):
                _write_svg(figures / f"{stem}.svg")
                _write_png(figures / f"{stem}.png", 300)

            report = figure_audit.audit_figure_directory(figures)

        self.assertTrue(report["ok"], report["issues"])
        self.assertEqual(report["issues"], [])

    def test_rejects_low_dpi_and_missing_editable_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            figures = Path(tmp)
            _write_svg(figures / "result_solution.svg", with_text=False)
            _write_png(figures / "result_solution.png", 96)

            report = figure_audit.audit_figure_directory(figures, require_categories=False)

        messages = "\n".join(item["message"] for item in report["issues"])
        self.assertFalse(report["ok"])
        self.assertIn("可编辑文本", messages)
        self.assertIn("低于 300 DPI", messages)

    def test_rejects_missing_format_pair(self):
        with tempfile.TemporaryDirectory() as tmp:
            figures = Path(tmp)
            _write_svg(figures / "raw_data.svg")

            report = figure_audit.audit_figure_directory(figures, require_categories=False)

        self.assertFalse(report["ok"])
        self.assertIn("缺少配对格式", report["issues"][0]["message"])


if __name__ == "__main__":
    unittest.main()
