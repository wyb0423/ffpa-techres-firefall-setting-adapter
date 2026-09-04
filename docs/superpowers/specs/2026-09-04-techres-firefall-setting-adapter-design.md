# Tech & Res × Firefall 世界观适配设计

日期：2026-09-04

## 目标

建立独立的 `FFPA — Tech & Res Firefall Setting Adapter`，以少量科技覆盖缓解 Tech & Res 现实时间线与 Firefall 核战后世界观的冲突。第一阶段只调整五项后期社会科技的显示文本和被动效果，不改科技 ID、时代、前置关系、解锁内容或 AI 权重。

## 已确认环境

- Victoria 3：`1.13.*`
- Tech & Res：Workshop `3472248460`，Mod ID `tech.res`，已安装版本 `1.6'`
- 2050: The Fire Falls：Workshop `3768192009`，Mod ID `alter_time_2050_fire_falls`，已安装版本 `0.1.1`
- Firefall 开局日期为 `2050.1.1`。
- 当前 Firefall 的 `common/technology` 与 Tech & Res 同目录内容逐文件一致；按既定加载顺序，Firefall 是本适配包需要覆盖的最终科技来源。
- Firefall 为 789 个国家应用低科技档案、5 个国家应用中等科技档案、7 个国家应用先进科技档案。中等档案已经包含 `international_organizations`；先进档案还包含 `decolonization` 与 `neoimperialism`。

## 发布边界

新项目目录：`ffpa-techres-firefall-setting-adapter`

玩家可见名称：`FFPA — Tech & Res Firefall Setting Adapter`

Mod ID：`com.wyb.ffpa-techres-firefall-setting-adapter`

首版：`0.1.0`

硬依赖：

- `tech.res` / `[1.13] Tech & Res` / `1.*`
- `alter_time_2050_fire_falls` / `2050: The Fire Falls` / `0.1.*`

本适配包必须在 Tech & Res 与 Firefall 之后加载。它不依赖 FFPA Firefall Flavor Pack、Core Balance Adapter、Building Pruning 或 Auto PM Adapter；这些包也不反向依赖本适配包。

## 第一阶段科技覆盖

每项科技保留上游的 `era`、`texture`、`category`、`unlocking_technologies` 和 `ai_weight`。覆盖文件完整重述五个顶层科技对象，只替换 `modifier`。

### `transnational_activism`

显示名称：

- English: `Cross-Border Solidarity Networks`
- 简体中文：`跨境互助网络`

显示说明：

- English: `The fire erased many borders without erasing the need for cooperation. Radio relays, caravan couriers, and recovering data links let unions, scholars, and local associations exchange warnings, coordinate relief, and restrain new powers across the scattered settlements.`
- 简体中文：`大火抹去了许多国界，却没有消除跨地域合作的需要。无线电中继、商队信使与逐步恢复的数据链路，使工会、学者和地方团体能够在分散的聚落之间交换警报、协调救援，并共同约束重新崛起的强权。`

新效果：

```text
interest_group_ig_intelligentsia_pol_str_mult = 0.25
interest_group_ig_trade_unions_pol_str_mult = 0.25
country_infamy_generation_against_unrecognized_mult = 0.1
```

相对上游：知识分子政治力量由 `+100%` 降至 `+25%`，新增工会政治力量 `+25%`，针对未受承认国家的恶名由 `+20%` 降至 `+10%`。

### `global_stock_market`

显示名称：

- English: `Interregional Clearing Network`
- 简体中文：`跨区结算网络`

显示说明：

- English: `The old exchanges and their instant global markets are gone. Standard ledgers, trusted clearing houses, radio quotations, and guarded courier routes now reconnect surviving markets well enough for capital to cross regional frontiers again.`
- 简体中文：`旧证券交易所及其即时全球市场已经消失。统一账册、可信清算所、无线电报价与受护送的信使路线重新连接起幸存市场，使资本得以再次跨越地区边界。`

新效果：

```text
country_minting_mult = 0.05
country_government_dividends_efficiency_add = 0.05
state_trade_capacity_mult = 0.05
```

相对上游：铸币收入由 `+10%` 降至 `+5%`，保留政府分红效率 `+5%`，移除免费公司特许权，新增贸易容量 `+5%`。

### `globalization`

显示名称：

- English: `Postwar Reconnection`
- 简体中文：`战后再联通`

显示说明：

- English: `This is not a return to the effortless global economy of the old world. Reopened ports, repaired rail corridors, common commercial standards, and long-distance relay networks gradually bind isolated markets into a fragile new system of exchange.`
- 简体中文：`这并非旧世界无缝全球经济的回归。重新开放的港口、修复的铁路走廊、共同商业标准和长途通信中继，正把彼此孤立的市场逐步连接成一套脆弱的新交换体系。`

新效果：

```text
country_max_companies_add = 1
state_trade_capacity_mult = 0.05
state_market_access_price_impact = 0.05
```

相对上游：保留最大公司数量 `+1`，移除识字带来的预期生活水平、劳动人口比例和污染健康红利，新增贸易容量与市场接入价格影响各 `+5%`。

### `social_media`

显示名称：

- English: `Mesh Public Sphere`
- 简体中文：`网状公共空间`

显示说明：

- English: `The centralized platforms of the old world did not survive intact. Local servers, radio-linked message boards, and improvised mesh networks let distant communities speak to one another again, expanding their reach while weakening any government's monopoly over information.`
- 简体中文：`旧世界的集中式平台未能完整幸存。地方服务器、无线电互联的信息板和临时搭建的网状网络，使遥远社区得以重新对话；它们扩大了社会影响，也削弱了政府对信息的垄断。`

新效果：

```text
country_influence_mult = 0.05
country_authority_mult = -0.05
```

相对上游：影响力由 `+10%` 降至 `+5%`，新增权威力 `-5%`。

### `app_economy`

显示名称：

- English: `Distributed Service Platforms`
- 简体中文：`分布式服务平台`

显示说明：

- English: `Recovered software stacks and rebuilt payment links allow merchants, offices, and freight operators to coordinate through distributed service platforms. The most successful operators grow into a new generation of companies adapted to unreliable infrastructure.`
- 简体中文：`恢复的软件栈与重建的支付链路，使商户、办公机构和货运经营者能够通过分布式服务平台协同运作。其中最成功的经营者逐渐成长为适应不稳定基础设施的新一代公司。`

新效果：

```text
country_max_companies_add = 1
building_ecommerce_logistics_throughput_add = 0.05
building_office_throughput_add = 0.05
```

相对上游：保留最大公司数量 `+1`，新增电商物流与办公楼吞吐量各 `+5%`。

## 文件结构

第一阶段运行时只需要以下文件：

```text
.metadata/metadata.json
common/technology/technologies/zzzz_ffpa_techres_firefall_society.txt
localization/english/ffpa_techres_firefall_setting_l_english.yml
localization/simp_chinese/ffpa_techres_firefall_setting_l_simp_chinese.yml
README.md
AGENTS.md
.gitignore
```

研究和设计文档放入 `docs/`。不创建事件、on_action、scripted effect、变量、Journal Entry、决议或设置界面。

## 覆盖与兼容

- 五个技术 ID 是上游对象，不改名、不复制为新的并行科技。
- 不使用 `replace_path`，避免接管整个科技目录。
- 上游更新后，以 Tech & Res → Firefall → 本适配包的顺序重新比较五个最终对象；若上游新增字段，覆盖文件必须显式吸收。
- 其他后加载 Mod 若再次定义同一技术 ID，会覆盖本适配包；README 必须登记这一限制。
- 已研究科技继续使用原 ID，不需要存档迁移。加载或移除适配包后，现有存档应按当前最终定义重新计算科技修正，但仍需实机确认。

## 验证

静态验证：

1. `metadata.json` 可由 `jq` 解析，依赖 ID 与版本匹配当前安装。
2. 科技文件花括号平衡，且只含五个预期顶层键。
3. 每个覆盖对象与 Firefall 最终对象比较，差异仅为已登记的 `modifier` 内容。
4. 英文和简中本地化键集合完全一致，各含五个名称键和五个说明键。
5. 两份本地化文件为 UTF-8 BOM，语言头正确。
6. 新项目没有意外重复顶层键；`git diff --check` 无新增空白错误。

实机验证：

1. 新游戏科技树显示五项新名称和说明。
2. 每项科技 tooltip 只显示设计中的修正和原有解锁关系。
3. 读取已经研究这些科技的旧存档，确认国家修正按新定义生效。
4. 禁用本适配包后，科技恢复 Firefall/Tech & Res 上游定义，存档不丢失研究状态。
5. 检查 `error.log`、`game.log` 与 `debug.log`，确认没有来自本适配包的解析错误或重复定义异常。

## 明确排除

第一阶段不修改：

- `international_organizations`、`decolonization`、`neoimperialism` 及其布尔机制开关；
- Firefall 的 `tff_tech_low`、`tff_tech_mid`、`tff_tech_advanced` 开局科技档案；
- 科技时代、成本、树形结构、前置关系和 AI 权重；
- 互联网、AI、AGI、数据中心、生产方式、公司定义和未来奇观；
- 现有 FFPA 各 Mod 的文件或依赖关系。

这些高耦合内容只有在第一阶段实机验证后，才作为独立设计继续评估。
