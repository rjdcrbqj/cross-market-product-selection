// Maintenance-only generator for the committed workbook asset.
// This file is not a runtime dependency of the installed Skill.
import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const [, , command, ...args] = process.argv;

export const AMAZON_HEADERS = [
  "状态", "模式", "排名", "Amazon商品图片", "站点", "Amazon ASIN", "Amazon变体/SKU", "品牌", "商品标题",
  "Amazon链接", "Amazon主图链接", "产品本体门槛", "外观门槛", "功能门槛", "价格/MOQ门槛",
  "详情身份门槛", "证据一致性门槛", "门槛原因", "Amazon目标售价", "Amazon实际售价", "Amazon币种",
  "Amazon销量", "Amazon销量来源类型", "Amazon销量统计周期", "Amazon评价星级", "Amazon评价数量",
  "Amazon销量得分", "Amazon价格得分", "Amazon评价得分", "Amazon产品总评分", "核心通过证据", "来源类型",
  "来源链接", "检索路径", "获取时间", "置信度", "冲突说明", "决策日志引用",
];

export const SUPPLY_HEADERS = [
  "状态", "模式", "排名", "1688商品图片", "1688商品ID", "1688 SKU/规格", "供应商ID", "店铺名称", "商品标题",
  "1688链接", "供应商主页", "1688主图链接", "产品本体门槛", "外观门槛", "功能门槛", "价格/MOQ门槛",
  "供应商门槛", "生产能力门槛", "ODM/OEM/定制门槛", "证据一致性门槛", "门槛原因", "目标成本",
  "实际单价", "成本币种", "采购数量档位", "MOQ", "1688销量", "1688销量来源类型", "1688销量统计周期",
  "1688评价星级", "1688评价数量", "1688销量得分", "1688价格得分", "1688评价得分", "1688产品总评分",
  "生产能力证据", "ODM/OEM/定制证据", "核心通过证据", "来源类型", "来源链接", "检索路径", "获取时间",
  "置信度", "冲突说明", "决策日志引用",
];

export const MATCH_HEADERS = [
  "状态", "模式", "排名", "记录/配对ID", "Amazon商品图片", "1688商品图片", "站点", "Amazon ASIN",
  "Amazon变体/SKU", "1688商品ID", "1688 SKU/规格", "供应商ID", "Amazon商品标题", "1688商品标题",
  "Amazon链接", "1688链接", "Amazon主图链接", "1688主图链接", "供应商主页", "产品本体门槛", "外观门槛",
  "功能门槛", "价格/MOQ门槛", "详情身份门槛", "供应商门槛", "生产能力门槛", "ODM/OEM/定制门槛",
  "证据一致性门槛", "外观匹配说明", "功能匹配说明", "市场机会得分", "市场机会结论", "市场机会证据",
  "供应能力得分", "供应能力结论", "供应能力证据", "匹配质量得分", "匹配质量结论", "匹配质量证据",
  "最终配对得分", "生产能力证据", "ODM/OEM/定制证据", "主要限制", "来源类型", "来源链接", "检索路径",
  "获取时间", "置信度", "冲突说明", "决策日志引用",
];

export const STRICT_HEADERS = [
  "状态", "模式", "排名", "Amazon商品图片", "1688商品图片", "记录/配对ID", "站点", "Amazon ASIN",
  "Amazon变体/SKU", "1688商品ID", "1688 SKU/规格", "供应商ID", "标题/配对说明", "Amazon链接", "1688链接",
  "供应商主页", "Amazon主图链接", "1688主图链接", "产品本体门槛", "外观门槛", "功能门槛", "价格/MOQ门槛",
  "详情身份门槛", "供应商门槛", "生产能力门槛", "ODM/OEM/定制门槛", "证据一致性门槛", "外观匹配说明",
  "功能匹配说明", "Amazon目标售价", "Amazon实际售价", "Amazon币种", "Amazon销量", "Amazon销量来源类型",
  "Amazon销量统计周期", "Amazon评价星级", "Amazon评价数量", "Amazon销量得分", "Amazon价格得分", "Amazon评价得分",
  "Amazon产品总评分", "目标成本", "实际单价", "成本币种", "1688销量", "1688销量来源类型", "1688销量统计周期",
  "1688评价星级", "1688评价数量", "1688销量得分", "1688价格得分", "1688评价得分", "1688产品总评分",
  "市场机会得分", "市场机会结论", "市场机会证据", "供应能力得分", "供应能力结论", "供应能力证据",
  "匹配质量得分", "匹配质量结论", "匹配质量证据", "最终配对得分", "核心通过证据", "生产能力证据",
  "ODM/OEM/定制证据", "主要限制", "来源类型", "来源链接", "检索路径", "获取时间", "置信度", "冲突说明",
  "决策日志引用", "输出时间",
];

const PLATFORM_SCORE_HEADERS = new Set([
  "Amazon销量得分", "Amazon价格得分", "Amazon评价得分", "Amazon产品总评分",
  "1688销量得分", "1688价格得分", "1688评价得分", "1688产品总评分",
]);

const PENDING_HEADERS = [
  "状态", "模式", "记录/配对ID", "平台", "商品图片", "Amazon ASIN", "1688商品ID", "标题/配对说明",
  "缺失或冲突门槛", "现有证据", "补证据动作", "Amazon链接", "1688链接", "主图链接", "证据链接",
  "用户保留决定", "决策日志引用", "更新时间",
];

const REJECTED_HEADERS = [
  "状态", "模式", "记录/配对ID", "平台", "商品图片", "Amazon ASIN", "1688商品ID", "标题/配对说明",
  "失败门槛", "失败事实", "证据链接", "Amazon链接", "1688链接", "决策日志引用", "淘汰时间",
];

const TASK_ROWS = [
  ["模式", "", "Amazon / 1688 / 联合；固定七表仅表示能力，不能据表头推断模式"],
  ["业务目标", "", "说明严格清单要支持的业务决策"],
  ["品类/用途", "", "填写目标产品与使用场景"],
  ["市场/范围", "", "填写站点、国家、区域或供应范围"],
  ["参考图片/链接", "", "填写参考图片、商品链接、ASIN 或 1688 商品ID"],
  ["目标数量", "", "填写最多需要的严格结果数；允许少于该数量"],
  ["外观必须特点", "", "仅凭实际主图可核验的必备形态、颜色或组合"],
  ["允许变化", "", "填写可以接受的外观、规格或包装差异"],
  ["外观排除项", "", "填写明确排除的形态、颜色、附件或变体"],
  ["必须功能", "", "填写必须由可靠证据确认的功能"],
  ["可选功能", "", "填写加分但不作为硬门槛的功能"],
  ["排除功能", "", "填写出现即淘汰的功能或用途"],
  ["目标售价", "", "Amazon 价格得分只与该目标售价双向比较"],
  ["目标成本", "", "1688 价格得分只与该目标成本双向比较"],
  ["币种", "", "填写目标售价与目标成本使用的币种"],
  ["采购数量档位", "", "填写用于核验 1688 实际单价的采购数量"],
  ["价格允许偏差", "", "仅作价格硬门槛；不进入价格得分分母"],
  ["销量统计周期", "", "填写月、近30天或其他明确周期"],
  ["评价口径", "", "填写星级来源、评价数量范围及变体合并规则"],
  ["跨站点去重口径", "", "填写 ASIN、稳定商品ID或规范链接等去重规则"],
  ["关键字段", "", "列明本任务额外必填与可选字段"],
  ["缺失值策略", "缺失保持空白；硬门槛证据不足转待核验", "未知值不得写成 0、否或推断值"],
  ["用户确认状态", "待用户确认", "确认后改为“已确认”；未确认不得批量付费检索"],
  ["销量权重", 0.4, "平台产品总评分固定权重 40%，不可改写"],
  ["价格权重", 0.4, "平台产品总评分固定权重 40%，不可改写"],
  ["评价权重", 0.2, "平台产品总评分固定权重 20%，不可改写"],
  ["权重合计", null, "固定权重合计必须等于 100%"],
  ["评价满分星级", 5, "评价得分仅接受 0 到该满分；越界不得截断"],
  ["评分下限", 0, "标准化分数不得低于该值"],
  ["评分满分", 100, "销量、价格、评价三个分项的统一满分"],
  ["价格评分规则", "Amazon 对目标售价；1688 对目标成本；按绝对偏差率双向接近", "公式为 MAX(0,100*(1-ABS(actual-target)/target))"],
  ["证据不足处理", "三项评分任一原始证据缺失即转待核验", "不得把缺失值写成 0，也不得进入严格排名"],
  ["结果数量规则", "严格结果不足目标数量时如实少于 Top-N", "不得用待核验或淘汰项凑数"],
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

function columnRange(headers, header) {
  const column = columnName(headers.indexOf(header));
  return `$${column}$4:$${column}$103`;
}

function columnWidth(header) {
  if (header.includes("商品图片")) return 20;
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

function addStatusRules(sheet) {
  const statusRange = sheet.getRange("A4:A103");
  statusRange.dataValidation = { rule: { type: "list", values: ["严格合格", "待核验", "已淘汰"] } };
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
    else if (header.includes("时间")) range.format.numberFormat = "yyyy-mm-dd hh:mm";
    if (header.includes("ID") || header.includes("ASIN") || header.includes("SKU")) range.format.numberFormat = "@";
  });
}

function platformFormulas(headers, side) {
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
  const status = "$A4";
  const mode = cell(headers, "模式");
  const sales = cell(headers, names.sales);
  const source = cell(headers, names.source);
  const period = cell(headers, names.period);
  const target = cell(headers, names.target);
  const actual = cell(headers, names.actual);
  const rating = cell(headers, names.rating);
  const salesRange = columnRange(headers, names.sales);
  const criteria = [
    ["状态", '"严格合格"'],
    ["模式", mode],
    ...(side === "amazon" ? [["站点", cell(headers, "站点")]] : []),
    [names.source, source],
    [names.period, period],
  ];
  const criteriaArguments = criteria.flatMap(([header, criterion]) => [columnRange(headers, header), criterion]).join(",");
  const count = `COUNTIFS(${criteriaArguments})`;
  const minimum = `MINIFS(${salesRange},${criteriaArguments})`;
  const maximum = `MAXIFS(${salesRange},${criteriaArguments})`;
  const requiredGroupCells = [mode, ...(side === "amazon" ? [cell(headers, "站点")] : []), source, period, sales];
  const salesFormula = `=IF(OR(${status}<>"严格合格",${requiredGroupCells.map((value) => `${value}=""`).join(",")}),"",ROUND(IF(${count}<=1,100,IF(${maximum}=${minimum},100,(${sales}-${minimum})/(${maximum}-${minimum})*100)),2))`;
  const priceFormula = `=IF(OR(${status}<>"严格合格",${target}="",${actual}="",${target}<=0,${actual}<0),"",ROUND(MAX(0,100*(1-ABS(${actual}-${target})/${target})),2))`;
  const ratingFormula = `=IF(OR(${status}<>"严格合格",${rating}="",${taskRef("评价满分星级")}="",${rating}<0,${rating}>${taskRef("评价满分星级")}),"",ROUND(100*${rating}/${taskRef("评价满分星级")},2))`;
  const salesScore = cell(headers, names.salesScore);
  const priceScore = cell(headers, names.priceScore);
  const ratingScoreCell = cell(headers, names.ratingScore);
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
  sheet.getRange(`B4:B${TASK_ROW_BY_FIELD["用户确认状态"]}`).format.fill = "#FFF4CE";
  sheet.getRange(`B${TASK_ROW_BY_FIELD["销量权重"]}:B${TASK_ROW_BY_FIELD["权重合计"]}`).format.fill = "#E8F0FE";
  sheet.getRange(`B${TASK_ROW_BY_FIELD["模式"]}`).dataValidation = { rule: { type: "list", values: ["Amazon", "1688", "联合"] } };
  sheet.getRange(`B${TASK_ROW_BY_FIELD["用户确认状态"]}`).dataValidation = { rule: { type: "list", values: ["待用户确认", "已确认", "需补充"] } };
  sheet.getRange(`B${TASK_ROW_BY_FIELD["价格允许偏差"]}`).format.numberFormat = "0.0%";
  sheet.getRange(`B${TASK_ROW_BY_FIELD["销量权重"]}:B${TASK_ROW_BY_FIELD["权重合计"]}`).format.numberFormat = "0%";
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
  addStatusRules(sheet);
  setSemanticFormats(sheet, config.headers);
  return sheet;
}

export async function buildTemplate(outputPath) {
  const workbook = Workbook.create();
  buildTaskSheet(workbook);
  buildDataSheet(workbook, {
    name: "亚马逊候选", title: "亚马逊候选",
    description: "评分只计算证据完整且状态为严格合格的同模式、同站点、同销量来源类型与同统计周期记录。",
    headers: AMAZON_HEADERS, tableName: "AmazonCandidatesTable", formulas: platformFormulas(AMAZON_HEADERS, "amazon"),
  });
  buildDataSheet(workbook, {
    name: "1688候选", title: "1688候选",
    description: "严格核验商品、供应商主体、生产能力与明确 ODM/OEM/定制证据；评分仅使用同组严格行。",
    headers: SUPPLY_HEADERS, tableName: "SupplyCandidatesTable", formulas: platformFormulas(SUPPLY_HEADERS, "1688"),
  });
  buildDataSheet(workbook, {
    name: "货源匹配", title: "Amazon × 1688 货源匹配",
    description: "市场机会、供应能力与匹配质量分别记录结论和证据；未确认最终配对公式及三类权重时不填最终分和排名。",
    headers: MATCH_HEADERS, tableName: "SourceMatchesTable",
  });
  buildDataSheet(workbook, {
    name: "严格结果", title: "严格结果",
    description: "仅收录全部适用硬门槛与原始评分证据已确认的记录；单平台只要求本侧，联合要求两侧并分离三类判断。",
    headers: STRICT_HEADERS, tableName: "StrictResultsTable",
    formulas: { ...platformFormulas(STRICT_HEADERS, "amazon"), ...platformFormulas(STRICT_HEADERS, "1688") },
  });
  buildDataSheet(workbook, {
    name: "待核验", title: "待核验",
    description: "没有明确失败但缺少可靠硬门槛或评分原始证据的记录放在这里；写清缺口、现有证据与补证据动作。",
    headers: PENDING_HEADERS, tableName: "PendingAuditTable",
  });
  buildDataSheet(workbook, {
    name: "淘汰记录", title: "淘汰记录",
    description: "只记录已有可靠证据确认失败的记录；必须保留稳定身份、具体失败门槛、失败事实与证据链接。",
    headers: REJECTED_HEADERS, tableName: "RejectedAuditTable",
  });
  for (const sheet of workbook.worksheets.items) sheet.freezePanes.freezeRows(3);
  await fs.mkdir(path.dirname(outputPath), { recursive: true });
  const output = await SpreadsheetFile.exportXlsx(workbook);
  await output.save(outputPath);
  console.log(JSON.stringify({ outputPath, sheets: workbook.worksheets.items.map((sheet) => sheet.name) }));
}

function strictScenarioValues(mode, scenario) {
  const gates = {
    "产品本体门槛": "通过", "外观门槛": "通过", "功能门槛": "通过", "价格/MOQ门槛": "通过",
    "详情身份门槛": "通过", "供应商门槛": "通过", "生产能力门槛": "通过",
    "ODM/OEM/定制门槛": "通过", "证据一致性门槛": "通过",
  };
  const amazon = {
    "站点": "US", "Amazon ASIN": "B0SYNTH001", "Amazon变体/SKU": "BLACK-STD",
    "Amazon链接": "https://www.amazon.com/dp/B0SYNTH001", "Amazon主图链接": "https://images.example.com/amazon.png",
    "Amazon目标售价": 150, "Amazon实际售价": 135, "Amazon币种": "USD", "Amazon销量": 100,
    "Amazon销量来源类型": "合成月销量", "Amazon销量统计周期": "近30天", "Amazon评价星级": 4.5,
    "Amazon评价数量": 200,
  };
  const supply = {
    "1688商品ID": "168800000001", "1688 SKU/规格": "STANDARD", "供应商ID": "SUPPLIER-001",
    "1688链接": "https://detail.1688.com/offer/168800000001.html", "供应商主页": "https://supplier.example.com/company/SUPPLIER-001",
    "1688主图链接": "https://images.example.com/1688.png", "目标成本": 100, "实际单价": 90, "成本币种": "CNY",
    "1688销量": 50, "1688销量来源类型": "合成近30天销量", "1688销量统计周期": "近30天",
    "1688评价星级": 4, "1688评价数量": 20,
    "生产能力证据": "同一供应商主体页面列出注塑与组装生产线",
    "ODM/OEM/定制证据": "同一供应商主体支持 OEM、打样和来图定制",
  };
  const values = {
    "状态": "严格合格", "模式": mode, "排名": mode === "联合" ? "" : 1, "记录/配对ID": `SYNTH-${mode}`,
    "标题/配对说明": "合成集成测试记录", ...gates,
    "外观匹配说明": "合成主图与任务书外观一致", "功能匹配说明": "合成详情证据确认功能",
    "核心通过证据": "合成详情、图片、身份与门槛证据", "来源类型": "合成离线测试",
    "来源链接": "https://evidence.example.com/synthetic", "检索路径": "本地合成集成夹具",
    "获取时间": "2026-09-02T10:00:00+08:00", "置信度": "高", "决策日志引用": "SYNTH-001",
    "输出时间": "2026-09-02T10:05:00+08:00",
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
  if (scenario === "odm-color") values["ODM/OEM/定制证据"] = "支持颜色选择";
  if (scenario === "production-store") values["生产能力证据"] = "店名：某某制造厂";
  if (scenario === "production-link") values["生产能力证据"] = values["1688链接"];
  if (scenario === "missing-production") values["生产能力证据"] = "";
  if (scenario === "missing-homepage") values["供应商主页"] = "";
  return values;
}

export async function createScenario(templatePath, outputPath, mode, scenario = "valid") {
  if (!["Amazon", "1688", "联合"].includes(mode)) throw new Error(`无效模式：${mode}`);
  const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(templatePath));
  const task = workbook.worksheets.getItem("任务说明");
  task.getRange(`B${TASK_ROW_BY_FIELD["模式"]}`).values = [[mode]];
  task.getRange(`B${TASK_ROW_BY_FIELD["用户确认状态"]}`).values = [["已确认"]];
  const sheet = workbook.worksheets.getItem("严格结果");
  const valuesByHeader = strictScenarioValues(mode, scenario);
  for (const [index, header] of STRICT_HEADERS.entries()) {
    if (PLATFORM_SCORE_HEADERS.has(header)) continue;
    sheet.getRange(`${columnName(index)}4`).values = [[valuesByHeader[header] ?? null]];
  }
  const transparentPng = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Wl+ZR0AAAAASUVORK5CYII=";
  const imageHeaders = mode === "Amazon" ? ["Amazon商品图片"] : mode === "1688" ? ["1688商品图片"] : ["Amazon商品图片", "1688商品图片"];
  if (scenario !== "missing-image") {
    for (const header of imageHeaders) {
      sheet.images.add({
        dataUrl: transparentPng,
        anchor: { from: { row: 3, col: STRICT_HEADERS.indexOf(header) }, extent: { widthPx: 120, heightPx: 75 } },
      });
    }
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
    ["亚马逊候选", "A3:AL4"],
    ["1688候选", "A3:AS4"],
    ["严格结果", "A3:BW4"],
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
