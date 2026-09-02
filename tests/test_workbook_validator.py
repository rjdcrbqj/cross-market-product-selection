from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
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
  <xdr:absoluteAnchor>
    <xdr:pos x="0" y="0"/><xdr:ext cx="1" cy="1"/>
    <xdr:pic><xdr:blipFill><a:blip r:embed="rIdAbsolute"/></xdr:blipFill></xdr:pic><xdr:clientData/>
  </xdr:absoluteAnchor>
</xdr:wsDr>"""
    drawing_rels = """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rIdImage" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="../media/image1.png"/>
  <Relationship Id="rIdNotMedia" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="../embeddings/object.bin"/>
  <Relationship Id="rIdAbsolute" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="../media/image2.png"/>
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
        archive.writestr("xl/media/image2.png", b"absolute-anchor-image")
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
        header = "字段" if name == "任务说明" else "状态"
        sheet_parts[f"xl/worksheets/sheet{index}.xml"] = f"""<?xml version="1.0" encoding="UTF-8"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>
  <row r="1"><c r="A1" t="inlineStr"><is><t>{header}</t></is></c></row>
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


def _rewrite_zip(path, replacements=None, removed=()):
    replacements = replacements or {}
    with ZipFile(path) as archive:
        parts = {name: archive.read(name) for name in archive.namelist() if name not in removed}
    parts.update(
        {
            name: content.encode("utf-8") if isinstance(content, str) else content
            for name, content in replacements.items()
        }
    )
    replacement_path = path.with_suffix(".replacement.xlsx")
    with ZipFile(replacement_path, "w") as archive:
        for name, content in parts.items():
            archive.writestr(name, content)
    replacement_path.replace(path)


def _empty_fixture_sheet_part(sheet_name):
    sheet_index = sorted(REQUIRED_SHEETS).index(sheet_name) + 1
    return f"xl/worksheets/sheet{sheet_index}.xml"


def _cli_result(workbook_path):
    output = io.StringIO()
    with redirect_stdout(output):
        exit_code = validate_workbook.main([str(workbook_path)])
    return exit_code, json.loads(output.getvalue()), output.getvalue()


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

    def test_nonempty_data_rows_reject_missing_or_noncanonical_status(self):
        rows = [
            RowRecord("亚马逊候选", 4, {"状态": "严格", "Amazon ASIN": "B0OLDSTATUS"}),
            RowRecord("1688候选", 5, {"状态": "淘汰", "1688商品ID": "1688-OLD"}),
            RowRecord("货源匹配", 6, {"状态": "", "记录/配对ID": "PAIR-NO-STATUS"}),
            RowRecord("严格结果", 7, strict_values(状态="严格"), image_embedded=True),
            RowRecord("待核验", 8, {"状态": "待处理", "商品ID": "PENDING-INVALID"}),
            RowRecord("淘汰记录", 9, {"状态": "淘汰", "商品ID": "REJECTED-INVALID"}),
        ]

        status_issues = [
            (issue.code, issue.sheet, issue.row)
            for issue in validate_workbook_model(model(rows))
            if issue.code == "STATUS_INVALID"
        ]

        self.assertEqual(
            status_issues,
            [
                ("STATUS_INVALID", "亚马逊候选", 4),
                ("STATUS_INVALID", "1688候选", 5),
                ("STATUS_INVALID", "货源匹配", 6),
                ("STATUS_INVALID", "严格结果", 7),
                ("STATUS_INVALID", "待核验", 8),
                ("STATUS_INVALID", "淘汰记录", 9),
            ],
        )

    def test_audit_sheets_reject_canonical_status_for_wrong_destination(self):
        rows = [
            RowRecord("严格结果", 4, strict_values(状态="待核验"), image_embedded=True),
            RowRecord("待核验", 5, {"状态": "已淘汰", "商品ID": "PENDING-WRONG"}),
            RowRecord("淘汰记录", 6, {"状态": "严格合格", "商品ID": "REJECTED-WRONG"}),
        ]

        mismatch_issues = [
            (issue.code, issue.sheet, issue.row)
            for issue in validate_workbook_model(model(rows))
            if issue.code == "STATUS_SHEET_MISMATCH"
        ]

        self.assertEqual(
            mismatch_issues,
            [
                ("STATUS_SHEET_MISMATCH", "严格结果", 4),
                ("STATUS_SHEET_MISMATCH", "待核验", 5),
                ("STATUS_SHEET_MISMATCH", "淘汰记录", 6),
            ],
        )

    def test_candidate_and_match_sheets_accept_every_canonical_status(self):
        rows = [
            RowRecord(sheet, index + 4, {"状态": status, "商品ID": f"{sheet}-{index}"})
            for sheet in ("亚马逊候选", "1688候选", "货源匹配")
            for index, status in enumerate(("严格合格", "待核验", "已淘汰"))
        ]

        status_codes = {
            issue.code
            for issue in validate_workbook_model(model(rows))
            if issue.code.startswith("STATUS_")
        }

        self.assertEqual(status_codes, set())

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

    def test_1688_mode_accepts_1688_or_generic_image_but_rejects_amazon_image(self):
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
        generic = RowRecord(
            "严格结果",
            5,
            {**values, "1688商品ID": "1688-2"},
            True,
            frozenset({"商品图片"}),
            frozenset({2}),
        )
        invalid = RowRecord(
            "严格结果",
            6,
            {**values, "1688商品ID": "1688-3"},
            True,
            frozenset({"Amazon商品图片"}),
            frozenset({2}),
        )
        issues = validate_workbook_model(model([valid, generic, invalid], mode="1688"))
        image_rows = {issue.row for issue in issues if issue.code == "STRICT_IMAGE_MISSING"}
        self.assertEqual(image_rows, {6})

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

    def test_non_finite_score_inputs_are_rejected(self):
        for field_name, value in (
            ("销量得分", float("nan")),
            ("价格得分", float("inf")),
            ("评价得分", float("-inf")),
            ("总评分", float("nan")),
        ):
            with self.subTest(field_name=field_name):
                row = RowRecord("严格结果", 4, strict_values(**{field_name: value}), True)
                codes = {issue.code for issue in validate_workbook_model(model([row]))}
                self.assertIn("SCORE_WEIGHTS_INVALID", codes)

    def test_sorting_rejects_a_second_row_higher_by_exactly_point_zero_one(self):
        rows = [
            RowRecord(
                "严格结果",
                4,
                strict_values(商品ID="A1", 销量得分=50, 价格得分=50, 评价得分=50, 总评分=50),
                True,
            ),
            RowRecord(
                "严格结果",
                5,
                strict_values(商品ID="A2", 销量得分=50.025, 价格得分=50, 评价得分=50, 总评分=50.01),
                True,
            ),
        ]
        codes = {issue.code for issue in validate_workbook_model(model(rows))}
        self.assertIn("TOTAL_SCORE_NOT_DESCENDING", codes)

    def test_joint_mode_does_not_accept_generic_image_as_amazon_side(self):
        row = RowRecord(
            "严格结果",
            4,
            strict_values(
                **{
                    "记录/配对ID": "PAIR-1",
                    "Amazon主图链接": "https://example.com/amazon.jpg",
                    "1688主图链接": "https://example.com/1688.jpg",
                    "主图链接": "",
                    "供应商主页": "https://supplier.example.com/store",
                    "ODM/OEM/定制证据": "支持 OEM",
                }
            ),
            True,
            frozenset({"商品图片", "1688商品图片"}),
            frozenset({1, 2}),
        )
        codes = {issue.code for issue in validate_workbook_model(model([row], mode="联合"))}
        self.assertIn("STRICT_IMAGE_MISSING", codes)

    def test_single_platform_mode_rejects_other_platform_image_and_link(self):
        amazon_row = RowRecord(
            "严格结果",
            4,
            strict_values(**{"Amazon ASIN": "B0TEST", "商品ID": "", "主图链接": "", "1688主图链接": "https://example.com/1688.jpg"}),
            True,
            frozenset({"1688商品图片"}),
            frozenset({2}),
        )
        amazon_codes = {issue.code for issue in validate_workbook_model(model([amazon_row], mode="Amazon"))}
        self.assertIn("STRICT_IMAGE_MISSING", amazon_codes)
        self.assertIn("STRICT_IMAGE_URL_MISSING", amazon_codes)

        source_row = RowRecord(
            "严格结果",
            4,
            strict_values(
                **{
                    "1688商品ID": "1688-1",
                    "商品ID": "",
                    "主图链接": "",
                    "Amazon主图链接": "https://example.com/amazon.jpg",
                    "供应商主页": "https://supplier.example.com/store",
                    "ODM/OEM/定制证据": "支持定制",
                }
            ),
            True,
            frozenset({"Amazon商品图片"}),
            frozenset({2}),
        )
        source_codes = {issue.code for issue in validate_workbook_model(model([source_row], mode="1688"))}
        self.assertIn("STRICT_IMAGE_MISSING", source_codes)
        self.assertIn("STRICT_IMAGE_URL_MISSING", source_codes)

    def test_main_image_link_must_be_http_url_with_host(self):
        for bad_url in ("not-a-url", "https:///missing-host", "ftp://example.com/a.jpg"):
            with self.subTest(bad_url=bad_url):
                row = RowRecord("严格结果", 4, strict_values(主图链接=bad_url), True)
                codes = {issue.code for issue in validate_workbook_model(model([row]))}
                self.assertIn("STRICT_IMAGE_URL_MISSING", codes)

    def test_supplier_profile_must_be_http_url_with_host(self):
        for bad_url in ("supplier page", "https:///missing-host", "ftp://supplier.example.com/store"):
            with self.subTest(bad_url=bad_url):
                row = RowRecord(
                    "严格结果",
                    4,
                    strict_values(
                        **{
                            "1688商品ID": "1688-1",
                            "商品ID": "",
                            "1688主图链接": "https://example.com/1688.jpg",
                            "主图链接": "",
                            "供应商主页": bad_url,
                            "ODM/OEM/定制证据": "支持来图定制",
                        }
                    ),
                    True,
                    frozenset({"1688商品图片"}),
                    frozenset({2}),
                )
                codes = {issue.code for issue in validate_workbook_model(model([row], mode="1688"))}
                self.assertIn("SUPPLIER_PROFILE_MISSING", codes)

    def test_negative_or_placeholder_customization_evidence_is_rejected(self):
        rejected_values = (
            "",
            "无",
            "否",
            "不支持",
            "暂不支持 OEM",
            "商家明确不支持定制",
            "无法定制",
            "不能定制",
            "不可定制",
            "不提供 OEM",
            "没有证据支持 OEM",
            "无证据",
            "未有证据支持 ODM",
            "尚未确认支持 OEM",
            "待核验",
            "未知",
            "-",
            "N/A",
            "no OEM service",
            "not supported",
            "none",
            "unsupported ODM",
            "false",
            "unknown",
            "pending",
        )
        for evidence in rejected_values:
            with self.subTest(evidence=evidence):
                row = RowRecord(
                    "严格结果",
                    4,
                    strict_values(
                        **{
                            "1688商品ID": "1688-1",
                            "商品ID": "",
                            "1688主图链接": "https://example.com/1688.jpg",
                            "主图链接": "",
                            "供应商主页": "https://supplier.example.com/store",
                            "ODM/OEM/定制证据": evidence,
                        }
                    ),
                    True,
                    frozenset({"1688商品图片"}),
                    frozenset({2}),
                )
                codes = {issue.code for issue in validate_workbook_model(model([row], mode="1688"))}
                self.assertIn("ODM_EVIDENCE_MISSING", codes)

        for evidence in (
            "支持 ODM/OEM 定制",
            "可定制",
            "supports OEM customization",
            "https://evidence.example.com/customization",
        ):
            with self.subTest(positive_evidence=evidence):
                positive = RowRecord(
                    "严格结果",
                    4,
                    strict_values(
                        **{
                            "1688商品ID": "1688-1",
                            "商品ID": "",
                            "1688主图链接": "https://example.com/1688.jpg",
                            "主图链接": "",
                            "供应商主页": "https://supplier.example.com/store",
                            "ODM/OEM/定制证据": evidence,
                        }
                    ),
                    True,
                    frozenset({"1688商品图片"}),
                    frozenset({2}),
                )
                codes = {issue.code for issue in validate_workbook_model(model([positive], mode="1688"))}
                self.assertNotIn("ODM_EVIDENCE_MISSING", codes)

    def test_total_validation_calls_shared_scoring_function_with_inputs(self):
        row = RowRecord(
            "严格结果",
            4,
            strict_values(销量得分=11, 价格得分=22, 评价得分=33, 总评分=73.21),
            True,
        )
        with patch.object(validate_workbook, "total_score", return_value=73.21) as shared_total_score:
            issues = validate_workbook_model(model([row]))

        self.assertEqual(issues, [])
        shared_total_score.assert_called_once_with(11.0, 22.0, 33.0)


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

    def test_declared_sheets_require_valid_workbook_relationships_and_existing_parts(self):
        cases = ("missing relationships", "missing r:id", "unknown r:id", "wrong relationship type", "missing worksheet part")
        for case in cases:
            with self.subTest(case=case), tempfile.TemporaryDirectory() as temporary_directory:
                workbook_path = Path(temporary_directory) / "broken.xlsx"
                _write_empty_valid_ooxml_fixture(workbook_path)
                if case == "missing relationships":
                    _rewrite_zip(workbook_path, removed={"xl/_rels/workbook.xml.rels"})
                elif case in {"missing r:id", "unknown r:id"}:
                    with ZipFile(workbook_path) as archive:
                        workbook_xml = archive.read("xl/workbook.xml").decode("utf-8")
                    replacement = "" if case == "missing r:id" else ' r:id="unknownRelationship"'
                    workbook_xml = workbook_xml.replace(' r:id="rId1"', replacement, 1)
                    _rewrite_zip(workbook_path, {"xl/workbook.xml": workbook_xml})
                elif case == "wrong relationship type":
                    with ZipFile(workbook_path) as archive:
                        relationships_xml = archive.read("xl/_rels/workbook.xml.rels").decode("utf-8")
                    relationships_xml = relationships_xml.replace("/relationships/worksheet", "/relationships/chartsheet", 1)
                    _rewrite_zip(workbook_path, {"xl/_rels/workbook.xml.rels": relationships_xml})
                else:
                    _rewrite_zip(workbook_path, removed={"xl/worksheets/sheet1.xml"})

                with self.assertRaises((KeyError, ValueError)):
                    validate_workbook.extract_workbook_model(workbook_path)

    def test_nonempty_sheet_without_exact_status_header_is_read_error(self):
        invalid_sheets = {
            "status instruction title": """<?xml version="1.0" encoding="UTF-8"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>
  <row r="1"><c r="A1" t="inlineStr"><is><t>状态填写说明</t></is></c></row>
  <row r="2"><c r="A2" t="inlineStr"><is><t>严格合格</t></is></c></row>
</sheetData></worksheet>""",
            "all english header": """<?xml version="1.0" encoding="UTF-8"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>
  <row r="1"><c r="A1" t="inlineStr"><is><t>status</t></is></c><c r="B1" t="inlineStr"><is><t>product id</t></is></c></row>
</sheetData></worksheet>""",
        }
        for case, sheet_xml in invalid_sheets.items():
            with self.subTest(case=case), tempfile.TemporaryDirectory() as temporary_directory:
                workbook_path = Path(temporary_directory) / "bad-header.xlsx"
                _write_empty_valid_ooxml_fixture(workbook_path)
                _rewrite_zip(workbook_path, {_empty_fixture_sheet_part("严格结果"): sheet_xml})

                exit_code, payload, _ = _cli_result(workbook_path)

                self.assertEqual(exit_code, 1)
                self.assertEqual({issue["code"] for issue in payload["issues"]}, {"WORKBOOK_READ_ERROR"})

    def test_completely_empty_worksheet_is_allowed(self):
        empty_sheet = """<?xml version="1.0" encoding="UTF-8"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData/></worksheet>"""
        with tempfile.TemporaryDirectory() as temporary_directory:
            workbook_path = Path(temporary_directory) / "empty-sheet.xlsx"
            _write_empty_valid_ooxml_fixture(workbook_path)
            _rewrite_zip(workbook_path, {_empty_fixture_sheet_part("严格结果"): empty_sheet})

            exit_code, payload, _ = _cli_result(workbook_path)

        self.assertEqual(exit_code, 0)
        self.assertEqual(payload, {"ok": True, "issues": []})

    def test_nonempty_task_instructions_use_exact_field_header(self):
        task_sheet = """<?xml version="1.0" encoding="UTF-8"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>
  <row r="1"><c r="A1" t="inlineStr"><is><t>选品任务说明</t></is></c></row>
  <row r="2"><c r="A2" t="inlineStr"><is><t>说明：请填写已确认内容</t></is></c></row>
  <row r="3"><c r="A3" t="inlineStr"><is><t> 字 段 </t></is></c><c r="B3" t="inlineStr"><is><t>确认内容</t></is></c></row>
  <row r="4"><c r="A4" t="inlineStr"><is><t>任务模式</t></is></c><c r="B4" t="inlineStr"><is><t>Amazon</t></is></c></row>
</sheetData></worksheet>"""
        with tempfile.TemporaryDirectory() as temporary_directory:
            workbook_path = Path(temporary_directory) / "task-instructions.xlsx"
            _write_empty_valid_ooxml_fixture(workbook_path)
            _rewrite_zip(workbook_path, {_empty_fixture_sheet_part("任务说明"): task_sheet})

            extracted = validate_workbook.extract_workbook_model(workbook_path)
            exit_code, payload, _ = _cli_result(workbook_path)

        task_rows = [row for row in extracted.rows if row.sheet == "任务说明"]
        self.assertEqual(extracted.headers["任务说明"], ["字 段", "确认内容"])
        self.assertEqual(task_rows[0].values, {"字 段": "任务模式", "确认内容": "Amazon"})
        self.assertEqual(exit_code, 0)
        self.assertEqual(payload, {"ok": True, "issues": []})

    def test_task_instruction_title_cannot_masquerade_as_field_header(self):
        task_sheet = """<?xml version="1.0" encoding="UTF-8"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>
  <row r="1"><c r="A1" t="inlineStr"><is><t>字段填写说明</t></is></c></row>
  <row r="2"><c r="A2" t="inlineStr"><is><t>任务模式</t></is></c><c r="B2" t="inlineStr"><is><t>Amazon</t></is></c></row>
</sheetData></worksheet>"""
        with tempfile.TemporaryDirectory() as temporary_directory:
            workbook_path = Path(temporary_directory) / "fake-task-header.xlsx"
            _write_empty_valid_ooxml_fixture(workbook_path)
            _rewrite_zip(workbook_path, {_empty_fixture_sheet_part("任务说明"): task_sheet})

            exit_code, payload, _ = _cli_result(workbook_path)

        self.assertEqual(exit_code, 1)
        self.assertEqual({issue["code"] for issue in payload["issues"]}, {"WORKBOOK_READ_ERROR"})

    def test_cells_without_references_use_their_reasonable_sequence(self):
        sheet_without_cell_references = """<?xml version="1.0" encoding="UTF-8"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>
  <row r="1"><c t="inlineStr"><is><t>状态</t></is></c><c t="inlineStr"><is><t>商品ID</t></is></c></row>
  <row r="2"><c t="inlineStr"><is><t>待核验</t></is></c><c t="inlineStr"><is><t>NO-REF-1</t></is></c></row>
</sheetData></worksheet>"""
        with tempfile.TemporaryDirectory() as temporary_directory:
            workbook_path = Path(temporary_directory) / "no-cell-reference.xlsx"
            _write_empty_valid_ooxml_fixture(workbook_path)
            _rewrite_zip(workbook_path, {_empty_fixture_sheet_part("严格结果"): sheet_without_cell_references})

            extracted = validate_workbook.extract_workbook_model(workbook_path)

        strict_rows = [row for row in extracted.rows if row.sheet == "严格结果"]
        self.assertEqual(extracted.headers["严格结果"], ["状态", "商品ID"])
        self.assertEqual(strict_rows[0].values, {"状态": "待核验", "商品ID": "NO-REF-1"})

    def test_cli_structures_missing_relationships_missing_file_and_corrupt_zip_as_read_errors(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_path = Path(temporary_directory)
            missing_relationships = temporary_path / "missing-relationships.xlsx"
            _write_empty_valid_ooxml_fixture(missing_relationships)
            _rewrite_zip(missing_relationships, removed={"xl/_rels/workbook.xml.rels"})
            corrupt = temporary_path / "corrupt.xlsx"
            corrupt.write_bytes(b"not a ZIP archive")
            missing = temporary_path / "does-not-exist.xlsx"

            for workbook_path in (missing_relationships, corrupt, missing):
                with self.subTest(workbook_path=workbook_path.name):
                    exit_code, payload, _ = _cli_result(workbook_path)
                    self.assertEqual(exit_code, 1)
                    self.assertFalse(payload["ok"])
                    self.assertEqual({issue["code"] for issue in payload["issues"]}, {"WORKBOOK_READ_ERROR"})


if __name__ == "__main__":
    unittest.main()
