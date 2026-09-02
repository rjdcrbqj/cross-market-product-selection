from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / "skills" / "cross-market-product-selection"


class SkillContractTests(unittest.TestCase):
    def test_core_skill_is_chinese_first_and_generic(self):
        text = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
        for phrase in ["先确认外观与功能", "严格合格", "待核验", "已淘汰", "图片必须嵌入", "40%", "20%"]:
            self.assertIn(phrase, text)
        self.assertNotIn("P10", text)

    def test_required_chinese_references_exist(self):
        for name in ["需求确认与评分.md", "证据质量.md", "Excel输出规范.md"]:
            self.assertTrue((SKILL_DIR / "references" / name).is_file(), name)

    def test_every_local_markdown_link_resolves(self):
        markdown_files = [SKILL_DIR / "SKILL.md", *SKILL_DIR.joinpath("references").glob("*.md")]
        pattern = re.compile(r"\[[^\]]+\]\(([^)]+\.md)\)")
        for markdown_file in markdown_files:
            text = markdown_file.read_text(encoding="utf-8")
            for relative in pattern.findall(text):
                self.assertTrue((markdown_file.parent / relative).resolve().is_file(), f"{markdown_file}: {relative}")

    def test_scoring_formula_and_price_rule_are_documented(self):
        text = (SKILL_DIR / "references" / "需求确认与评分.md").read_text(encoding="utf-8")
        self.assertIn("销量标准分 × 40% + 价格相似分 × 40% + 评价标准分 × 20%", text)
        self.assertIn("|实际价格 − 目标价格|", text)


if __name__ == "__main__":
    unittest.main()
