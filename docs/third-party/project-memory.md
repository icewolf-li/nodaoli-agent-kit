# project-memory 来源与适配

- 上游：[ArcticZvan/project-memory](https://github.com/ArcticZvan/project-memory)
- 导入版本：[e5fca22c736ecd30d58cdb1306e5ecedc970a121](https://github.com/ArcticZvan/project-memory/tree/e5fca22c736ecd30d58cdb1306e5ecedc970a121)
- 导入日期：2026-10-07（Asia/Shanghai）
- 目录：`skills/project-memory/`
- 保留文件：`SKILL.md`、`SCHEMA.md`、原始 `LICENSE`（MIT，Copyright 2026 ArcticZvan）。

本地适配：

1. 去掉 Cursor 专属存储路径，将上游 `.cursor/memory/` 统一改为 `.memory/`；Skill 名称使用通用的 `project-memory`。
2. 保留按日记录、长期 `project-overview.md`、problem / solution / optimization / decision / correction 类型，以及旧条目的纠错和替代状态。
3. 与本仓库的记忆规则对齐：默认中文、正文简短列表、概览链接 decisions / architecture / TODO 的详细内容；旧日记不批量迁移或改格式。
4. 日期遵循用户当前客户端的日期、时间和时区；必要时查时钟，并转成用户时区。写入前刷新，避免上游“必须使用执行主机本地日期”的要求导致跨时区错日。
5. 增加未验证状态，不将未测试的方案记成 verified；跨日引用使用显式锚点，避免含时间的标题让链接失效。
6. 尊重现有 Git 可见性，不在首次启用时要求额外确认；用户要求只保留本地时再调整忽略规则。

安装器按当前选择将完整 Skill 复制到 `.agents/skills/project-memory/` 和 `.claude/skills/project-memory/`。共享记忆始终放项目根目录 `.memory/`，不会在两套客户端目录中各建一份。

本仓库只维护源 Skill，不在源仓库内运行安装器。更新上游时只比较上述三个文件和本地适配，不读取用户电脑上的其他 Skills，也不把旧记忆自动迁移进来。
