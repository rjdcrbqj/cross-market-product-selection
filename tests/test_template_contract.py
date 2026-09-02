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

SHEET_ORDER = ["任务说明", "亚马逊候选", "1688候选", "货源匹配", "严格结果", "待核验", "淘汰记录"]
TABLE_REFS = {
    "任务说明": "A3:C37",
    "亚马逊候选": "A3:AJ4",
    "1688候选": "A3:AO4",
    "货源匹配": "A3:AR4",
    "严格结果": "A3:AQ4",
    "待核验": "A3:R4",
    "淘汰记录": "A3:O4",
}

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

MATCH_HEADERS = [
    "状态", "排名", "记录/配对ID", "Amazon商品图片", "1688商品图片", "Amazon ASIN", "1688商品ID",
    "Amazon商品标题", "1688商品标题", "Amazon链接", "1688链接", "Amazon主图链接", "1688主图链接", "供应商主页",
    "产品本体匹配", "外观匹配", "功能匹配", "规格匹配", "成本/MOQ匹配", "证据一致性门槛",
    "外观匹配说明", "功能匹配说明", "目标成本", "实际单价", "币种", "价格偏差率", "Amazon月销量",
    "Amazon评价星级", "Amazon评价数量", "销量得分", "价格得分", "评价得分", "匹配总分",
    "生产能力证据", "ODM/OEM/定制证据", "核心匹配证据", "主要限制", "来源类型", "来源链接", "检索路径",
    "获取时间", "置信度", "冲突说明", "决策日志引用",
]

STRICT_HEADERS = [
    "状态", "模式", "排名", "Amazon商品图片", "1688商品图片", "记录/配对ID", "站点", "Amazon ASIN", "1688商品ID",
    "标题/配对说明", "Amazon链接", "1688链接", "供应商主页", "Amazon主图链接", "1688主图链接",
    "外观门槛", "功能门槛", "证据一致性门槛", "外观匹配说明", "功能匹配说明", "目标价格", "实际价格", "币种",
    "价格偏差率", "销量", "销量统计周期", "评价星级", "评价数量", "销量得分", "价格得分", "评价得分", "总评分",
    "核心通过证据", "ODM/OEM/定制证据", "主要限制", "来源类型", "来源链接", "检索路径", "获取时间", "置信度",
    "冲突说明", "决策日志引用", "输出时间",
]


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
                expected_anchor = "字段" if sheet_name == "任务说明" else "状态"
                self.assertEqual(self.xlsx.value(sheet_name, "A3"), expected_anchor)

    def test_each_excel_table_starts_at_real_header_row(self):
        for sheet_name, expected_ref in TABLE_REFS.items():
            with self.subTest(sheet=sheet_name):
                self.assertEqual(self.xlsx.table_refs(sheet_name), [expected_ref])

    def test_fonts_image_dimensions_row_heights_and_status_validation_are_usable(self):
        for sheet_name in SHEET_ORDER:
            with self.subTest(sheet=sheet_name, contract="font"):
                for address in ("A1", "A2", "A3", "A4"):
                    self.assertEqual(self.xlsx.font_name(sheet_name, address), "Microsoft YaHei")

        for sheet_name in SHEET_ORDER[1:]:
            headers = self.model.headers[sheet_name]
            with self.subTest(sheet=sheet_name, contract="image sizing"):
                image_columns = [index + 1 for index, header in enumerate(headers) if "商品图片" in header]
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
                status_validation = [item for item in validations if item[0] == "list" and "A4:A103" in item[1].split()]
                self.assertEqual(len(status_validation), 1)
                for status in ("严格", "待核验", "淘汰"):
                    self.assertIn(status, status_validation[0][2])

    def test_candidate_and_joint_headers_preserve_exact_order(self):
        self.assertEqual(self.model.headers["亚马逊候选"], AMAZON_HEADERS)
        self.assertEqual(self.model.headers["1688候选"], SUPPLY_HEADERS)
        self.assertEqual(self.model.headers["货源匹配"], MATCH_HEADERS)
        self.assertEqual(self.model.headers["严格结果"], STRICT_HEADERS)

    def test_task_confirmation_fields_weights_and_policies_are_visible(self):
        rows_by_field = {
            row.values["字段"]: row
            for row in self.model.rows
            if row.sheet == "任务说明" and row.values.get("字段")
        }
        expected_fields = {
            "参考图片/链接", "外观必须特点", "允许变化", "外观排除项", "必须功能", "可选功能", "排除功能",
            "目标售价", "目标成本", "币种", "采购数量档位", "价格允许偏差", "销量统计周期", "评价口径",
            "跨站点去重口径", "用户确认状态",
        }
        self.assertTrue(expected_fields.issubset(rows_by_field), expected_fields - rows_by_field.keys())
        self.assertAlmostEqual(float(rows_by_field["销量权重"].values["确认值"]), 0.4)
        self.assertAlmostEqual(float(rows_by_field["价格权重"].values["确认值"]), 0.4)
        self.assertAlmostEqual(float(rows_by_field["评价权重"].values["确认值"]), 0.2)
        self.assertEqual(self.xlsx.formula("任务说明", "B30"), "SUM(B27:B29)")
        self.assertAlmostEqual(float(self.xlsx.value("任务说明", "B30")), 1.0)
        self.assertIn("Amazon 对目标售价", rows_by_field["价格评分规则"].values["确认值"])
        self.assertIn("1688 对目标成本", rows_by_field["价格评分规则"].values["确认值"])
        self.assertIn("双向接近", rows_by_field["价格评分规则"].values["确认值"])
        self.assertIn("转待核验", rows_by_field["证据不足处理"].values["确认值"])
        self.assertIn("凑数", rows_by_field["结果数量规则"].values["填写说明"])

    def test_scoring_formulas_keep_missing_inputs_blank_and_reference_visible_assumptions(self):
        formula_contracts = {
            "亚马逊候选": ("$V$4:$V$103", "总评分"),
            "1688候选": ("$V$4:$V$103", "总评分"),
            "货源匹配": ("$AA$4:$AA$103", "匹配总分"),
            "严格结果": ("$Y$4:$Y$103", "总评分"),
        }
        for sheet_name, (sales_range, total_header) in formula_contracts.items():
            headers = self.model.headers[sheet_name]
            formulas = {
                header: self.xlsx.formula(sheet_name, f"{_column_name(headers.index(header) + 1)}4")
                for header in ("销量得分", "价格得分", "评价得分", total_header)
            }
            with self.subTest(sheet=sheet_name):
                self.assertIn(sales_range, formulas["销量得分"])
                self.assertNotRegex(formulas["销量得分"], r"\$?[A-Z]+:\$?[A-Z]+")
                for header in ("价格得分", "评价得分", total_header):
                    self.assertIn("IF(", formulas[header])
                    self.assertIn('""', formulas[header])
                for task_cell in ("$B$20", "$B$32", "$B$33"):
                    self.assertIn(f"'任务说明'!{task_cell}", formulas["价格得分"])
                for task_cell in ("$B$31", "$B$33"):
                    self.assertIn(f"'任务说明'!{task_cell}", formulas["评价得分"])
                for task_cell in ("$B$27", "$B$28", "$B$29"):
                    self.assertIn(f"'任务说明'!{task_cell}", formulas[total_header])


if __name__ == "__main__":
    unittest.main()
