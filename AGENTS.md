# 维护 nodaoli-agent-kit

这是个人 Agent 规则与精选 Skills 的源仓库。

- 修改前阅读 `rules/` 中与任务相关的规则。
- `rules/` 是通用规范的唯一来源；`templates/` 只提供安装后的入口适配。
- 未经用户选择，不扫描、读取或导入电脑上已有的 Skills。
- `skills/` 只收录用户主动选择的完整 Skill 目录。
- PowerShell 与 Bash 安装入口应保持相同的项目布局和更新语义。
- 修改安装器后运行 `python scripts/test_install.py`；测试只使用临时创建的示例 Skill。
- 公网安装不依赖克隆仓库，不写入用户全局 Agent 配置。
- 不在管理仓库自身运行安装器；使用 `.tmp/` 内的测试项目。
