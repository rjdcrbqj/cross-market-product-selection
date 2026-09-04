from pathlib import Path
import posixpath
import re
import sys
import unittest
from xml.etree import ElementTree
from zipfile import ZipFile


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = ROOT / "skills" / "cross-market-product-selection" / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from validate_workbook import extract_workbook_model, validate_workbook_model


MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
OFFICE_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PACKAGE_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"

SHEET_ORDER = ["任务说明", "目标产品", "价格基准", "亚马逊候选", "1688候选", "货源匹配", "严格结果", "待核验", "淘汰记录"]
TARGET_HEADERS = [
    "目标产品ID", "目标产品名称", "用户确认状态", "视觉对标模式", "参考图1链接", "参考图2链接", "必需视图",
    "外观必须特点", "允许变化", "外观排除项", "必须功能", "可选功能", "排除功能", "Amazon目标售价",
    "Amazon价格允许偏差", "Amazon同类均价", "Amazon同类均价最低样本数", "Amazon目标站点", "1688目标成本", "1688价格允许偏差",
    "采购数量档位", "目标严格合格数量", "Amazon目标币种", "1688成本币种",
]
PRICE_HEADERS = [
    "目标产品ID", "平台", "样本商品ID", "跨站产品组ID", "站点", "样本状态", "产品本体门槛", "外观门槛",
    "功能门槛", "标准价格", "标准币种", "来源链接", "获取时间", "排除原因",
]
AMAZON_HEADERS = [
    "状态", "模式", "目标产品ID", "排名", "Amazon商品图片", "Amazon对比图片", "站点", "Amazon ASIN", "Amazon变体/SKU", "品牌", "商品标题",
    "Amazon链接", "Amazon主图链接", "Amazon对比图链接", "产品本体门槛", "外观门槛", "功能门槛", "价格/MOQ门槛",
    "详情身份门槛", "证据一致性门槛", "门槛原因", "外观逐项核验", "功能逐项核验",
    "Amazon目标售价", "Amazon实际售价", "Amazon币种",
    "Amazon销量", "Amazon销量来源类型", "Amazon销量统计周期", "Amazon评价星级", "Amazon评价数量",
    "Amazon销量得分", "Amazon价格得分", "Amazon评价得分", "Amazon产品总评分", "核心通过证据", "来源类型",
    "来源链接", "检索路径", "获取时间", "置信度", "冲突说明", "决策日志引用",
]

SUPPLY_HEADERS = [
    "状态", "模式", "目标产品ID", "排名", "1688商品图片", "1688对比图片", "1688商品ID", "1688 SKU/规格", "供应商ID", "店铺名称", "商品标题",
    "1688链接", "供应商主页", "1688主图链接", "1688对比图链接", "产品本体门槛", "外观门槛", "功能门槛", "价格/MOQ门槛",
    "供应商门槛", "生产能力门槛", "ODM/OEM/定制门槛", "证据一致性门槛", "门槛原因", "目标成本",
    "外观逐项核验", "功能逐项核验", "实际单价", "成本币种", "采购数量档位", "MOQ", "阶梯价", "1688销量", "1688销量来源类型", "1688销量统计周期",
    "1688评价星级", "1688评价数量", "1688销量得分", "1688价格得分", "1688评价得分", "1688产品总评分",
    "生产能力证据", "ODM/OEM/定制证据", "核心通过证据", "来源类型", "来源链接", "检索路径", "获取时间",
    "置信度", "冲突说明", "决策日志引用",
]

MATCH_HEADERS = [
    "状态", "模式", "目标产品ID", "排名", "记录/配对ID", "Amazon商品图片", "Amazon对比图片", "1688商品图片", "1688对比图片", "站点", "Amazon ASIN",
    "Amazon变体/SKU", "1688商品ID", "1688 SKU/规格", "供应商ID", "Amazon商品标题", "1688商品标题",
    "Amazon链接", "1688链接", "Amazon主图链接", "Amazon对比图链接", "1688主图链接", "1688对比图链接", "供应商主页", "产品本体门槛", "外观门槛",
    "功能门槛", "价格/MOQ门槛", "目标成本", "实际单价", "成本币种", "采购数量档位", "MOQ", "阶梯价", "详情身份门槛", "供应商门槛", "生产能力门槛", "ODM/OEM/定制门槛",
    "证据一致性门槛", "外观逐项核验", "功能逐项核验", "市场机会得分", "市场机会结论", "市场机会证据",
    "供应能力得分", "供应能力结论", "供应能力证据", "匹配质量得分", "匹配质量结论", "匹配质量证据",
    "最终配对得分", "生产能力证据", "ODM/OEM/定制证据", "主要限制", "来源类型", "来源链接", "检索路径",
    "获取时间", "置信度", "冲突说明", "决策日志引用",
]

STRICT_HEADERS = [
    "状态", "模式", "目标产品ID", "排名", "Amazon商品图片", "Amazon对比图片", "1688商品图片", "1688对比图片", "记录/配对ID", "站点", "Amazon ASIN",
    "Amazon变体/SKU", "1688商品ID", "1688 SKU/规格", "供应商ID", "标题/配对说明", "Amazon链接", "1688链接",
    "供应商主页", "Amazon主图链接", "Amazon对比图链接", "1688主图链接", "1688对比图链接", "产品本体门槛", "外观门槛", "功能门槛", "价格/MOQ门槛",
    "详情身份门槛", "供应商门槛", "生产能力门槛", "ODM/OEM/定制门槛", "证据一致性门槛", "外观逐项核验",
    "功能逐项核验", "Amazon目标售价", "Amazon实际售价", "Amazon币种", "Amazon销量", "Amazon销量来源类型",
    "Amazon销量统计周期", "Amazon评价星级", "Amazon评价数量", "Amazon销量得分", "Amazon价格得分", "Amazon评价得分",
    "Amazon产品总评分", "目标成本", "实际单价", "成本币种", "采购数量档位", "MOQ", "阶梯价", "1688销量", "1688销量来源类型", "1688销量统计周期",
    "1688评价星级", "1688评价数量", "1688销量得分", "1688价格得分", "1688评价得分", "1688产品总评分",
    "市场机会得分", "市场机会结论", "市场机会证据", "供应能力得分", "供应能力结论", "供应能力证据",
    "匹配质量得分", "匹配质量结论", "匹配质量证据", "最终配对得分", "核心通过证据", "生产能力证据",
    "ODM/OEM/定制证据", "主要限制", "来源类型", "来源链接", "检索路径", "获取时间", "置信度", "冲突说明",
    "决策日志引用", "输出时间",
]

PENDING_HEADERS = [
    "状态", "模式", "目标产品ID", "记录/配对ID", "平台", "商品图片", "Amazon ASIN", "1688商品ID", "标题/配对说明",
    "缺失或冲突门槛", "现有证据", "补证据动作", "Amazon链接", "1688链接", "主图链接", "证据链接",
    "用户保留决定", "决策日志引用", "更新时间",
]
REJECTED_HEADERS = [
    "状态", "模式", "目标产品ID", "记录/配对ID", "平台", "商品图片", "Amazon ASIN", "1688商品ID", "标题/配对说明",
    "失败门槛", "失败事实", "证据链接", "Amazon链接", "1688链接", "决策日志引用", "淘汰时间",
]

EXPECTED_HEADERS = {
    "目标产品": TARGET_HEADERS,
    "价格基准": PRICE_HEADERS,
    "亚马逊候选": AMAZON_HEADERS,
    "1688候选": SUPPLY_HEADERS,
    "货源匹配": MATCH_HEADERS,
    "严格结果": STRICT_HEADERS,
    "待核验": PENDING_HEADERS,
    "淘汰记录": REJECTED_HEADERS,
}


def _relationship_part(source_part):
    directory, filename = posixpath.split(source_part)
    return posixpath.join(directory, "_rels", f"{filename}.rels")


def _resolve_part(source_part, target):
    target = target.replace("\\", "/")
    if target.startswith("/"):
        return posixpath.normpath(target.lstrip("/"))
    return posixpath.normpath(posixpath.join(posixpath.dirname(source_part), target))


def _column_name(index):
    value = index
    result = ""
    while value:
        value, remainder = divmod(value - 1, 26)
        result = chr(65 + remainder) + result
    return result


class XlsxContract:
    def __init__(self, path):
        self.archive = ZipFile(path)
        self.shared_strings = self._shared_strings()
        self.workbook_root = self._root("xl/workbook.xml")
        workbook_rels = self._relationships("xl/workbook.xml")
        self.sheet_order = []
        self.sheet_parts = {}
        for sheet in self.workbook_root.findall(f".//{{{MAIN_NS}}}sheet"):
            name = sheet.get("name")
            rel_id = sheet.get(f"{{{OFFICE_REL_NS}}}id")
            self.sheet_order.append(name)
            self.sheet_parts[name] = workbook_rels[rel_id][0]

    def close(self):
        self.archive.close()

    def _root(self, part):
        return ElementTree.fromstring(self.archive.read(part))

    def _relationships(self, source_part):
        root = self._root(_relationship_part(source_part))
        result = {}
        for rel in root.findall(f"{{{PACKAGE_REL_NS}}}Relationship"):
            result[rel.get("Id")] = (_resolve_part(source_part, rel.get("Target")), rel.get("Type", ""))
        return result

    def _shared_strings(self):
        if "xl/sharedStrings.xml" not in self.archive.namelist():
            return []
        root = self._root("xl/sharedStrings.xml")
        return ["".join(node.text or "" for node in item.iter(f"{{{MAIN_NS}}}t")) for item in root]

    def sheet_root(self, sheet_name):
        return self._root(self.sheet_parts[sheet_name])

    def cell(self, sheet_name, address):
        return self.sheet_root(sheet_name).find(f".//{{{MAIN_NS}}}c[@r='{address}']")

    def value(self, sheet_name, address):
        cell = self.cell(sheet_name, address)
        if cell is None:
            return ""
        cell_type = cell.get("t")
        if cell_type == "inlineStr":
            return "".join(node.text or "" for node in cell.iter(f"{{{MAIN_NS}}}t"))
        value_node = cell.find(f"{{{MAIN_NS}}}v")
        if value_node is None or value_node.text is None:
            return ""
        raw = value_node.text
        if cell_type == "s":
            return self.shared_strings[int(raw)]
        if cell_type in {"str", "e"}:
            return raw
        try:
            return float(raw)
        except ValueError:
            return raw

    def formula(self, sheet_name, address):
        cell = self.cell(sheet_name, address)
        if cell is None:
            return ""
        formula_node = cell.find(f"{{{MAIN_NS}}}f")
        return "" if formula_node is None else formula_node.text or ""

    def table_refs(self, sheet_name):
        sheet_part = self.sheet_parts[sheet_name]
        relationships = self._relationships(sheet_part)
        refs = []
        for table_part in self.sheet_root(sheet_name).findall(f".//{{{MAIN_NS}}}tablePart"):
            rel_id = table_part.get(f"{{{OFFICE_REL_NS}}}id")
            table_path, rel_type = relationships[rel_id]
            if rel_type.endswith("/table"):
                refs.append(self._root(table_path).get("ref"))
        return refs

    def column_width(self, sheet_name, column_index):
        for column in self.sheet_root(sheet_name).findall(f".//{{{MAIN_NS}}}cols/{{{MAIN_NS}}}col"):
            if int(column.get("min")) <= column_index <= int(column.get("max")):
                return float(column.get("width"))
        return None

    def row_height(self, sheet_name, row_number):
        row = self.sheet_root(sheet_name).find(f".//{{{MAIN_NS}}}row[@r='{row_number}']")
        return None if row is None or row.get("ht") is None else float(row.get("ht"))

    def data_validations(self, sheet_name):
        result = []
        for validation in self.sheet_root(sheet_name).findall(f".//{{{MAIN_NS}}}dataValidation"):
            formula = validation.find(f"{{{MAIN_NS}}}formula1")
            result.append((validation.get("type"), validation.get("sqref", ""), "" if formula is None else formula.text or ""))
        return result

    def font_name(self, sheet_name, address):
        cell = self.cell(sheet_name, address)
        style_index = 0 if cell is None or cell.get("s") is None else int(cell.get("s"))
        styles = self._root("xl/styles.xml")
        cell_xfs = styles.find(f"{{{MAIN_NS}}}cellXfs")
        fonts = styles.find(f"{{{MAIN_NS}}}fonts")
        font_index = int(cell_xfs[style_index].get("fontId", "0"))
        name = fonts[font_index].find(f"{{{MAIN_NS}}}name")
        return None if name is None else name.get("val")


class TemplateContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.template = ROOT / "skills" / "cross-market-product-selection" / "assets" / "通用选品数据库模板.xlsx"
        cls.xlsx = XlsxContract(cls.template)
        cls.model = extract_workbook_model(cls.template)

    @classmethod
    def tearDownClass(cls):
        cls.xlsx.close()

    def test_sheet_order_titles_descriptions_and_header_anchors_are_stable(self):
        self.assertEqual(self.xlsx.sheet_order, SHEET_ORDER)
        self.assertEqual(validate_workbook_model(self.model), [])
        for sheet_name in SHEET_ORDER:
            with self.subTest(sheet=sheet_name):
                self.assertRegex(str(self.xlsx.value(sheet_name, "A1")), r"[\u3400-\u9fff]")
                self.assertRegex(str(self.xlsx.value(sheet_name, "A2")), r"[\u3400-\u9fff]")
                expected_anchor = "字段" if sheet_name == "任务说明" else "目标产品ID" if sheet_name in {"目标产品", "价格基准"} else "状态"
                self.assertEqual(self.xlsx.value(sheet_name, "A3"), expected_anchor)

    def test_each_excel_table_starts_at_real_header_row(self):
        for sheet_name in SHEET_ORDER:
            with self.subTest(sheet=sheet_name):
                if sheet_name == "任务说明":
                    refs = self.xlsx.table_refs(sheet_name)
                    self.assertEqual(len(refs), 1)
                    self.assertTrue(refs[0].startswith("A3:C"))
                else:
                    expected_ref = f"A3:{_column_name(len(EXPECTED_HEADERS[sheet_name]))}4"
                    self.assertEqual(self.xlsx.table_refs(sheet_name), [expected_ref])

    def test_fonts_image_dimensions_row_heights_and_status_validation_are_usable(self):
        for sheet_name in SHEET_ORDER:
            with self.subTest(sheet=sheet_name, contract="font"):
                for address in ("A1", "A2", "A3", "A4"):
                    self.assertEqual(self.xlsx.font_name(sheet_name, address), "Microsoft YaHei")

        expected_statuses = {
            "亚马逊候选": '"严格合格,待核验"',
            "1688候选": '"严格合格,待核验"',
            "货源匹配": '"严格合格,待核验"',
            "严格结果": '"严格合格"',
            "待核验": '"待核验"',
            "淘汰记录": '"已淘汰"',
        }
        for sheet_name in SHEET_ORDER[3:]:
            headers = self.model.headers[sheet_name]
            with self.subTest(sheet=sheet_name, contract="image sizing"):
                image_columns = [index + 1 for index, header in enumerate(headers) if "图片" in header]
                self.assertTrue(image_columns)
                for column_index in image_columns:
                    width = self.xlsx.column_width(sheet_name, column_index)
                    self.assertIsNotNone(width)
                    self.assertGreaterEqual(width, 18)
                    self.assertLessEqual(width, 22)
                self.assertGreaterEqual(self.xlsx.row_height(sheet_name, 4), 90)
                self.assertLessEqual(self.xlsx.row_height(sheet_name, 4), 110)

            with self.subTest(sheet=sheet_name, contract="status validation"):
                validations = self.xlsx.data_validations(sheet_name)
                list_validations = [item for item in validations if item[0] == "list"]
                self.assertEqual(
                    list_validations,
                    [("list", "A4:A103", expected_statuses[sheet_name])],
                )

    def test_candidate_and_joint_headers_preserve_exact_order(self):
        for sheet_name, expected in EXPECTED_HEADERS.items():
            with self.subTest(sheet=sheet_name):
                self.assertEqual(self.model.headers[sheet_name], expected)

    def test_task_confirmation_fields_weights_and_policies_are_visible(self):
        rows_by_field = {
            row.values["字段"]: row
            for row in self.model.rows
            if row.sheet == "任务说明" and row.values.get("字段")
        }
        expected_fields = {"模式", "业务目标", "市场/范围", "目标产品数量", "销量统计周期", "评价口径", "跨站点去重口径"}
        self.assertTrue(expected_fields.issubset(rows_by_field), expected_fields - rows_by_field.keys())
        self.assertAlmostEqual(float(rows_by_field["销量权重"].values["确认值"]), 0.4)
        self.assertAlmostEqual(float(rows_by_field["价格权重"].values["确认值"]), 0.4)
        self.assertAlmostEqual(float(rows_by_field["评价权重"].values["确认值"]), 0.2)
        total_row = rows_by_field["权重合计"].row
        self.assertRegex(self.xlsx.formula("任务说明", f"B{total_row}"), r"SUM\(B\d+:B\d+\)")
        self.assertAlmostEqual(float(self.xlsx.value("任务说明", f"B{total_row}")), 1.0)
        for field in ("销量权重", "价格权重", "评价权重"):
            self.assertIn("固定", rows_by_field[field].values["填写说明"])
        for field in ("最终配对评分公式", "市场机会权重", "供应能力权重", "匹配质量权重"):
            self.assertIn(field, rows_by_field)
            self.assertTrue(rows_by_field[field].values["确认值"] in (None, ""))
        self.assertIn("每个目标产品", rows_by_field["价格评分规则"].values["确认值"])
        self.assertIn("双向接近", rows_by_field["价格评分规则"].values["确认值"])
        self.assertIn("转待核验", rows_by_field["证据不足处理"].values["确认值"])
        self.assertIn("凑数", rows_by_field["结果数量规则"].values["填写说明"])

        target_headers = self.model.headers["目标产品"]
        for field in ("视觉对标模式", "参考图1链接", "必需视图", "Amazon同类均价", "目标严格合格数量"):
            self.assertIn(field, target_headers)

    def test_scoring_formulas_enforce_strict_groups_domains_and_fixed_weights(self):
        formula_contracts = (
            ("亚马逊候选", "Amazon销量得分", "Amazon价格得分", "Amazon评价得分", "Amazon产品总评分", ("目标产品ID", "模式", "站点", "Amazon销量来源类型", "Amazon销量统计周期")),
            ("1688候选", "1688销量得分", "1688价格得分", "1688评价得分", "1688产品总评分", ("目标产品ID", "模式", "1688销量来源类型", "1688销量统计周期")),
            ("严格结果", "Amazon销量得分", "Amazon价格得分", "Amazon评价得分", "Amazon产品总评分", ("目标产品ID", "模式", "站点", "Amazon销量来源类型", "Amazon销量统计周期")),
            ("严格结果", "1688销量得分", "1688价格得分", "1688评价得分", "1688产品总评分", ("目标产品ID", "模式", "1688销量来源类型", "1688销量统计周期")),
        )
        for sheet_name, sales_header, price_header, rating_header, total_header, group_headers in formula_contracts:
            headers = self.model.headers[sheet_name]
            formulas = {
                header: self.xlsx.formula(sheet_name, f"{_column_name(headers.index(header) + 1)}4")
                for header in (sales_header, price_header, rating_header, total_header)
            }
            with self.subTest(sheet=sheet_name, total=total_header):
                for formula in formulas.values():
                    self.assertIn('$A4<>"严格合格"', formula)
                    self.assertIn('""', formula)
                    self.assertIn("ROUND(", formula)
                self.assertIn("COUNTIFS(", formulas[sales_header])
                self.assertIn("MINIFS(", formulas[sales_header])
                self.assertIn("MAXIFS(", formulas[sales_header])
                for group_header in group_headers:
                    group_column = _column_name(headers.index(group_header) + 1)
                    self.assertIn(f"${group_column}$4:${group_column}$103", formulas[sales_header])
                self.assertIn("MAX(0,100*(1-ABS(", formulas[price_header])
                self.assertNotIn("价格允许偏差", formulas[price_header])
                self.assertIn("<0", formulas[rating_header])
                self.assertIn(">", formulas[rating_header])
                self.assertNotIn("MIN(", formulas[rating_header])
                self.assertIn("*0.4", formulas[total_header])
                self.assertIn("*0.2", formulas[total_header])

    def test_joint_dimensions_are_separate_and_no_unconfirmed_final_formula_exists(self):
        for sheet_name in ("货源匹配", "严格结果"):
            headers = self.model.headers[sheet_name]
            for prefix in ("市场机会", "供应能力", "匹配质量"):
                self.assertIn(f"{prefix}得分", headers)
                self.assertIn(f"{prefix}结论", headers)
                self.assertIn(f"{prefix}证据", headers)
            final_column = _column_name(headers.index("最终配对得分") + 1)
            self.assertEqual(self.xlsx.formula(sheet_name, f"{final_column}4"), "")
            self.assertEqual(self.xlsx.value(sheet_name, f"{final_column}4"), "")


if __name__ == "__main__":
    unittest.main()
