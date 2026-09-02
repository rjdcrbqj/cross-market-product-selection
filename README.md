# 通用跨市场选品与货源匹配 Skill

这是一个面向 Amazon、1688 和两端货源匹配的通用选品工作流。它不把某一类产品的外形规则写死：保温杯、工具、家具或其他品类都先按本次任务确认外观、功能、价格和排除项，再用可追溯证据筛选。

当前稳定版本：[`v1.1.0`](https://github.com/rjdcrbqj/cross-market-product-selection/releases/tag/v1.1.0)。

## 安装与调用

在 Codex 中新建任务，复制下面的内容安装固定的 v1.1.0：

```text
请使用 $skill-installer 安装这个 Skill：
https://github.com/rjdcrbqj/cross-market-product-selection/tree/v1.1.0/skills/cross-market-product-selection
```

需要复现旧行为时，仍可安装历史版本 v1.0.0：

```text
请使用 $skill-installer 安装这个 Skill：
https://github.com/rjdcrbqj/cross-market-product-selection/tree/v1.0.0/skills/cross-market-product-selection
```

希望使用仓库最新版本时，使用 `main`：

```text
请使用 $skill-installer 安装这个 Skill：
https://github.com/rjdcrbqj/cross-market-product-selection/tree/main/skills/cross-market-product-selection
```

安装后请重启或重新加载 Codex；在新任务中显式输入 `$cross-market-product-selection`，以确保调用的是这个 Skill。

## 开始前需要确认什么

正式批量检索前，先确认目标产品外观及下列会改变筛选结论的信息；资料不全时可以做少量探索，但不能直接给出“严格合格”名单。

| 需要确认的内容 | 说明 |
| --- | --- |
| 任务范围 | Amazon、1688 或联合模式；站点、国家/地区、品类和目标数量 |
| 参考资料 | 参考图片、商品链接、ASIN、1688 商品 ID 或可描述的结构特征 |
| 外观与排除项 | 必须出现的外观特点、允许变化，以及不能接受的结构、颜色、套装或配件 |
| 功能 | 必须功能、可选功能和排除功能；最终以详情页、规格或说明书等功能证据核验 |
| 价格 | Amazon 使用目标售价，1688 使用目标成本；同时确认币种、目标采购数量/MOQ 和价格允许偏差 |
| 数据口径 | 销量统计周期、评价口径、跨站点去重方式、缺失数据处理和检索预算 |

可复制的开场示例：

```text
$cross-market-product-selection

模式：Amazon 美国站 + 1688 联合模式；最多需要 10 个严格合格的配对，不足不要凑数。
请先确认参考图片、外观必须特点、功能、排除项、Amazon 目标售价、1688 目标成本、
价格允许偏差、采购数量档位和目标站点。
只有实际主图和功能证据都通过时才进入严格结果；缺证据请转入待核验。
```

## 硬门槛、状态与评分

实际主图与功能证据是硬门槛。标题、关键词、搜索缩略图或推测只能帮助发现候选，不能替代对应商品和变体的实际主图、详情页功能证据或商品身份核验。

- `严格合格`：所有硬门槛都有可靠的通过证据；
- `待核验`：没有明确失败证据，但主图、功能、价格、身份、销量、评价或供应商证据缺失、模糊或冲突；
- `已淘汰`：可靠证据明确显示至少一个硬门槛不通过。

只对严格合格且销量、实际价格、评价证据齐全的候选评分。任一评分证据缺失或冲突，转为待核验，不用 `0`、评论数、BSR、搜索位置或猜测补数，也不凑 Top-N。

平台产品总评分固定为：**销量 40% + 价格 40% + 评价 20%**，不是可编辑的默认权重，也不是联合模式的最终匹配分。其中 Amazon 的价格分比较目标售价，1688 的价格分比较与目标采购数量相符的目标成本。价格相似分按绝对偏差对称计算，越接近目标价格越高；价格允许偏差仅作硬门槛，不进入得分分母：

```text
价格相似分 = MAX(0, 100 × (1 − |实际价格 − 目标价格| ÷ 目标价格))
```

例如目标价格为 150 时，150 得 100 分；135 和 165 都是相同的 10% 偏差，均得 90 分。允许价格范围先作为硬门槛；在范围内才计算价格相似分。

销量只在证据完整的严格合格同组记录内做 MIN/MAX：Amazon 同组至少要求模式、站点、销量来源类型和统计周期一致；1688 至少要求模式、销量来源类型和统计周期一致。单记录组为 100，待核验、已淘汰和不同组记录不参与。评价星级必须处于 0 到任务书确认的平台满分，越界不会被截成 100。

## 三种模式与数据边界

### Amazon

优先使用已配置的 Sorftime。只有 Sorftime 未配置、不可用或缺少必要字段时，才在确认付费范围后用 SerpApi 补充 Amazon 搜索和商品详情。SerpApi 不能核验 1688，不能把评论数、BSR 或搜索位置推断成销量；没有可靠销量时保持空白并转为待核验。

同一站点按站点、ASIN 和变体去重。欧洲综合榜会保留每个分站的观测记录，但同一跨站产品组只在最终榜单占一个位置；没有稳定商品证据时，不能只凭标题或相似图片合并。若需要分国家榜，则各站独立去重、独立排名。

### 1688

1688 的严格 ODM 工厂不等于“店名里有厂”或有一个商品链接。每个严格供应商都必须有：

1. 可识别主体的供应商主页；
2. 生产或制造能力的正向证据；
3. ODM/OEM/定制能力的正向证据；
4. 通过商品硬门槛的相关商品链接，以及与目标数量匹配的阶梯价和 MOQ。

任何一项缺失、打不开或冲突时转为待核验；低价或销量不能抵消供应商门槛。SerpApi 不能作为 1688 商品、供应商、生产能力或 ODM/OEM/定制的核验来源。

### 联合模式

先分别完成 Amazon 市场侧与 1688 供货侧的硬门槛核验，再记录具体配对的外观、功能、规格、成本和 MOQ 证据。联合严格结果需要两侧各自对应的实际主图与链接，并分别呈现市场机会、供应能力、匹配质量的得分或结论及证据；市场机会分不能掩盖供应端证据不足。只有任务说明明确确认最终配对公式与三类权重后才填写最终配对得分和排名，否则保持空白。

## 中文 Excel 交付

新输出使用中文工作表、中文表头、中文状态和中文说明，固定七表为：

`任务说明`、`亚马逊候选`、`1688候选`、`货源匹配`、`严格结果`、`待核验`、`淘汰记录`。固定七表只表示能力；本次模式读取任务说明“模式”的确认值，每个数据行的“模式”须与其一致。

需要外观核验的严格行，会在商品图片单元格位置嵌入商品主图，并保留与同一商品 ID/变体对应的有效 `http(s)` 主图链接、商品链接和来源链接，便于追溯。链接以有效 URL 文本保留；不要求额外创建 Excel 专用超链接对象。图片、来源、评分输入和状态不完整的行不能进入严格结果。

模板、评分和交付前校验均已随 Skill 提供：

- `assets/通用选品数据库模板.xlsx`：中文七表模板；
- `scripts/scoring.py`：固定 4:4:2 评分公式；
- `scripts/validate_workbook.py`：检查中文表头、严格结果、图片、链接、评分和供应商证据。
- `tools/maintain_selection_template.mjs`：仅供仓库维护者用 `@oai/artifact-tool` 重建模板，不是 Skill 运行依赖。

## 项目结构

```text
.
├── README.md
├── skills/cross-market-product-selection/
│   ├── SKILL.md
│   ├── agents/openai.yaml
│   ├── assets/通用选品数据库模板.xlsx
│   ├── references/             # 中文任务确认、证据、Amazon、1688、联合与 SerpApi 规则
│   └── scripts/
│       ├── scoring.py
│       └── validate_workbook.py
├── tests/                      # 评分、文档、模板与校验器测试
├── tools/maintain_selection_template.mjs  # 仅用于维护模板资产
└── docs/releases/v1.1.0.md
```

## 版本

- 稳定版：[v1.1.0](https://github.com/rjdcrbqj/cross-market-product-selection/tree/v1.1.0/skills/cross-market-product-selection)
- 历史稳定版：[v1.0.0](https://github.com/rjdcrbqj/cross-market-product-selection/tree/v1.0.0/skills/cross-market-product-selection)
- 最新开发版：[main](https://github.com/rjdcrbqj/cross-market-product-selection/tree/main/skills/cross-market-product-selection)
- 许可协议：[MIT License](LICENSE)
