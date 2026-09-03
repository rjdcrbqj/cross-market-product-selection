from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = ROOT / "skills" / "cross-market-product-selection" / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from validate_workbook import extract_workbook_model, validate_workbook_model


TEMPLATE = ROOT / "skills" / "cross-market-product-selection" / "assets" / "通用选品数据库模板.xlsx"
MAINTAINER = ROOT / "tools" / "maintain_selection_template.mjs"


class RealTemplateIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.node = shutil.which("node")
        if cls.node is None:
            raise AssertionError("真实模板集成门禁需要工作区随附的 Node.js")

    def create_scenario(self, directory, mode, scenario="valid"):
        output = Path(directory) / f"{mode}-{scenario}.xlsx"
        subprocess.run(
            [self.node, str(MAINTAINER), "scenario", str(TEMPLATE), str(output), mode, scenario],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        return output

    def test_real_committed_template_extracts_and_validates_in_all_three_modes(self):
        candidate_sheet = {"Amazon": "亚马逊候选", "1688": "1688候选", "联合": "货源匹配"}
        with tempfile.TemporaryDirectory() as temporary_directory:
            for mode in ("Amazon", "1688", "联合"):
                with self.subTest(mode=mode):
                    workbook_path = self.create_scenario(temporary_directory, mode)
                    model = extract_workbook_model(workbook_path)
                    issues = validate_workbook_model(model)
                    self.assertEqual(issues, [])
                    strict = [row for row in model.rows if row.sheet == "严格结果"]
                    self.assertEqual(len(strict), 1)
                    expected_images = 2 if mode == "联合" else 1
                    self.assertEqual(len(strict[0].image_headers), expected_images)
                    candidates = [row for row in model.rows if row.sheet == candidate_sheet[mode]]
                    self.assertEqual(len(candidates), 1)
                    self.assertEqual(candidates[0].values["状态"], "严格合格")
                    self.assertEqual(len(candidates[0].image_headers), expected_images)
                    for header, value in candidates[0].values.items():
                        if isinstance(value, str) and value.startswith(("http://", "https://")):
                            with self.subTest(mode=mode, header=header):
                                self.assertEqual(candidates[0].hyperlinks.get(header), value)

    def test_real_template_scenarios_preserve_platform_score_formulas(self):
        amazon_score_fields = {
            "Amazon销量得分",
            "Amazon价格得分",
            "Amazon评价得分",
            "Amazon产品总评分",
        }
        supply_score_fields = {
            "1688销量得分",
            "1688价格得分",
            "1688评价得分",
            "1688产品总评分",
        }
        expected_formula_fields = {
            "Amazon": amazon_score_fields,
            "1688": supply_score_fields,
            "联合": amazon_score_fields | supply_score_fields,
        }
        with tempfile.TemporaryDirectory() as temporary_directory:
            for mode, expected_fields in expected_formula_fields.items():
                with self.subTest(mode=mode):
                    workbook_path = self.create_scenario(temporary_directory, mode)
                    model = extract_workbook_model(workbook_path)
                    strict = next(row for row in model.rows if row.sheet == "严格结果")
                    self.assertEqual(set(strict.formulas), expected_fields)

    def test_real_committed_template_rejects_factory_and_image_counterexamples(self):
        cases = (
            ("1688", "odm-color", "ODM_EVIDENCE_MISSING"),
            ("1688", "production-store", "PRODUCTION_EVIDENCE_MISSING"),
            ("1688", "production-link", "PRODUCTION_EVIDENCE_MISSING"),
            ("1688", "missing-production", "PRODUCTION_EVIDENCE_MISSING"),
            ("1688", "missing-homepage", "SUPPLIER_PROFILE_MISSING"),
            ("联合", "missing-image", "STRICT_IMAGE_MISSING"),
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            for mode, scenario, expected_code in cases:
                with self.subTest(mode=mode, scenario=scenario):
                    workbook_path = self.create_scenario(temporary_directory, mode, scenario)
                    issue_codes = {issue.code for issue in validate_workbook_model(extract_workbook_model(workbook_path))}
                    self.assertIn(expected_code, issue_codes)

    def test_versioned_maintainer_rebuilds_the_committed_semantic_contract(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            rebuilt = Path(temporary_directory) / "rebuilt.xlsx"
            subprocess.run(
                [self.node, str(MAINTAINER), "build", str(rebuilt)],
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            committed_model = extract_workbook_model(TEMPLATE)
            rebuilt_model = extract_workbook_model(rebuilt)

        self.assertEqual(rebuilt_model.sheets, committed_model.sheets)
        self.assertEqual(rebuilt_model.headers, committed_model.headers)
        self.assertEqual(rebuilt_model.task_fields, committed_model.task_fields)
        self.assertEqual(validate_workbook_model(rebuilt_model), [])


if __name__ == "__main__":
    unittest.main()
