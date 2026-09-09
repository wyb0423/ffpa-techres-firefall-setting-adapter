# 资金池仅显示／到账 +1：离线排查

## 已确认的缺陷与修复

`ffpa_sc_aid_settle_pool` 过去仅比较记账变量与新计算金额，并检查修正是否存在。
记账变量不代表引擎中已保存修正的真实倍率。因此，当收入变量为 300、修正实际倍率为 1 时，金额没有变化就会一直跳过重建。接受国服务费与援助强度使用同样的缓存条件。

现在每次有效结算都先移除再添加这三类动态修正，覆盖教育、人才、生产、社会、军事五个资金池。保留原有金额公式、威望分配、提供国固定代价及清理路径；项目期限和冷却不重置。原有存档在下次月度结算或既有退出／战争刷新时重建，无需另设迁移开关。

成本是每个有效接受国每次结算最多多做两组移除／添加，每个提供国每个项目多做一组；没有新增国家扫描或周度调度。不能以离线检查代替实际性能测量。

## 倍率语法的交叉核对

- 本地原版 `common/scripted_effects/00_chris_scripted_effects.txt` 的 `modifier_montenegrin_raiding` 使用 `multiplier = raiding_income`；对应 `common/static_modifiers/montenegrin_modifiers.txt` 的基础财政收入正是 `country_tax_income_add = 1`。
- 本地原版 `events/law_events/education_laws.txt` 使用 `multiplier = var:literacy_teacher_mod`；变量作为倍率并非本项目独有写法。
- 本地 Workshop `3219394272/common/scripted_effects/joi_france_scripted_effects.txt` 也使用 `multiplier = var:radicals_seat`。这只说明同类实现存在，不构成该 Mod 的运行时验证。
- 只读反汇编本地 arm64 可执行文件：`CAddModifierEffect<0>::ExecuteDerived` 在 `0x101a70efc` 求脚本值，并将其传给 `AddTimedModifier`；`CTimedModifier` 构造函数在 `0x103a15d68` 保存传入倍率，非衰减的 `CalculateMultiplier` 在 `0x103a15e64` 返回保存值。没有发现这条路径把永久修正倍率强制设为 1。地址仅对当前本地二进制有效；并未启动或附加游戏进程。
- 在线参考：[Modding Co-op 引擎文档转储](https://github.com/Victoria-3-Modding-Co-op/Modding-Digests/blob/main/1.12.4/docs/effects.log)、[论坛变量倍率示例讨论](https://www.reddit.com/r/victoria3/comments/zm2kad/)。这些版本较旧，最终语法判断以上述本地原版和引擎为依据。Paradox Wiki 页面访问返回 401，没有据此作结论。

## 验证与未确认项

`python3 scripts/check_aid_pool_scripts.py` 注入“账本正确、实际倍率错误”的状态，覆盖五类项目分别有 1／2／3 个提供国的情况。修改前明确失败，修改后恢复原金额与强度，连续刷新不叠加且保留期限。原有退会、战争、减半、零威望分配及资金守恒检查仍通过。

同时通过 `check_aid_pool_model.py`、`check_compact.py --workshop-root <Workshop 根目录>` 和 `git diff --check`。本次改动没有修改本地化和日志界面，工作区已有的这些修改属于其他工作。

**尚未证明第一次出现 +1 的原因。** 注入错误状态不是用户存档的复现；引擎只读分析也不能证明特定加载栈的实际到账。机器无法运行游戏，现有日志早于本机制，故不能排除用户看到基础修正提示、运行版本差异或其他运行时问题。以后实机应对照资金池账面金额、财政明细、实际修正倍率，在月度刷新前后及存档重载后各观察一次；若刷新后仍为 +1，需要继续追踪求值／显示层，不能把本次缓存修复当作完整结案。

## 本轮继续排查：用户确认实际财政收入为 +1

用户明确反馈名称正常、实际增加的财政收入为 +1，且本机无法运行游戏。因此不能把问题归为基础修正提示，也不能声称前述兜底修复解决了首次错误。

本轮重新读取了共享结算、五类包装入口、月度／退会／战争调用和所有财政修正定义。动态倍率仅出现在共享结算的服务费、接受国收益和提供国收入三处；其余固定代价和会员奖励没有这类倍率。没有找到其他遗漏倍率的财政授予入口。

本地 arm64 引擎继续追踪至 `CTimedModifiers::CalculateModifierNode`：`0x100117718` 调用 `CalculateMultiplier`，在 `0x1001177e4` 将结果传给修正聚合，而非直接使用常数 1。`CAddModifierEffect::PostInit` 只补默认永久期限，没有重置倍率。这否定了目前提出的“省略期限就一定忽略倍率”推断，不能据此添加任意期限来假装修复。只读反汇编仍不是运行证明。

本机 `content_load.json` 没有加载本适配器，现有日志和存档均早于本机制，不能用这套加载记录代表出现故障的机器。

### 手动诊断入口

新增 `common/scripted_effects/ffpa_compact_aid_debug.txt`，没有自动调用、不改变变量或修正。加载当前文件后，在出现故障的提供国使用调试控制台：

```text
effect ffpa_sc_aid_debug = yes
```

在 `logs/debug.log` 中搜索 `FFPA_AID`。输出包含本国账面周收入、各池分配、本国财政收入／支出的真实汇总修正，以及实际已挂载收入、服务费和收益修正的引擎提示。汇总修正包含其他来源，不能直接把全国汇总与单池金额相等作为验收标准。诊断字符串及控制台调用尚待游戏执行验证。

先保留首次输出，再通过原有刷新入口执行并重新取样：

```text
effect ffpa_sc_aid_refresh_all = yes
effect ffpa_sc_aid_debug = yes
```

刷新会按现有规则重新结算所有活动援助池，但不推进月份。若账面金额大于 1、首次挂载值为 1，刷新后仍为 1，便可确认兜底重建无效，需要拿这次运行的错误日志和存档继续查求值／加载路径；若恢复，则继续核对下次财政更新及存档重载后的真实收支。接受国用同一诊断入口检查服务费与收益缩放。

新增静态断言覆盖五类收入与服务费的基础金额、诊断入口只读且不自动调度。援助脚本、资金池模型、协定静态／状态检查、本地化与日志展示检查及 `git diff --check` 均通过。根因与实机到账仍未确认；本轮交付是继续诊断能力和验证补强，不是已证实的最终修复。
