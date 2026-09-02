from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = ROOT / "skills" / "cross-market-product-selection" / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from validate_workbook import extract_workbook_model


AMAZON_HEADERS = [
    "状态", "排名", "商品图片", "ASIN", "站点", "品牌", "商品标题", "商品链接", "主图链接", "变体/SKU",
    "产品本体门槛", "外观门槛", "功能门槛", "价格范围门槛", "详情身份门槛", "证据一致性门槛", "门槛原因",
    "目标售价", "实际售价", "币种", "价格偏差率", "月销量", "销量统计周期", "评价星级", "评价数量",
    "销量得分", "价格得分", "评价得分", "总评分", "来源类型", "证据链接", "检索路径", "获取时间", "置信度", "冲突说明", "决策日志引用",
]

SUPPLY_HEADERS = [
    "状态", "排名", "商品图片", "1688商品ID", "商品标题", "商品链接", "主图链接", "SKU/规格",
    "产品本体门槛", "外观门槛", "功能门槛", "价格范围门槛", "供应商门槛", "证据一致性门槛", "门槛原因",
    "目标成本", "实际单价", "币种", "价格偏差率", "采购数量档位", "MOQ", "近30天销量", "评价星级", "评价数量",
    "销量得分", "价格得分", "评价得分", "总评分", "店铺名称", "供应商ID", "供应商主页", "生产能力证据",
    "ODM/OEM/定制证据", "交期", "来源类型", "证据链接", "检索路径", "获取时间", "置信度", "冲突说明", "决策日志引用",
]


class TemplateContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        template = ROOT / "skills" / "cross-market-product-selection" / "assets" / "通用选品数据库模板.xlsx"
        cls.model = None
        cls.extraction_error = None
        try:
            cls.model = extract_workbook_model(template)
        except (OSError, ValueError) as error:
            cls.extraction_error = error

    def require_model(self):
        self.assertIsNone(self.extraction_error, f"模板结构不可读：{self.extraction_error}")
        return self.model

    def test_required_sheets_exist(self):
        model = self.require_model()
        expected = {"任务说明", "亚马逊候选", "1688候选", "货源匹配", "严格结果", "待核验", "淘汰记录"}
        self.assertEqual(model.sheets, expected)

    def test_product_sheets_have_exact_image_and_score_contract(self):
        model = self.require_model()
        self.assertEqual(model.headers.get("亚马逊候选"), AMAZON_HEADERS)
        self.assertEqual(model.headers.get("1688候选"), SUPPLY_HEADERS)

        strict_headers = model.headers["严格结果"]
        for header in [
            "状态", "Amazon商品图片", "1688商品图片", "Amazon主图链接", "1688主图链接",
            "外观门槛", "功能门槛", "销量得分", "价格得分", "评价得分", "总评分",
        ]:
            self.assertIn(header, strict_headers, f"严格结果: {header}")

        match_headers = model.headers["货源匹配"]
        for header in ["Amazon商品图片", "1688商品图片", "Amazon主图链接", "1688主图链接"]:
            self.assertIn(header, match_headers, f"货源匹配: {header}")

    def test_task_sheet_contains_confirmation_fields(self):
        model = self.require_model()
        headers = model.headers["任务说明"]
        self.assertIn("字段", headers)
        fields = {
            row.values.get("字段")
            for row in model.rows
            if row.sheet == "任务说明" and row.values.get("字段")
        }
        expected = {
            "参考图片/链接", "外观必须特点", "允许变化", "外观排除项", "必须功能", "可选功能", "排除功能",
            "目标售价", "目标成本", "币种", "采购数量档位", "价格允许偏差", "销量统计周期", "评价口径",
            "跨站点去重口径", "用户确认状态",
        }
        self.assertTrue(expected.issubset(fields), expected - fields)


if __name__ == "__main__":
    unittest.main()
