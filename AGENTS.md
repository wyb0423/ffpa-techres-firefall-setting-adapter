# AGENTS.md

## 项目边界

本仓库负责 Tech & Res 与 `2050: The Fire Falls` 的科技世界观适配，以及 Tech & Res 引入的联合国机制改造。用户已明确要求两者放在同一项目，不拆分独立机制 Mod。目标版本为 Victoria 3 `1.13.*`，硬依赖 ID 为 `tech.res` 和 `alter_time_2050_fire_falls`。

2026-09-09 已批准接入 CMF，新增硬依赖 `com.github.Victoria-3-Modding-Co-op.Community-Mod-Framework`。CMF 在两个内容前置之前加载，本适配包仍最后加载。公共组织页只读；原国家日志保留操作与状态接口。进度使用 CMF 底层 GUI 组件直接绑定只读数值，不新增投票时钟或角色缓存。设计见 `docs/superpowers/specs/2026-09-09-compact-cmf-design.md`。

## 修改规则

- 本 Mod 必须在两个依赖之后加载，不使用 `replace_path`。
- 首版只拥有 `transnational_activism`、`global_stock_market`、`globalization`、`social_media`、`app_economy` 五个顶层科技覆盖。
- 已有 0.2.0 按已批准的 B1 方案 1 增加 `international_organizations`、`decolonization`、`neoimperialism` 三项科技覆盖。科技对象仍只修改文本与被动数值，保留三个布尔 modifier；后续联合国机制通过独立脚本在本项目内改造，不把科技布尔当作机制总开关。
- 覆盖必须保留上游的科技 ID、时代、贴图、类别、前置科技和 AI 权重；上游更新后先比较 Firefall 最终定义，再修改本仓库。
- 英文和简体中文本地化键必须成对维护，YAML 文件保留 UTF-8 BOM。
- 2026-09-09 已批准增加青霉素、社会民主主义、疫苗接种运动、遗传病筛检、新女权主义、基因工程六项人口适配。五项出生率各 +5%，六项合计净增劳动力比例 10 个百分点、死亡率额外 -4%；保留其他原有效果。数值见 `docs/superpowers/specs/2026-09-09-population-recovery-design.md`。
- 联合国机制采用已选“幸存者协定／专注重建合作”方向，拥有会员、议会、教育、贸易、单个工程项目及对应 AI、迁移和旧限制清理；不实施已取消的调停、领土裁判或集体战争。
- 允许为上述机制新增或定点覆盖事件、决议、日志、按钮、scripted effects/triggers/values、修正和 on_action。先追踪调用链，再选择最小覆盖；不整份恢复 Firefall 已删除的上游 on_action。
- 全局议会时钟统一推进，不能由各国日志各自递减；玩家与 AI 同为三个月投票、结算后九个月冷却。
- 协议自选参加，入会不自动改法或批量创建履约日志；AI 必须覆盖提案、表决、参加、实际改革与投资全过程。
- 不复制开局科技档案、生产方式或其他 FFPA Mod 的定居、统一战争与经济逻辑。涉及共享法律、AI 策略或独立倾向时仅清理联合国附加条件，保留最终定义的其他行为。
- 核条约仅做会员识别与旧档兼容，不擅自解除条约及其退出锁定期。
- 设计决策与已确认数值见 `docs/2026-09-07-un-system-research-and-options.md` 第 7.8–7.13 节，实施次序见 `docs/superpowers/plans/2026-09-07-survivor-compact-implementation-plan.md`。用户后续指示优先于文档。

## 最低验证

提交前校验 `.metadata/metadata.json`、所有修改脚本的括号与顶层键、本地化键集合和 BOM，并运行 `git diff --check`。对机制逻辑保留最小可运行静态／状态检查，不将模型检查当成游戏引擎验证。

游戏内验证需覆盖新游戏、旧存档和用户日志，以及不同会员数下的三个月投票／九个月冷却、AI 全流程、晚入会日志数量、退会重入、数值叠加和旧事件清理。不能启动游戏时明确未完成的验证，不宣称已经实机通过。
