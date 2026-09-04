# AGENTS.md

## 项目边界

本仓库只负责 Tech & Res 与 `2050: The Fire Falls` 的科技世界观适配。目标版本为 Victoria 3 `1.13.*`，硬依赖 ID 为 `tech.res` 和 `alter_time_2050_fire_falls`。

## 修改规则

- 本 Mod 必须在两个依赖之后加载，不使用 `replace_path`。
- 首版只拥有 `transnational_activism`、`global_stock_market`、`globalization`、`social_media`、`app_economy` 五个顶层科技覆盖。
- 覆盖必须保留上游的科技 ID、时代、贴图、类别、前置科技和 AI 权重；上游更新后先比较 Firefall 最终定义，再修改本仓库。
- 英文和简体中文本地化键必须成对维护，YAML 文件保留 UTF-8 BOM。
- 不在本仓库复制事件、on_action、开局科技档案、生产方式或其他 FFPA Mod 的逻辑。

## 最低验证

提交前校验 `.metadata/metadata.json`、科技文件括号与顶层键、本地化键集合和 BOM，并运行 `git diff --check`。游戏内验证需同时覆盖新游戏、旧存档和用户日志。
