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
        for name in ["需求确认与评分.md", "证据质量.md", "Excel输出规范.md", "多产品提示词模板.md"]:
            self.assertTrue((SKILL_DIR / "references" / name).is_file(), name)

    def test_multi_product_agent_contract_is_documented(self):
        core = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
        intake = (SKILL_DIR / "references" / "需求确认与评分.md").read_text(encoding="utf-8")
        evidence = (SKILL_DIR / "references" / "证据质量.md").read_text(encoding="utf-8")
        amazon = (SKILL_DIR / "references" / "亚马逊模式.md").read_text(encoding="utf-8")
        source = (SKILL_DIR / "references" / "1688模式.md").read_text(encoding="utf-8")
        excel = (SKILL_DIR / "references" / "Excel输出规范.md").read_text(encoding="utf-8")
        prompt = (SKILL_DIR / "references" / "多产品提示词模板.md").read_text(encoding="utf-8")
        ui = (SKILL_DIR / "agents" / "openai.yaml").read_text(encoding="utf-8")

        for phrase in ["多产品", "目标产品ID", "每个目标产品", "严格多视图", "Amazon同类均价"]:
            self.assertIn(phrase, core)
        self.assertIn("一行一个目标产品", intake)
        self.assertIn("候选可见事实", evidence)
        self.assertIn("不得低于该目标产品的合格同类均价", amazon)
        self.assertIn("价格带下限", source)
        self.assertIn("固定九表", excel)
        for phrase in ["产品A", "产品B", "不足不凑数", "必须先输出冻结合同"]:
            self.assertIn(phrase, prompt)
        self.assertNotIn("P10", prompt)
        self.assertIn("多产品", ui)

    def test_mode_references_encode_source_and_dedup_boundaries(self):
        amazon = (SKILL_DIR / "references" / "亚马逊模式.md").read_text(encoding="utf-8")
        source1688 = (SKILL_DIR / "references" / "1688模式.md").read_text(encoding="utf-8")
        joint = (SKILL_DIR / "references" / "联合模式.md").read_text(encoding="utf-8")
        serpapi = (SKILL_DIR / "references" / "SerpApi亚马逊备用方案.md").read_text(encoding="utf-8")
        self.assertIn("跨站点重复占位", amazon)
        self.assertIn("供应商主页", source1688)
        self.assertIn("外观匹配", joint)
        self.assertIn("不得用于核验 1688", serpapi)

    def test_mode_references_tighten_identity_match_and_retry_boundaries(self):
        amazon = (SKILL_DIR / "references" / "亚马逊模式.md").read_text(encoding="utf-8")
        joint = (SKILL_DIR / "references" / "联合模式.md").read_text(encoding="utf-8")
        serpapi = (SKILL_DIR / "references" / "SerpApi亚马逊备用方案.md").read_text(encoding="utf-8")
        self.assertIn("观测不得作为身份依据", amazon)
        self.assertIn("分站观测必须保留", amazon)
        self.assertIn("图片相似但仍无法确认时，判为待核验配对", joint)
        self.assertNotIn("无法确认为待核验配对", joint)
        self.assertIn("认证/额度不可重试", serpapi)

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
        self.assertIn("模式 + 站点 + 销量来源类型 + 销量统计周期", text)
        self.assertIn("价格允许偏差只作为硬门槛", text)
        self.assertIn("0 到任务书确认的平台满分", text)

    def test_reviewed_core_contracts_are_documented(self):
        core = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
        intake = (SKILL_DIR / "references" / "需求确认与评分.md").read_text(encoding="utf-8")
        evidence = (SKILL_DIR / "references" / "证据质量.md").read_text(encoding="utf-8")
        excel = (SKILL_DIR / "references" / "Excel输出规范.md").read_text(encoding="utf-8")

        self.assertIn("任一缺失或冲突时，转为待核验，不计算总评分并从严格结果移出", core)
        for phrase in ["追加式决策日志", "仅在明确冲突时覆盖前序规则", "稳定商品 ID/配对 ID"]:
            self.assertIn(phrase, intake)
        for phrase in ["有序来源层级", "推断不得证明任何硬门槛", "字段权威性"]:
            self.assertIn(phrase, evidence)
        for phrase in [
            "任务说明、目标产品、价格基准、亚马逊候选、1688候选、货源匹配、严格结果、待核验、淘汰记录",
            "销量得分、评价数量、价格得分、稳定商品/配对 ID",
            "孤立图片、跨行图片",
        ]:
            self.assertIn(phrase, excel)

    def test_readme_and_ui_explain_v120_behavior(self):
        root = SKILL_DIR.parents[1]
        readme = (root / "README.md").read_text(encoding="utf-8")
        ui = (SKILL_DIR / "agents" / "openai.yaml").read_text(encoding="utf-8")

        for phrase in [
            "v1.2.0",
            "多产品",
            "目标产品ID",
            "固定九表",
            "确认目标产品外观",
            "目标售价",
            "目标成本",
            "价格允许偏差",
            "销量 40%",
            "价格 40%",
            "评价 20%",
            "绝对偏差",
            "嵌入商品主图",
            "亚马逊候选",
            "不凑 Top-N",
            "供应商主页",
            "生产能力",
            "ODM/OEM/定制",
            "Sorftime",
            "SerpApi",
            "外观逐项核验",
            "候选表只保留严格合格或待核验",
            "单击即可打开",
        ]:
            self.assertIn(phrase, readme)
        self.assertNotIn("Amazon候选", readme)
        self.assertNotIn("评分数量 25", readme)
        self.assertTrue((root / "tests").is_dir())
        self.assertIn("├── tests/", readme)
        for phrase in [
            'display_name: "通用跨市场选品与货源匹配"',
            "确认外观、功能和目标价格后",
            "中文 Excel",
            "销量40%、价格40%、评价20%",
            "嵌入商品主图",
            "候选表不得混入已淘汰",
            "全部 URL 单击可打开",
        ]:
            self.assertIn(phrase, ui)

    def test_v110_release_notes_preserve_documented_boundaries(self):
        release = ROOT / "docs" / "releases" / "v1.1.0.md"
        self.assertTrue(release.is_file(), "缺少 v1.1.0 中文发布说明")
        text = release.read_text(encoding="utf-8")
        for phrase in [
            "## 新增",
            "## 行为变化",
            "## 兼容性",
            "## 安装",
            "## 验证",
            "v1.0.0",
            "仍可安装",
            "scripts/scoring.py",
            "scripts/validate_workbook.py",
            "通用选品数据库模板.xlsx",
            "不预设冻结窗格",
            "可在 Excel 中手动冻结",
        ]:
            self.assertIn(phrase, text)

    def test_excel_output_reference_requires_clickable_urls_candidate_images_and_no_freeze_claim(self):
        text = (SKILL_DIR / "references" / "Excel输出规范.md").read_text(encoding="utf-8")
        core = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
        for phrase in [
            "具有 host 的有效 http/https URL 文本",
            "XLSX hyperlink 对象",
            "候选表不得出现已淘汰",
            "候选行必须嵌入",
            "必须将实际主图嵌入 Excel",
        ]:
            self.assertIn(phrase, text)
        self.assertNotIn("不要求独立 XLSX hyperlink 对象", text)
        self.assertNotIn("冻结表头", text)
        self.assertNotIn("冻结表头", core)

    def test_v111_release_notes_document_output_hardening_and_installation(self):
        release = ROOT / "docs" / "releases" / "v1.1.1.md"
        self.assertTrue(release.is_file(), "缺少 v1.1.1 中文发布说明")
        text = release.read_text(encoding="utf-8")
        for phrase in [
            "## 修复",
            "## 其他校验加固",
            "## 兼容性",
            "## 安装",
            "## 验证",
            "候选表和严格结果",
            "XLSX hyperlink",
            "外观逐项核验",
            "功能逐项核验",
            "v1.1.0",
            "v1.0.0",
            "https://github.com/rjdcrbqj/cross-market-product-selection/tree/v1.1.1/skills/cross-market-product-selection",
        ]:
            self.assertIn(phrase, text)

    def test_v120_release_notes_document_multi_product_upgrade_and_installation(self):
        release = ROOT / "docs" / "releases" / "v1.2.0.md"
        self.assertTrue(release.is_file(), "缺少 v1.2.0 中文发布说明")
        text = release.read_text(encoding="utf-8")
        for phrase in [
            "## 新增",
            "## 行为变化",
            "## 兼容性",
            "## 安装",
            "## 验证",
            "多产品",
            "目标产品ID",
            "严格多视图",
            "Amazon同类均价",
            "固定九表",
            "v1.1.1",
            "https://github.com/rjdcrbqj/cross-market-product-selection/tree/v1.2.0/skills/cross-market-product-selection",
        ]:
            self.assertIn(phrase, text)

        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn(
            "https://github.com/rjdcrbqj/cross-market-product-selection/releases/tag/v1.2.0",
            readme,
        )
        self.assertIn(
            "https://github.com/rjdcrbqj/cross-market-product-selection/tree/v1.2.0/skills/cross-market-product-selection",
            readme,
        )

    def test_readme_and_release_preserve_install_directory_urls(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        release = (ROOT / "docs" / "releases" / "v1.1.0.md").read_text(encoding="utf-8")
        install_urls = [
            "https://github.com/rjdcrbqj/cross-market-product-selection/tree/v1.1.0/skills/cross-market-product-selection",
            "https://github.com/rjdcrbqj/cross-market-product-selection/tree/v1.0.0/skills/cross-market-product-selection",
            "https://github.com/rjdcrbqj/cross-market-product-selection/tree/main/skills/cross-market-product-selection",
        ]
        for text in [readme, release]:
            for install_url in install_urls:
                self.assertIn(install_url, text)


if __name__ == "__main__":
    unittest.main()
