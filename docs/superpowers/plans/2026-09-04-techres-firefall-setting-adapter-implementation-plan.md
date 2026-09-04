# Tech & Res × Firefall 世界观适配实施计划

日期：2026-09-04

## 目标

按已批准设计建立一个独立、后加载的兼容 Mod，只覆盖五项后期社会科技的文本和被动修正。

## 实施步骤

1. 建立 Victoria 3 1.13 元数据，声明 `tech.res` 与 `alter_time_2050_fire_falls` 为硬依赖。
2. 从 Firefall 最终科技数据库完整复制五个顶层对象，只改各自的 `modifier`。
3. 用英文与简体中文本地化覆盖五个名称键和五个说明键。
4. 记录加载顺序、兼容边界与实机验收方法。
5. 校验 JSON、顶层键、modifier 引用、本地化键集合、UTF-8 BOM、括号和 Git 差异。

## 完成条件

- 运行时只改动 `transnational_activism`、`global_stock_market`、`globalization`、`social_media`、`app_economy`。
- `app_economy` 保留 `country_max_companies_add = 1`。
- 不使用 `replace_path`，不改科技 ID、前置、时代、贴图、类别或 AI 权重。
- 本适配包在 Tech & Res 与 Firefall 之后加载时成为这五个对象的最终来源。
