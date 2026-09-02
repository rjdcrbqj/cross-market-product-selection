from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from zipfile import ZipFile


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "skills" / "cross-market-product-selection" / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

import validate_workbook
from validate_workbook import RowRecord, WorkbookModel, validate_workbook_model


REQUIRED_SHEETS = {
    "任务说明",
    "亚马逊候选",
    "1688候选",
    "货源匹配",
    "严格结果",
    "待核验",
    "淘汰记录",
}


def model(rows=(), headers=None, mode=None):
    return WorkbookModel(
        sheets=set(REQUIRED_SHEETS),
        headers=headers
        or {
            "严格结果": [
                "状态",
                "商品图片",
                "主图链接",
                "商品ID",
                "外观门槛",
                "功能门槛",
                "销量得分",
                "价格得分",
                "评价得分",
                "总评分",
            ]
        },
        rows=list(rows),
        mode=mode,
    )


def strict_values(**overrides):
    values = {
        "状态": "严格合格",
        "商品ID": "A1",
        "主图链接": "https://example.com/a.jpg",
        "外观门槛": "通过",
        "功能门槛": "通过",
        "销量得分": 100,
        "价格得分": 90,
        "评价得分": 80,
        "总评分": 92,
    }
    values.update(overrides)
    return values


def _write_ooxml_fixture(path):
    workbook = """<?xml version="1.0" encoding="UTF-8"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
 xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets>
    <sheet name="严格结果" sheetId="1" r:id="rIdStrict"/>
    <sheet name="待核验" sheetId="2" r:id="rIdPending"/>
    <sheet name="1688候选" sheetId="3" r:id="rId1688"/>
  </sheets>
</workbook>"""
    workbook_rels = """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rIdPending" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="/xl/worksheets/pending.xml"/>
  <Relationship Id="rIdStrict" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/strict.xml"/>
  <Relationship Id="rId1688" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/source1688.xml"/>
</Relationships>"""
    shared_strings = """<?xml version="1.0" encoding="UTF-8"?>
<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <si><t>状态</t></si>
  <si><t>商品图片</t></si>
  <si><t>主图链接</t></si>
  <si><t>销量得分</t></si>
  <si><t>价格得分</t></si>
  <si><t>评价得分</t></si>
  <si><t>总评分</t></si>
  <si><t>外观门槛</t></si>
  <si><t>功能门槛</t></si>
  <si><r><t>严格</t></r><r><t>合格</t></r></si>
  <si><t>通过</t></si>
</sst>"""
    strict_sheet = """<?xml version="1.0" encoding="UTF-8"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
 xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheetData>
    <row r="1"><c r="A1" t="inlineStr"><is><t>严格结果标题</t></is></c></row>
    <row r="2"><c r="A2" t="inlineStr"><is><t>说明：以下为数据</t></is></c></row>
    <row r="3">
      <c r="A3" t="s"><v>0</v></c>
      <c r="B3" t="inlineStr"><is><t>Amazon ASIN</t></is></c>
      <c r="C3" t="s"><v>1</v></c>
      <c r="D3" t="s"><v>2</v></c>
      <c r="E3" t="s"><v>3</v></c>
      <c r="F3" t="s"><v>4</v></c>
      <c r="G3" t="s"><v>5</v></c>
      <c r="H3" t="s"><v>6</v></c>
      <c r="I3" t="s"><v>7</v></c>
      <c r="J3" t="s"><v>8</v></c>
    </row>
    <row r="4">
      <c r="A4" t="s"><v>9</v></c>
      <c r="B4" t="inlineStr"><is><t>B0FIXTURE1</t></is></c>
      <c r="D4" t="inlineStr"><is><t>https://example.com/a.jpg</t></is></c>
      <c r="E4"><v>100</v></c><c r="F4"><v>90</v></c><c r="G4"><v>80</v></c>
      <c r="H4"><f>E4*0.4+F4*0.4+G4*0.2</f><v>92</v></c>
      <c r="I4" t="s"><v>10</v></c><c r="J4" t="s"><v>10</v></c>
    </row>
    <row r="5">
      <c r="A5" t="s"><v>9</v></c>
      <c r="B5" t="inlineStr"><is><t>B0FIXTURE2</t></is></c>
      <c r="D5" t="inlineStr"><is><t>https://example.com/b.jpg</t></is></c>
      <c r="E5"><v>90</v></c><c r="F5"><v>90</v></c><c r="G5"><v>90</v></c>
      <c r="H5"><f>E5*0.4+F5*0.4+G5*0.2</f><v>90</v></c>
      <c r="I5" t="s"><v>10</v></c><c r="J5" t="s"><v>10</v></c>
    </row>
  </sheetData>
  <drawing r:id="rIdDrawing"/>
</worksheet>"""
    pending_sheet = """<?xml version="1.0" encoding="UTF-8"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <sheetData>
    <row r="1"><c r="A1" t="inlineStr"><is><t>状态</t></is></c><c r="B1" t="inlineStr"><is><t>商品ID</t></is></c></row>
    <row r="2"><c r="A2" t="inlineStr"><is><t>待核验</t></is></c><c r="B2" t="str"><v>PENDING-1</v></c></row>
  </sheetData>
</worksheet>"""
    strict_rels = """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rIdDrawing" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/drawing" Target="../drawings/drawing1.xml"/>
</Relationships>"""
    source_1688_sheet = """<?xml version="1.0" encoding="UTF-8"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>
  <row r="1"><c r="A1" t="inlineStr"><is><t>状态</t></is></c><c r="B1" t="inlineStr"><is><t>1688商品ID</t></is></c></row>
</sheetData></worksheet>"""
    drawing = """<?xml version="1.0" encoding="UTF-8"?>
<xdr:wsDr xmlns:xdr="http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing"
 xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
 xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <xdr:oneCellAnchor>
    <xdr:from><xdr:col>2</xdr:col><xdr:colOff>0</xdr:colOff><xdr:row>3</xdr:row><xdr:rowOff>0</xdr:rowOff></xdr:from>
    <xdr:ext cx="1" cy="1"/><xdr:pic><xdr:blipFill><a:blip r:embed="rIdImage"/></xdr:blipFill></xdr:pic><xdr:clientData/>
  </xdr:oneCellAnchor>
  <xdr:twoCellAnchor>
    <xdr:from><xdr:col>2</xdr:col><xdr:colOff>0</xdr:colOff><xdr:row>4</xdr:row><xdr:rowOff>0</xdr:rowOff></xdr:from>
    <xdr:to><xdr:col>3</xdr:col><xdr:colOff>0</xdr:colOff><xdr:row>5</xdr:row><xdr:rowOff>0</xdr:rowOff></xdr:to>
    <xdr:pic><xdr:blipFill><a:blip r:embed="rIdNotMedia"/></xdr:blipFill></xdr:pic><xdr:clientData/>
  </xdr:twoCellAnchor>
</xdr:wsDr>"""
    drawing_rels = """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rIdImage" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="../media/image1.png"/>
  <Relationship Id="rIdNotMedia" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="../embeddings/object.bin"/>
</Relationships>"""
    with ZipFile(path, "w") as archive:
        archive.writestr("xl/workbook.xml", workbook)
        archive.writestr("xl/_rels/workbook.xml.rels", workbook_rels)
        archive.writestr("xl/sharedStrings.xml", shared_strings)
        archive.writestr("xl/worksheets/strict.xml", strict_sheet)
        archive.writestr("xl/worksheets/pending.xml", pending_sheet)
        archive.writestr("xl/worksheets/source1688.xml", source_1688_sheet)
        archive.writestr("xl/worksheets/_rels/strict.xml.rels", strict_rels)
        archive.writestr("xl/drawings/drawing1.xml", drawing)
        archive.writestr("xl/drawings/_rels/drawing1.xml.rels", drawing_rels)
        archive.writestr("xl/media/image1.png", b"fixture-image")
        archive.writestr("xl/embeddings/object.bin", b"not-an-image-part")


def _write_empty_valid_ooxml_fixture(path):
    sheets = []
    relationships = []
    sheet_parts = {}
    for index, name in enumerate(sorted(REQUIRED_SHEETS), start=1):
        relationship_id = f"rId{index}"
        sheets.append(f'<sheet name="{name}" sheetId="{index}" r:id="{relationship_id}"/>')
        relationships.append(
            f'<Relationship Id="{relationship_id}" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
            f'Target="worksheets/sheet{index}.xml"/>'
        )
        sheet_parts[f"xl/worksheets/sheet{index}.xml"] = """<?xml version="1.0" encoding="UTF-8"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>
  <row r="1"><c r="A1" t="inlineStr"><is><t>状态</t></is></c></row>
</sheetData></worksheet>"""
    workbook = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>'
        + "".join(sheets)
        + "</sheets></workbook>"
    )
    workbook_rels = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        + "".join(relationships)
        + "</Relationships>"
    )
    with ZipFile(path, "w") as archive:
        archive.writestr("xl/workbook.xml", workbook)
        archive.writestr("xl/_rels/workbook.xml.rels", workbook_rels)
        for name, content in sheet_parts.items():
            archive.writestr(name, content)


class WorkbookValidatorSemanticTests(unittest.TestCase):
    def test_valid_legacy_strict_row_passes(self):
        rows = [RowRecord("严格结果", 4, strict_values(), image_embedded=True)]
        self.assertEqual(validate_workbook_model(model(rows)), [])

    def test_required_sheet_and_chinese_header_are_checked(self):
        missing_sheet_model = model()
        missing_sheet_model.sheets.remove("淘汰记录")
        codes = {issue.code for issue in validate_workbook_model(missing_sheet_model)}
        self.assertIn("SHEET_MISSING", codes)

        headers = {"严格结果": ["status", "product id", "total score"]}
        codes = {issue.code for issue in validate_workbook_model(model(headers=headers))}
        self.assertIn("CHINESE_HEADER_MISSING", codes)

    def test_empty_template_with_chinese_headers_passes(self):
        self.assertEqual(validate_workbook_model(model()), [])

    def test_missing_embedded_image_or_url_is_rejected(self):
        no_image = RowRecord("严格结果", 4, strict_values(), image_embedded=False)
        no_url = RowRecord(
            "严格结果",
            5,
            strict_values(商品ID="A2", 主图链接=""),
            image_embedded=True,
        )
        codes = {issue.code for issue in validate_workbook_model(model([no_image, no_url]))}
        self.assertIn("STRICT_IMAGE_MISSING", codes)
        self.assertIn("STRICT_IMAGE_URL_MISSING", codes)

    def test_duplicate_identity_and_bad_sort_are_reported(self):
        rows = [
            RowRecord("严格结果", 4, strict_values(销量得分=50, 价格得分=50, 评价得分=50, 总评分=50), True),
            RowRecord("严格结果", 5, strict_values(销量得分=60, 价格得分=60, 评价得分=60, 总评分=60), True),
        ]
        codes = {issue.code for issue in validate_workbook_model(model(rows))}
        self.assertIn("STRICT_ID_DUPLICATE", codes)
        self.assertIn("TOTAL_SCORE_NOT_DESCENDING", codes)

    def test_identity_priority_uses_record_id_before_lower_priority_fields(self):
        rows = [
            RowRecord(
                "严格结果",
                4,
                strict_values(**{"记录/配对ID": "PAIR-1", "商品ID": "SHARED", "总评分": 92}),
                True,
            ),
            RowRecord(
                "严格结果",
                5,
                strict_values(**{"记录/配对ID": "PAIR-2", "商品ID": "SHARED"}),
                True,
            ),
            RowRecord("严格结果", 6, {"状态": "", "商品ID": ""}, False),
        ]
        codes = {issue.code for issue in validate_workbook_model(model(rows))}
        self.assertNotIn("STRICT_ID_DUPLICATE", codes)
        self.assertNotIn("STRICT_IMAGE_MISSING", codes)

    def test_failed_gate_or_missing_score_cannot_be_strict(self):
        row = RowRecord(
            "严格结果",
            4,
            strict_values(外观门槛="不通过", 价格得分="", 总评分=""),
            True,
        )
        codes = {issue.code for issue in validate_workbook_model(model([row]))}
        self.assertIn("STRICT_GATE_NOT_PASSED", codes)
        self.assertIn("STRICT_SCORE_MISSING", codes)

    def test_total_must_use_shared_four_four_two_scoring_function(self):
        row = RowRecord("严格结果", 4, strict_values(总评分=91), True)
        codes = {issue.code for issue in validate_workbook_model(model([row]))}
        self.assertIn("SCORE_WEIGHTS_INVALID", codes)

    def test_amazon_mode_accepts_amazon_or_generic_candidate_image_column(self):
        amazon_values = strict_values(**{"Amazon ASIN": "B0TEST", "商品ID": ""})
        amazon = RowRecord(
            "严格结果",
            4,
            amazon_values,
            image_embedded=True,
            image_headers=frozenset({"Amazon主图"}),
            image_columns=frozenset({1}),
        )
        generic = RowRecord(
            "严格结果",
            5,
            {**amazon_values, "Amazon ASIN": "B0NEXT"},
            image_embedded=True,
            image_headers=frozenset({"商品图片"}),
            image_columns=frozenset({1}),
        )
        self.assertEqual(validate_workbook_model(model([amazon, generic], mode="Amazon")), [])

    def test_1688_mode_requires_1688_image_and_supplier_evidence(self):
        values = strict_values(
            **{
                "商品ID": "",
                "1688商品ID": "1688-1",
                "1688主图链接": "https://example.com/1688.jpg",
                "主图链接": "",
                "供应商主页": "https://example.com/supplier",
                "ODM/OEM/定制证据": "支持来图定制，见供应商主页",
            }
        )
        valid = RowRecord(
            "严格结果",
            4,
            values,
            True,
            frozenset({"1688商品图片"}),
            frozenset({2}),
        )
        invalid = RowRecord(
            "严格结果",
            5,
            {**values, "1688商品ID": "1688-2"},
            True,
            frozenset({"商品图片"}),
            frozenset({2}),
        )
        issues = validate_workbook_model(model([valid, invalid], mode="1688"))
        image_rows = {issue.row for issue in issues if issue.code == "STRICT_IMAGE_MISSING"}
        self.assertEqual(image_rows, {5})

    def test_1688_mode_reports_missing_supplier_profile_and_customization_evidence(self):
        row = RowRecord(
            "严格结果",
            4,
            strict_values(**{"1688商品ID": "1688-1", "商品ID": "", "1688主图链接": "https://example.com/x.jpg", "主图链接": ""}),
            True,
            frozenset({"1688商品图片"}),
            frozenset({2}),
        )
        codes = {issue.code for issue in validate_workbook_model(model([row], mode="1688"))}
        self.assertIn("SUPPLIER_PROFILE_MISSING", codes)
        self.assertIn("ODM_EVIDENCE_MISSING", codes)

    def test_joint_mode_requires_both_sides_images_and_main_image_urls(self):
        row = RowRecord(
            "严格结果",
            4,
            strict_values(
                **{
                    "记录/配对ID": "PAIR-1",
                    "Amazon主图链接": "https://example.com/amazon.jpg",
                    "1688主图链接": "",
                    "主图链接": "",
                    "供应商主页": "https://example.com/supplier",
                    "ODM/OEM/定制证据": "支持 OEM",
                }
            ),
            True,
            frozenset({"Amazon商品图片"}),
            frozenset({1}),
        )
        codes = {issue.code for issue in validate_workbook_model(model([row], mode="联合"))}
        self.assertIn("STRICT_IMAGE_MISSING", codes)
        self.assertIn("STRICT_IMAGE_URL_MISSING", codes)


class WorkbookExtractorTests(unittest.TestCase):
    def test_extracts_relationship_mapped_sheets_cells_formula_cache_and_row_anchored_images(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            workbook_path = Path(temporary_directory) / "fixture.xlsx"
            _write_ooxml_fixture(workbook_path)

            extracted = validate_workbook.extract_workbook_model(workbook_path)

        self.assertEqual(extracted.sheets, {"严格结果", "待核验", "1688候选"})
        self.assertEqual(extracted.headers["严格结果"][0:4], ["状态", "Amazon ASIN", "商品图片", "主图链接"])
        self.assertEqual(extracted.mode, "Amazon")
        strict_rows = [row for row in extracted.rows if row.sheet == "严格结果"]
        self.assertEqual([row.row for row in strict_rows], [4, 5])
        self.assertEqual(strict_rows[0].values["Amazon ASIN"], "B0FIXTURE1")
        self.assertEqual(strict_rows[0].values["销量得分"], 100)
        self.assertEqual(strict_rows[0].values["总评分"], 92)
        self.assertTrue(strict_rows[0].image_embedded)
        self.assertEqual(strict_rows[0].image_headers, frozenset({"商品图片"}))
        self.assertEqual(strict_rows[0].image_columns, frozenset({2}))
        self.assertFalse(strict_rows[1].image_embedded)
        self.assertEqual(strict_rows[1].image_headers, frozenset())
        pending_rows = [row for row in extracted.rows if row.sheet == "待核验"]
        self.assertEqual(pending_rows[0].values, {"状态": "待核验", "商品ID": "PENDING-1"})

    def test_cli_returns_zero_and_utf8_json_for_valid_empty_template(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            workbook_path = Path(temporary_directory) / "empty-valid.xlsx"
            _write_empty_valid_ooxml_fixture(workbook_path)
            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = validate_workbook.main([str(workbook_path)])

        self.assertEqual(exit_code, 0)
        self.assertEqual(json.loads(output.getvalue()), {"ok": True, "issues": []})

    def test_cli_returns_one_and_json_issues_for_invalid_workbook(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            workbook_path = Path(temporary_directory) / "invalid.xlsx"
            _write_ooxml_fixture(workbook_path)
            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = validate_workbook.main([str(workbook_path)])

        payload = json.loads(output.getvalue())
        self.assertEqual(exit_code, 1)
        self.assertFalse(payload["ok"])
        self.assertIn("SHEET_MISSING", {issue["code"] for issue in payload["issues"]})
        self.assertIn("缺少必需工作表", output.getvalue())


if __name__ == "__main__":
    unittest.main()
