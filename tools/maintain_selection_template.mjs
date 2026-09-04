// Maintenance-only generator for the committed workbook asset.
// This file is not a runtime dependency of the installed Skill.
import fs from "node:fs/promises";
import path from "node:path";
import { deflateSync } from "node:zlib";
import { FileBlob, SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const [, , command, ...args] = process.argv;

export const AMAZON_HEADERS = [
  "状态", "模式", "目标产品ID", "排名", "Amazon商品图片", "Amazon对比图片", "站点", "Amazon ASIN", "Amazon变体/SKU", "品牌", "商品标题",
  "Amazon链接", "Amazon主图链接", "Amazon对比图链接", "产品本体门槛", "外观门槛", "功能门槛", "价格/MOQ门槛",
  "详情身份门槛", "证据一致性门槛", "门槛原因", "外观逐项核验", "功能逐项核验",
  "Amazon目标售价", "Amazon实际售价", "Amazon币种",
  "Amazon销量", "Amazon销量来源类型", "Amazon销量统计周期", "Amazon评价星级", "Amazon评价数量",
  "Amazon销量得分", "Amazon价格得分", "Amazon评价得分", "Amazon产品总评分", "核心通过证据", "来源类型",
  "来源链接", "检索路径", "获取时间", "置信度", "冲突说明", "决策日志引用",
];

export const SUPPLY_HEADERS = [
  "状态", "模式", "目标产品ID", "排名", "1688商品图片", "1688对比图片", "1688商品ID", "1688 SKU/规格", "供应商ID", "店铺名称", "商品标题",
  "1688链接", "供应商主页", "1688主图链接", "1688对比图链接", "产品本体门槛", "外观门槛", "功能门槛", "价格/MOQ门槛",
  "供应商门槛", "生产能力门槛", "ODM/OEM/定制门槛", "证据一致性门槛", "门槛原因", "目标成本",
  "外观逐项核验", "功能逐项核验", "实际单价", "成本币种", "采购数量档位", "MOQ", "阶梯价", "1688销量", "1688销量来源类型", "1688销量统计周期",
  "1688评价星级", "1688评价数量", "1688销量得分", "1688价格得分", "1688评价得分", "1688产品总评分",
  "生产能力证据", "ODM/OEM/定制证据", "核心通过证据", "来源类型", "来源链接", "检索路径", "获取时间",
  "置信度", "冲突说明", "决策日志引用",
];

export const MATCH_HEADERS = [
  "状态", "模式", "目标产品ID", "排名", "记录/配对ID", "Amazon商品图片", "Amazon对比图片", "1688商品图片", "1688对比图片", "站点", "Amazon ASIN",
  "Amazon变体/SKU", "1688商品ID", "1688 SKU/规格", "供应商ID", "Amazon商品标题", "1688商品标题",
  "Amazon链接", "1688链接", "Amazon主图链接", "Amazon对比图链接", "1688主图链接", "1688对比图链接", "供应商主页", "产品本体门槛", "外观门槛",
  "功能门槛", "价格/MOQ门槛", "目标成本", "实际单价", "成本币种", "采购数量档位", "MOQ", "阶梯价", "详情身份门槛", "供应商门槛", "生产能力门槛", "ODM/OEM/定制门槛",
  "证据一致性门槛", "外观逐项核验", "功能逐项核验", "市场机会得分", "市场机会结论", "市场机会证据",
  "供应能力得分", "供应能力结论", "供应能力证据", "匹配质量得分", "匹配质量结论", "匹配质量证据",
  "最终配对得分", "生产能力证据", "ODM/OEM/定制证据", "主要限制", "来源类型", "来源链接", "检索路径",
  "获取时间", "置信度", "冲突说明", "决策日志引用",
];

export const STRICT_HEADERS = [
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
];

const AMAZON_SCORE_HEADERS = ["Amazon销量得分", "Amazon价格得分", "Amazon评价得分", "Amazon产品总评分"];
const SUPPLY_SCORE_HEADERS = ["1688销量得分", "1688价格得分", "1688评价得分", "1688产品总评分"];
const PLATFORM_SCORE_HEADERS = new Set([...AMAZON_SCORE_HEADERS, ...SUPPLY_SCORE_HEADERS]);

export const TARGET_HEADERS = [
  "目标产品ID", "目标产品名称", "用户确认状态", "视觉对标模式", "参考图1链接", "参考图2链接", "必需视图",
  "外观必须特点", "允许变化", "外观排除项", "必须功能", "可选功能", "排除功能", "Amazon目标售价",
  "Amazon价格允许偏差", "Amazon同类均价", "Amazon同类均价最低样本数", "Amazon目标站点", "1688目标成本", "1688价格允许偏差",
  "采购数量档位", "目标严格合格数量", "Amazon目标币种", "1688成本币种",
];

export const PRICE_HEADERS = [
  "目标产品ID", "平台", "样本商品ID", "跨站产品组ID", "站点", "样本状态", "产品本体门槛", "外观门槛",
  "功能门槛", "标准价格", "标准币种", "来源链接", "获取时间", "排除原因",
];

const PENDING_HEADERS = [
  "状态", "模式", "目标产品ID", "记录/配对ID", "平台", "商品图片", "Amazon ASIN", "1688商品ID", "标题/配对说明",
  "缺失或冲突门槛", "现有证据", "补证据动作", "Amazon链接", "1688链接", "主图链接", "证据链接",
  "用户保留决定", "决策日志引用", "更新时间",
];

const REJECTED_HEADERS = [
  "状态", "模式", "目标产品ID", "记录/配对ID", "平台", "商品图片", "Amazon ASIN", "1688商品ID", "标题/配对说明",
  "失败门槛", "失败事实", "证据链接", "Amazon链接", "1688链接", "决策日志引用", "淘汰时间",
];

const TASK_ROWS = [
  ["模式", "", "Amazon / 1688 / 联合；九表仅表示能力，不能据表头推断模式"],
  ["业务目标", "", "说明本批多产品选品要支持的业务决策"],
  ["市场/范围", "", "填写站点、国家、区域或供应范围"],
  ["目标产品数量", "", "与目标产品表中已确认的唯一目标产品 ID 数一致"],
  ["全局检索边界", "", "填写允许站点、语言、时间与付费数据边界"],
  ["销量统计周期", "", "填写月、近30天或其他明确周期"],
  ["评价口径", "", "填写星级来源、评价数量范围及变体合并规则"],
  ["跨站点去重口径", "", "每个目标产品内以 ASIN、稳定商品ID或规范链接去重；不同目标互不串行"],
  ["关键字段", "", "列明本任务额外必填与可选字段"],
  ["缺失值策略", "缺失保持空白；硬门槛证据不足转待核验", "未知值不得写成 0、否或推断值"],
  ["销量权重", 0.4, "平台产品总评分固定权重 40%，不可改写"],
  ["价格权重", 0.4, "平台产品总评分固定权重 40%，不可改写"],
  ["评价权重", 0.2, "平台产品总评分固定权重 20%，不可改写"],
  ["权重合计", null, "固定权重合计必须等于 100%"],
  ["评价满分星级", 5, "评价得分仅接受 0 到该满分；越界不得截断"],
  ["评分下限", 0, "标准化分数不得低于该值"],
  ["评分满分", 100, "销量、价格、评价三个分项的统一满分"],
  ["价格评分规则", "每个目标产品独立取目标售价/成本，按绝对偏差率双向接近", "Amazon 严格下限还不得低于该产品合格同类均价；1688 使用对称成本带"],
  ["证据不足处理", "三项评分任一原始证据缺失即转待核验", "不得把缺失值写成 0，也不得进入严格排名"],
  ["结果数量规则", "每个目标产品独立输出自己的 Top-N", "严格结果不足时如实少于目标数，不得用待核验或淘汰项凑数"],
  ["执行顺序", "先核验产品、外观、功能和证据一致性门槛，再评分排名", "硬门槛失败即淘汰；证据不足即待核验"],
  ["最终配对评分公式", "", "仅联合模式可选；需用户明确确认后才能填写最终配对得分"],
  ["市场机会权重", "", "与供应能力、匹配质量权重同时确认，未确认保持空白"],
  ["供应能力权重", "", "与市场机会、匹配质量权重同时确认，未确认保持空白"],
  ["匹配质量权重", "", "与市场机会、供应能力权重同时确认，未确认保持空白"],
];

const TASK_ROW_BY_FIELD = Object.fromEntries(TASK_ROWS.map((row, index) => [row[0], index + 4]));
const taskRef = (field) => `'任务说明'!$B$${TASK_ROW_BY_FIELD[field]}`;

function columnName(index) {
  let value = index + 1;
  let result = "";
  while (value > 0) {
    value -= 1;
    result = String.fromCharCode(65 + (value % 26)) + result;
    value = Math.floor(value / 26);
  }
  return result;
}

function cell(headers, header, row = 4) {
  const index = headers.indexOf(header);
  if (index < 0) throw new Error(`缺少公式字段：${header}`);
  return `${columnName(index)}${row}`;
}

function attachExternalHyperlink(sheet, rowIndex, columnIndex, value) {
  if (typeof value !== "string" || !/^https?:\/\/[^/\s]+/i.test(value)) return;
  const modelCell = sheet.__getOrCreateCell(rowIndex, columnIndex);
  modelCell.hyperlink = { uri: value, isExternal: true, action: "" };
  sheet.writeCellInputToYjs(modelCell);
}

function columnRange(headers, header) {
  const column = columnName(headers.indexOf(header));
  return `$${column}$4:$${column}$103`;
}

function columnWidth(header) {
  if (header.includes("图片")) return 20;
  if (["说明", "证据", "原因", "限制", "冲突", "结论"].some((term) => header.includes(term))) return 30;
  if (["链接", "主页", "检索路径"].some((term) => header.includes(term))) return 28;
  if (header.includes("时间") || header.includes("周期")) return 20;
  if (header.includes("ID") || header.includes("ASIN") || header.includes("SKU")) return 18;
  if (["状态", "模式", "排名", "币种", "置信度"].includes(header)) return 12;
  return 16;
}

function styleSheet(sheet, headers, title, description, tableName) {
  const lastColumn = columnName(headers.length - 1);
  sheet.showGridLines = false;
  sheet.getRange(`A1:${lastColumn}1`).merge();
  sheet.getRange("A1").values = [[title]];
  sheet.getRange(`A2:${lastColumn}2`).merge();
  sheet.getRange("A2").values = [[description]];
  const table = sheet.tables.add(`A3:${lastColumn}4`, true, tableName);
  table.style = "TableStyleMedium2";
  table.showHeaders = true;
  table.showFilterButton = true;
  sheet.getRange(`A1:${lastColumn}4`).format.font = { name: "Microsoft YaHei", fontSize: 10 };
  sheet.getRange(`A1:${lastColumn}1`).format = {
    fill: "#17324D",
    font: { name: "Microsoft YaHei", bold: true, color: "#FFFFFF", fontSize: 16 },
    verticalAlignment: "center",
  };
  sheet.getRange(`A2:${lastColumn}2`).format = {
    fill: "#DDF3F0",
    font: { name: "Microsoft YaHei", italic: true, color: "#17324D", fontSize: 10 },
    wrapText: true,
    verticalAlignment: "center",
  };
  sheet.getRange(`A3:${lastColumn}3`).format = {
    fill: "#0F766E",
    font: { name: "Microsoft YaHei", bold: true, color: "#FFFFFF", fontSize: 9 },
    wrapText: true,
    horizontalAlignment: "center",
    verticalAlignment: "center",
    borders: { preset: "all", style: "thin", color: "#D9E2E3" },
  };
  sheet.getRange(`A4:${lastColumn}4`).format = {
    fill: "#FFFFFF",
    font: { name: "Microsoft YaHei", color: "#243746", fontSize: 10 },
    wrapText: true,
    verticalAlignment: "center",
    borders: { preset: "all", style: "thin", color: "#D9E2E3" },
  };
  sheet.getRange(`A1:${lastColumn}1`).format.rowHeight = 30;
  sheet.getRange(`A2:${lastColumn}2`).format.rowHeight = 36;
  sheet.getRange(`A3:${lastColumn}3`).format.rowHeight = 48;
  sheet.getRange(`A4:${lastColumn}4`).format.rowHeight = 100;
  headers.forEach((header, index) => {
    const column = columnName(index);
    sheet.getRange(`${column}1:${column}4`).format.columnWidth = columnWidth(header);
  });
  return { lastColumn, table };
}

function addStatusRules(sheet, allowedStatuses) {
  const statusRange = sheet.getRange("A4:A103");
  statusRange.dataValidation = { rule: { type: "list", values: allowedStatuses } };
  statusRange.conditionalFormats.add("containsText", { text: "严格合格", format: { fill: "#DCFCE7", font: { bold: true, color: "#166534" } } });
  statusRange.conditionalFormats.add("containsText", { text: "待核验", format: { fill: "#FEF3C7", font: { bold: true, color: "#92400E" } } });
  statusRange.conditionalFormats.add("containsText", { text: "已淘汰", format: { fill: "#FEE2E2", font: { bold: true, color: "#991B1B" } } });
}

function setSemanticFormats(sheet, headers) {
  headers.forEach((header, index) => {
    const range = sheet.getRange(`${columnName(index)}4:${columnName(index)}103`);
    if (header.includes("得分") || header.includes("评分") || header.includes("星级")) range.format.numberFormat = "0.00";
    else if (header.includes("销量") || header.includes("数量") || header === "MOQ" || header === "排名") range.format.numberFormat = "#,##0";
    else if (["售价", "价格", "单价", "成本"].some((term) => header.includes(term))) range.format.numberFormat = "#,##0.00";
    if (header.includes("允许偏差")) range.format.numberFormat = "0.0%";
    else if (header.includes("时间")) range.format.numberFormat = "yyyy-mm-dd hh:mm";
    if (header.includes("ID") || header.includes("ASIN") || header.includes("SKU")) range.format.numberFormat = "@";
  });
}

function platformFormulas(headers, side, row = 4) {
  const names = side === "amazon"
    ? {
        target: "Amazon目标售价", actual: "Amazon实际售价", sales: "Amazon销量", source: "Amazon销量来源类型",
        period: "Amazon销量统计周期", rating: "Amazon评价星级", salesScore: "Amazon销量得分",
        priceScore: "Amazon价格得分", ratingScore: "Amazon评价得分", total: "Amazon产品总评分",
      }
    : {
        target: "目标成本", actual: "实际单价", sales: "1688销量", source: "1688销量来源类型",
        period: "1688销量统计周期", rating: "1688评价星级", salesScore: "1688销量得分",
        priceScore: "1688价格得分", ratingScore: "1688评价得分", total: "1688产品总评分",
      };
  const status = `$A${row}`;
  const targetId = cell(headers, "目标产品ID", row);
  const mode = cell(headers, "模式", row);
  const sales = cell(headers, names.sales, row);
  const source = cell(headers, names.source, row);
  const period = cell(headers, names.period, row);
  const target = cell(headers, names.target, row);
  const actual = cell(headers, names.actual, row);
  const rating = cell(headers, names.rating, row);
  const salesRange = columnRange(headers, names.sales);
  const criteria = [
    ["状态", '"严格合格"'],
    ["目标产品ID", targetId],
    ["模式", mode],
    ...(side === "amazon" ? [["站点", cell(headers, "站点", row)]] : []),
    [names.source, source],
    [names.period, period],
  ];
  const criteriaArguments = criteria.flatMap(([header, criterion]) => [columnRange(headers, header), criterion]).join(",");
  const count = `COUNTIFS(${criteriaArguments})`;
  const minimum = `MINIFS(${salesRange},${criteriaArguments})`;
  const maximum = `MAXIFS(${salesRange},${criteriaArguments})`;
  const requiredGroupCells = [targetId, mode, ...(side === "amazon" ? [cell(headers, "站点", row)] : []), source, period, sales];
  const salesFormula = `=IF(OR(${status}<>"严格合格",${requiredGroupCells.map((value) => `${value}=""`).join(",")}),"",ROUND(IF(${count}<=1,100,IF(${maximum}=${minimum},100,(${sales}-${minimum})/(${maximum}-${minimum})*100)),2))`;
  const priceFormula = `=IF(OR(${status}<>"严格合格",${targetId}="",${target}="",${actual}="",${target}<=0,${actual}<0),"",ROUND(MAX(0,100*(1-ABS(${actual}-${target})/${target})),2))`;
  const ratingFormula = `=IF(OR(${status}<>"严格合格",${rating}="",${taskRef("评价满分星级")}="",${rating}<0,${rating}>${taskRef("评价满分星级")}),"",ROUND(100*${rating}/${taskRef("评价满分星级")},2))`;
  const salesScore = cell(headers, names.salesScore, row);
  const priceScore = cell(headers, names.priceScore, row);
  const ratingScoreCell = cell(headers, names.ratingScore, row);
  const totalFormula = `=IF(OR(${status}<>"严格合格",${salesScore}="",${priceScore}="",${ratingScoreCell}=""),"",ROUND(${salesScore}*0.4+${priceScore}*0.4+${ratingScoreCell}*0.2,2))`;
  return {
    [names.salesScore]: salesFormula,
    [names.priceScore]: priceFormula,
    [names.ratingScore]: ratingFormula,
    [names.total]: totalFormula,
  };
}

function buildTaskSheet(workbook) {
  const sheet = workbook.worksheets.add("任务说明");
  const headers = ["字段", "确认值", "填写说明"];
  sheet.getRange("A3:C3").values = [headers];
  sheet.getRange(`A4:C${TASK_ROWS.length + 3}`).values = TASK_ROWS;
  sheet.getRange(`B${TASK_ROW_BY_FIELD["权重合计"]}`).formulas = [[`=SUM(B${TASK_ROW_BY_FIELD["销量权重"]}:B${TASK_ROW_BY_FIELD["评价权重"]})`]];
  const { table } = styleSheet(
    sheet,
    headers,
    "通用跨市场选品任务说明",
    "先确认任务模式、范围与硬门槛，再检索、核验实际主图、评分和排名；缺证据转待核验。",
    "TaskInstructionsSeed",
  );
  table.delete();
  const finalTable = sheet.tables.add(`A3:C${TASK_ROWS.length + 3}`, true, "TaskInstructionsTable");
  finalTable.style = "TableStyleMedium2";
  finalTable.showHeaders = true;
  finalTable.showFilterButton = true;
  sheet.getRange(`A4:C${TASK_ROWS.length + 3}`).format.font = { name: "Microsoft YaHei", fontSize: 10, color: "#243746" };
  sheet.getRange(`A4:C${TASK_ROWS.length + 3}`).format.wrapText = true;
  sheet.getRange(`A4:C${TASK_ROWS.length + 3}`).format.borders = { preset: "all", style: "thin", color: "#D9E2E3" };
  sheet.getRange(`A4:A${TASK_ROWS.length + 3}`).format.columnWidth = 22;
  sheet.getRange(`B4:B${TASK_ROWS.length + 3}`).format.columnWidth = 42;
  sheet.getRange(`C4:C${TASK_ROWS.length + 3}`).format.columnWidth = 52;
  sheet.getRange(`A4:C${TASK_ROWS.length + 3}`).format.rowHeight = 32;
  sheet.getRange(`B4:B${TASK_ROW_BY_FIELD["缺失值策略"]}`).format.fill = "#FFF4CE";
  sheet.getRange(`B${TASK_ROW_BY_FIELD["销量权重"]}:B${TASK_ROW_BY_FIELD["权重合计"]}`).format.fill = "#E8F0FE";
  sheet.getRange(`B${TASK_ROW_BY_FIELD["模式"]}`).dataValidation = { rule: { type: "list", values: ["Amazon", "1688", "联合"] } };
  sheet.getRange(`B${TASK_ROW_BY_FIELD["销量权重"]}:B${TASK_ROW_BY_FIELD["权重合计"]}`).format.numberFormat = "0%";
}

function buildTargetSheet(workbook) {
  const sheet = workbook.worksheets.add("目标产品");
  const lastColumn = columnName(TARGET_HEADERS.length - 1);
  sheet.getRange(`A3:${lastColumn}3`).values = [TARGET_HEADERS];
  sheet.getRange(`A4:${lastColumn}4`).values = [TARGET_HEADERS.map(() => null)];
  styleSheet(
    sheet,
    TARGET_HEADERS,
    "目标产品合同",
    "每个目标产品独立冻结参考图、必需视图、外观/功能门槛、Amazon目标站点、目标价格与 Top-N；一行一产品。",
    "TargetProductsTable",
  );
  setSemanticFormats(sheet, TARGET_HEADERS);
  sheet.getRange("C4:C103").dataValidation = { rule: { type: "list", values: ["待用户确认", "已确认", "需补充"] } };
  sheet.getRange("D4:D103").dataValidation = { rule: { type: "list", values: ["普通单图", "严格多视图"] } };
  return sheet;
}

function buildPriceSheet(workbook) {
  const sheet = workbook.worksheets.add("价格基准");
  const lastColumn = columnName(PRICE_HEADERS.length - 1);
  sheet.getRange(`A3:${lastColumn}3`).values = [PRICE_HEADERS];
  sheet.getRange(`A4:${lastColumn}4`).values = [PRICE_HEADERS.map(() => null)];
  styleSheet(
    sheet,
    PRICE_HEADERS,
    "Amazon 同类价格基准",
    "只有目标站点内且产品本体、外观和功能都通过的可追溯样本才能纳入；同一商品和跨站产品组在每个目标内各只计一次。",
    "PriceBenchmarksTable",
  );
  setSemanticFormats(sheet, PRICE_HEADERS);
  sheet.getRange("B4:B103").dataValidation = { rule: { type: "list", values: ["Amazon", "1688"] } };
  sheet.getRange("F4:F103").dataValidation = { rule: { type: "list", values: ["纳入", "排除", "待核验"] } };
  return sheet;
}

function buildDataSheet(workbook, config) {
  const sheet = workbook.worksheets.add(config.name);
  const lastColumn = columnName(config.headers.length - 1);
  sheet.getRange(`A3:${lastColumn}3`).values = [config.headers];
  sheet.getRange(`A4:${lastColumn}4`).values = [config.headers.map(() => null)];
  for (const [header, formula] of Object.entries(config.formulas ?? {})) {
    sheet.getRange(`${cell(config.headers, header)}`).formulas = [[formula]];
  }
  styleSheet(sheet, config.headers, config.title, config.description, config.tableName);
  addStatusRules(sheet, config.allowedStatuses);
  setSemanticFormats(sheet, config.headers);
  return sheet;
}

export async function buildTemplate(outputPath) {
  const workbook = Workbook.create();
  buildTaskSheet(workbook);
  buildTargetSheet(workbook);
  buildPriceSheet(workbook);
  buildDataSheet(workbook, {
    name: "亚马逊候选", title: "亚马逊候选",
    description: "按目标产品 ID 分组记录仍可比较的商品；严格多视图要求主图与对比/结构图同时嵌入并保留原链接。",
    allowedStatuses: ["严格合格", "待核验"],
    headers: AMAZON_HEADERS, tableName: "AmazonCandidatesTable", formulas: platformFormulas(AMAZON_HEADERS, "amazon"),
  });
  buildDataSheet(workbook, {
    name: "1688候选", title: "1688候选",
    description: "按目标产品 ID 核验商品与工厂；已知单价越过目标成本带即淘汰，严格行必须绑定 SKU、采购档位、MOQ和阶梯价。",
    allowedStatuses: ["严格合格", "待核验"],
    headers: SUPPLY_HEADERS, tableName: "SupplyCandidatesTable", formulas: platformFormulas(SUPPLY_HEADERS, "1688"),
  });
  buildDataSheet(workbook, {
    name: "货源匹配", title: "Amazon × 1688 货源匹配",
    description: "市场机会、供应能力与匹配质量分别记录结论和证据；未确认最终配对公式及三类权重时不填最终分和排名。",
    allowedStatuses: ["严格合格", "待核验"],
    headers: MATCH_HEADERS, tableName: "SourceMatchesTable",
  });
  buildDataSheet(workbook, {
    name: "严格结果", title: "严格结果",
    description: "仅收录全部硬门槛与原始评分证据已确认的记录；去重、评分、排名和 Top-N 都必须在同一目标产品 ID 内完成。",
    allowedStatuses: ["严格合格"],
    headers: STRICT_HEADERS, tableName: "StrictResultsTable",
    formulas: { ...platformFormulas(STRICT_HEADERS, "amazon"), ...platformFormulas(STRICT_HEADERS, "1688") },
  });
  buildDataSheet(workbook, {
    name: "待核验", title: "待核验",
    description: "没有明确失败但缺少可靠硬门槛或评分原始证据的记录放在这里；写清缺口、现有证据与补证据动作。",
    allowedStatuses: ["待核验"],
    headers: PENDING_HEADERS, tableName: "PendingAuditTable",
  });
  buildDataSheet(workbook, {
    name: "淘汰记录", title: "淘汰记录",
    description: "只记录已有可靠证据确认失败的记录；必须保留稳定身份、具体失败门槛、失败事实与证据链接。",
    allowedStatuses: ["已淘汰"],
    headers: REJECTED_HEADERS, tableName: "RejectedAuditTable",
  });
  for (const sheet of workbook.worksheets.items) sheet.freezePanes.freezeRows(3);
  await fs.mkdir(path.dirname(outputPath), { recursive: true });
  const output = await SpreadsheetFile.exportXlsx(workbook);
  await output.save(outputPath);
  console.log(JSON.stringify({ outputPath, sheets: workbook.worksheets.items.map((sheet) => sheet.name) }));
}

const SYNTHETIC_TARGETS = [
  { id: "P-A", name: "目标产品 A", amazonTarget: 150, amazonAverage: 150, supplyTarget: 100, color: [20, 130, 180] },
  { id: "P-B", name: "目标产品 B", amazonTarget: 300, amazonAverage: 300, supplyTarget: 200, color: [180, 90, 60] },
];

function crc32(data) {
  let crc = 0xffffffff;
  for (const byte of data) {
    crc ^= byte;
    for (let bit = 0; bit < 8; bit += 1) crc = (crc >>> 1) ^ ((crc & 1) ? 0xedb88320 : 0);
  }
  return (crc ^ 0xffffffff) >>> 0;
}

function pngChunk(type, data) {
  const typeBytes = Buffer.from(type, "ascii");
  const length = Buffer.alloc(4);
  length.writeUInt32BE(data.length);
  const checksum = Buffer.alloc(4);
  checksum.writeUInt32BE(crc32(Buffer.concat([typeBytes, data])));
  return Buffer.concat([length, typeBytes, data, checksum]);
}

function solidPngDataUrl([red, green, blue], width = 300, height = 300) {
  const header = Buffer.alloc(13);
  header.writeUInt32BE(width, 0);
  header.writeUInt32BE(height, 4);
  header[8] = 8;
  header[9] = 2;
  const row = Buffer.alloc(1 + width * 3);
  for (let column = 0; column < width; column += 1) {
    row[1 + column * 3] = red;
    row[2 + column * 3] = green;
    row[3 + column * 3] = blue;
  }
  const raw = Buffer.concat(Array.from({ length: height }, () => row));
  const png = Buffer.concat([
    Buffer.from("89504e470d0a1a0a", "hex"),
    pngChunk("IHDR", header),
    pngChunk("IDAT", deflateSync(raw)),
    pngChunk("IEND", Buffer.alloc(0)),
  ]);
  return `data:image/png;base64,${png.toString("base64")}`;
}

function targetScenarioValues(mode, target) {
  return {
    "目标产品ID": target.id,
    "目标产品名称": target.name,
    "用户确认状态": "已确认",
    "视觉对标模式": "严格多视图",
    "参考图1链接": `https://brand.example.com/${target.id}/reference-main.png`,
    "参考图2链接": `https://brand.example.com/${target.id}/reference-structure.png`,
    "必需视图": "视图1=整体主视图；视图2=关键结构或状态图",
    "外观必须特点": "外观1=主体轮廓、比例与参考图一致；外观2=关键连接或变化结构与参考图一致",
    "允许变化": "颜色、表面装饰和包装可变化",
    "外观排除项": "排除1=主体结构路线明显不同",
    "必须功能": "功能1=完成目标产品的核心用途",
    "可选功能": "无",
    "排除功能": "无",
    "Amazon目标售价": mode === "1688" ? "" : target.amazonTarget,
    "Amazon价格允许偏差": mode === "1688" ? "" : 0.2,
    "Amazon同类均价": mode === "1688" ? "" : target.amazonAverage,
    "Amazon同类均价最低样本数": mode === "1688" ? "" : 5,
    "Amazon目标站点": mode === "1688" ? "" : "DE",
    "1688目标成本": mode === "Amazon" ? "" : target.supplyTarget,
    "1688价格允许偏差": mode === "Amazon" ? "" : 0.2,
    "采购数量档位": mode === "Amazon" ? "" : "1000件",
    "目标严格合格数量": 10,
    "Amazon目标币种": mode === "1688" ? "" : "CNY",
    "1688成本币种": mode === "Amazon" ? "" : "CNY",
  };
}

function strictScenarioValues(mode, scenario, target, targetIndex) {
  const gates = {
    "产品本体门槛": "通过", "外观门槛": "通过", "功能门槛": "通过", "价格/MOQ门槛": "通过",
    "详情身份门槛": "通过", "供应商门槛": "通过", "生产能力门槛": "通过",
    "ODM/OEM/定制门槛": "通过", "证据一致性门槛": "通过",
  };
  const asin = `B0SYNTH00${targetIndex + 1}`;
  const amazon = {
    "站点": "DE", "Amazon ASIN": asin, "Amazon变体/SKU": `${target.id}-STANDARD`,
    "Amazon链接": `https://www.amazon.de/dp/${asin}`, "Amazon主图链接": `https://images.example.com/${target.id}/amazon-main.png`,
    "Amazon对比图链接": `https://images.example.com/${target.id}/amazon-structure.png`,
    "Amazon目标售价": target.amazonTarget, "Amazon实际售价": target.amazonTarget, "Amazon币种": "CNY", "Amazon销量": 100 + targetIndex * 100,
    "Amazon销量来源类型": "合成月销量", "Amazon销量统计周期": "近30天", "Amazon评价星级": 4.5,
    "Amazon评价数量": 200,
  };
  const supply = {
    "1688商品ID": `16880000000${targetIndex + 1}`, "1688 SKU/规格": `${target.id}-STANDARD`, "供应商ID": `SUPPLIER-${target.id}`,
    "1688链接": `https://detail.1688.com/offer/16880000000${targetIndex + 1}.html`, "供应商主页": `https://supplier.example.com/company/SUPPLIER-${target.id}`,
    "1688主图链接": `https://images.example.com/${target.id}/1688-main.png`, "1688对比图链接": `https://images.example.com/${target.id}/1688-structure.png`,
    "目标成本": target.supplyTarget, "实际单价": target.supplyTarget, "成本币种": "CNY", "采购数量档位": "1000件", "MOQ": 500,
    "阶梯价": `500件=${target.supplyTarget + 10} CNY/件；1000件=${target.supplyTarget} CNY/件`,
    "1688销量": 50 + targetIndex * 50, "1688销量来源类型": "合成近30天销量", "1688销量统计周期": "近30天",
    "1688评价星级": 4, "1688评价数量": 20,
    "生产能力证据": `供应商主体 SUPPLIER-${target.id} 页面列出注塑与组装生产线`,
    "ODM/OEM/定制证据": "同一供应商主体支持 OEM、打样和来图定制",
  };
  const mainEvidence = mode === "联合" ? "Amazon主图与1688主图" : "商品主图";
  const structureEvidence = mode === "联合" ? "Amazon结构图与1688结构图" : "商品结构图";
  const values = {
    "状态": "严格合格", "模式": mode, "目标产品ID": target.id, "排名": mode === "联合" ? "" : 1, "记录/配对ID": `SYNTH-${mode}-${target.id}`,
    "标题/配对说明": `合成集成测试记录 ${target.id}`, ...gates,
    "外观逐项核验": `外观1=通过（候选可见事实=${target.id}的${mainEvidence}显示主体轮廓，对标参考=参考图1显示相同轮廓，关键差异=仅颜色不同）；外观2=通过（候选可见事实=${target.id}的${structureEvidence}显示关键连接，对标参考=参考图2显示相同连接，关键差异=无关键差异）；排除1=通过（候选可见事实=${target.id}的${mainEvidence}与${structureEvidence}未出现排除结构，对标参考=排除项已冻结，关键差异=无）`,
    "功能逐项核验": mode === "联合"
      ? "功能1=通过（Amazon详情页与1688详情页规格均明确列出）"
      : "功能1=通过（商品详情页规格）",
    "核心通过证据": `合成详情、图片、身份与门槛证据 ${target.id}`, "来源类型": "合成离线测试",
    "来源链接": `https://evidence.example.com/synthetic/${target.id}`, "检索路径": "本地合成集成夹具",
    "获取时间": "2026-09-02T10:00:00+08:00", "置信度": "高", "决策日志引用": "SYNTH-001",
    "输出时间": "2026-09-04T10:05:00+08:00",
    ...(mode !== "1688" ? amazon : {}),
    ...(mode !== "Amazon" ? supply : {}),
  };
  if (mode === "联合") {
    Object.assign(values, {
      "市场机会得分": 90, "市场机会结论": "通过", "市场机会证据": "合成 Amazon 市场证据",
      "供应能力得分": 88, "供应能力结论": "通过", "供应能力证据": "合成供应商生产与履约证据",
      "匹配质量得分": 92, "匹配质量结论": "通过", "匹配质量证据": "合成规格与功能匹配证据",
      "最终配对得分": "",
    });
  }
  if (targetIndex === 0 && scenario === "odm-color") values["ODM/OEM/定制证据"] = "支持颜色选择";
  if (targetIndex === 0 && scenario === "production-store") values["生产能力证据"] = "店名：某某制造厂";
  if (targetIndex === 0 && scenario === "production-link") values["生产能力证据"] = values["1688链接"];
  if (targetIndex === 0 && scenario === "missing-production") values["生产能力证据"] = "";
  if (targetIndex === 0 && scenario === "missing-homepage") values["供应商主页"] = "";
  if (targetIndex === 0 && scenario === "tier-mismatch") values["采购数量档位"] = "1件";
  if (targetIndex === 0 && scenario === "tier-price-mismatch") {
    values["阶梯价"] = `500件=${target.supplyTarget + 10} CNY/件；1000件=999 CNY/件`;
  }
  return values;
}

function writeValues(sheet, headers, rowNumber, valuesByHeader, skipHeaders = new Set()) {
  for (const [index, header] of headers.entries()) {
    if (skipHeaders.has(header)) continue;
    const value = valuesByHeader[header] ?? null;
    sheet.getRange(`${columnName(index)}${rowNumber}`).values = [[value]];
    attachExternalHyperlink(sheet, rowNumber - 1, index, value);
  }
  sheet.getRange(`A${rowNumber}:${columnName(headers.length - 1)}${rowNumber}`).format.rowHeight = 100;
}

function addScenarioImages(sheet, headers, rowNumber, imageHeaders, dataUrl, skip = false) {
  if (skip) return;
  for (const header of imageHeaders) {
    sheet.images.add({
      dataUrl,
      anchor: { from: { row: rowNumber - 1, col: headers.indexOf(header) }, extent: { widthPx: 120, heightPx: 75 } },
    });
  }
}

export async function createScenario(templatePath, outputPath, mode, scenario = "valid") {
  if (!["Amazon", "1688", "联合"].includes(mode)) throw new Error(`无效模式：${mode}`);
  const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(templatePath));
  const task = workbook.worksheets.getItem("任务说明");
  task.getRange(`B${TASK_ROW_BY_FIELD["模式"]}`).values = [[mode]];
  task.getRange(`B${TASK_ROW_BY_FIELD["目标产品数量"]}`).values = [[SYNTHETIC_TARGETS.length]];
  const targetSheet = workbook.worksheets.getItem("目标产品");
  const priceSheet = workbook.worksheets.getItem("价格基准");
  for (const [targetIndex, target] of SYNTHETIC_TARGETS.entries()) {
    writeValues(targetSheet, TARGET_HEADERS, 4 + targetIndex, targetScenarioValues(mode, target));
    if (mode !== "1688") {
      for (let sampleIndex = 0; sampleIndex < 5; sampleIndex += 1) {
        const rowNumber = 4 + targetIndex * 5 + sampleIndex;
        writeValues(priceSheet, PRICE_HEADERS, rowNumber, {
          "目标产品ID": target.id, "平台": "Amazon",
          "样本商品ID": scenario === "duplicate-price-product" && targetIndex === 0
            ? `${target.id}-SAME-PRODUCT`
            : `${target.id}-SAMPLE-${sampleIndex + 1}`,
          "跨站产品组ID": `${target.id}-GROUP-${sampleIndex + 1}`,
          "站点": scenario === "price-site-mismatch" && targetIndex === 0 && sampleIndex === 0 ? "US" : "DE",
          "样本状态": "纳入",
          "产品本体门槛": "通过", "外观门槛": "通过", "功能门槛": "通过", "标准价格": target.amazonAverage,
          "标准币种": "CNY", "来源链接": `https://www.amazon.de/dp/${target.id}S${sampleIndex + 1}`,
          "获取时间": "2026-09-04T10:00:00+08:00", "排除原因": "",
        });
      }
    }
  }

  const strictSheet = workbook.worksheets.getItem("严格结果");
  const strictImageHeaders = mode === "Amazon"
    ? ["Amazon商品图片", "Amazon对比图片"]
    : mode === "1688"
      ? ["1688商品图片", "1688对比图片"]
      : ["Amazon商品图片", "Amazon对比图片", "1688商品图片", "1688对比图片"];
  const candidateConfig = mode === "Amazon"
    ? { sheetName: "亚马逊候选", headers: AMAZON_HEADERS, imageHeaders: ["Amazon商品图片"] }
    : mode === "1688"
      ? { sheetName: "1688候选", headers: SUPPLY_HEADERS, imageHeaders: ["1688商品图片"] }
      : { sheetName: "货源匹配", headers: MATCH_HEADERS, imageHeaders: ["Amazon商品图片", "1688商品图片"] };
  const candidateSheet = workbook.worksheets.getItem(candidateConfig.sheetName);
  candidateConfig.imageHeaders = mode === "Amazon"
    ? ["Amazon商品图片", "Amazon对比图片"]
    : mode === "1688"
      ? ["1688商品图片", "1688对比图片"]
      : strictImageHeaders;
  for (const [targetIndex, target] of SYNTHETIC_TARGETS.entries()) {
    const rowNumber = 4 + targetIndex;
    const valuesByHeader = strictScenarioValues(mode, scenario, target, targetIndex);
    writeValues(strictSheet, STRICT_HEADERS, rowNumber, valuesByHeader, PLATFORM_SCORE_HEADERS);
    writeValues(candidateSheet, candidateConfig.headers, rowNumber, {
      ...valuesByHeader,
      "商品标题": valuesByHeader["标题/配对说明"],
      "Amazon商品标题": `合成 Amazon 商品 ${target.id}`,
      "1688商品标题": `合成 1688 商品 ${target.id}`,
      "店铺名称": `合成供应商 ${target.id}`,
    }, PLATFORM_SCORE_HEADERS);
    const inactiveStrictScores = mode === "Amazon" ? SUPPLY_SCORE_HEADERS : mode === "1688" ? AMAZON_SCORE_HEADERS : [];
    for (const header of inactiveStrictScores) {
      strictSheet.getRange(cell(STRICT_HEADERS, header, rowNumber)).clear({ applyTo: "contents" });
    }
    for (const [header, formula] of Object.entries({
      ...(mode !== "1688" ? platformFormulas(STRICT_HEADERS, "amazon", rowNumber) : {}),
      ...(mode !== "Amazon" ? platformFormulas(STRICT_HEADERS, "1688", rowNumber) : {}),
    })) strictSheet.getRange(cell(STRICT_HEADERS, header, rowNumber)).formulas = [[formula]];
    const candidateSides = mode === "Amazon" ? ["amazon"] : mode === "1688" ? ["1688"] : [];
    for (const side of candidateSides) {
      for (const [header, formula] of Object.entries(platformFormulas(candidateConfig.headers, side, rowNumber))) {
        candidateSheet.getRange(cell(candidateConfig.headers, header, rowNumber)).formulas = [[formula]];
      }
    }
    const image = solidPngDataUrl(target.color);
    const skipImages = targetIndex === 0 && scenario === "missing-image";
    addScenarioImages(strictSheet, STRICT_HEADERS, rowNumber, strictImageHeaders, image, skipImages);
    addScenarioImages(candidateSheet, candidateConfig.headers, rowNumber, candidateConfig.imageHeaders, image, skipImages);
  }
  await fs.mkdir(path.dirname(outputPath), { recursive: true });
  const output = await SpreadsheetFile.exportXlsx(workbook);
  await output.save(outputPath);
  console.log(JSON.stringify({ outputPath, mode, scenario }));
}

async function inspectWorkbook(workbookPath) {
  const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(workbookPath));
  const result = await workbook.inspect({ kind: "workbook,sheet,table,formula,drawing", maxChars: 20000, options: { maxResults: 300 } });
  console.log(result.ndjson);
  for (const [sheetId, range] of [
    ["亚马逊候选", `A3:${columnName(AMAZON_HEADERS.length - 1)}4`],
    ["1688候选", `A3:${columnName(SUPPLY_HEADERS.length - 1)}4`],
    ["货源匹配", `A3:${columnName(MATCH_HEADERS.length - 1)}4`],
    ["严格结果", `A3:${columnName(STRICT_HEADERS.length - 1)}4`],
  ]) {
    const formulas = await workbook.inspect({ kind: "formula", sheetId, range, include: "values,formulas", maxChars: 12000, options: { maxResults: 100 } });
    console.log(formulas.ndjson);
  }
  const errors = await workbook.inspect({
    kind: "match",
    searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
    options: { useRegex: true, maxResults: 300 },
    summary: "formula error scan",
  });
  console.log(errors.ndjson);
}

async function renderWorkbook(workbookPath, outputDirectory) {
  const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(workbookPath));
  await fs.mkdir(outputDirectory, { recursive: true });
  for (const sheet of workbook.worksheets.items) {
    const preview = await workbook.render({ sheetName: sheet.name, range: "A1:O8", autoCrop: "all", scale: 1, format: "png" });
    const safeName = sheet.name.replace(/[<>:"/\\|?*]/g, "_");
    await fs.writeFile(path.join(outputDirectory, `${safeName}.png`), new Uint8Array(await preview.arrayBuffer()));
  }
  console.log(JSON.stringify({ outputDirectory, renderedSheets: workbook.worksheets.items.map((sheet) => sheet.name) }));
}

if (command === "build") {
  await buildTemplate(args[0]);
} else if (command === "scenario") {
  await createScenario(args[0], args[1], args[2], args[3] ?? "valid");
} else if (command === "inspect") {
  await inspectWorkbook(args[0]);
} else if (command === "render") {
  await renderWorkbook(args[0], args[1]);
} else if (command !== undefined) {
  throw new Error(`未知命令：${command}`);
}
