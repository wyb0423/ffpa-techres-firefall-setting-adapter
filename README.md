# FFPA — Tech & Res Firefall Setting Adapter

为 `[1.13] Tech & Res` 与 `2050: The Fire Falls` 提供轻量世界观适配。首版只重写五项后期社会科技的显示文本与被动效果，不改科技树结构、开局科技档位或解锁关系。

## 必要前置与加载顺序

- `[1.13] Tech & Res`，Workshop ID `3472248460`；
- `2050: The Fire Falls`，Workshop ID `3768192009`。

推荐顺序：

```text
[1.13] Tech & Res
→ 2050: The Fire Falls
→ FFPA — Tech & Res Firefall Setting Adapter
```

本适配包必须最后加载；后加载且再次定义相同科技 ID 的 Mod 会覆盖它。

## 首版改动

- `transnational_activism` → “跨境互助网络”：弱化知识分子单一加成，加入工会互助与较温和的外交约束。
- `global_stock_market` → “跨区结算网络”：改为铸币、政府分红与贸易容量加成。
- `globalization` → “战后再联通”：保留公司数量，并改为贸易容量和市场接入加成。
- `social_media` → “网状公共空间”：降低影响力加成，同时削弱政府权威。
- `app_economy` → “分布式服务平台”：保留最大公司数量 `+1`，并增加电商物流与办公楼吞吐量。

没有使用 `replace_path`。既有存档继续沿用原科技 ID；载入后应按当前最终定义重新计算科技修正。

## 兼容与验收

Tech & Res 或 Firefall 更新后，需要重新比较这五个完整科技对象并吸收上游新增字段。建议在新游戏与已研究相关科技的旧存档中检查科技名称、说明、tooltip 与实际修正，并在用户日志目录的 `error.log`、`game.log`、`debug.log` 中搜索本适配包相关解析错误。

设计与验证边界见 [`docs/superpowers/specs/2026-09-04-techres-firefall-setting-adapter-design.md`](docs/superpowers/specs/2026-09-04-techres-firefall-setting-adapter-design.md)。
