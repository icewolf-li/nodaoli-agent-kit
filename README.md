# nodaoli-agent-kit

个人 Agent 规则与精选 Skills 的源仓库。新项目只下载并安装需要的文件，不需要克隆这个仓库，不写入全局 Agent 配置。

## 一键使用

先进入**目标项目根目录**，再复制执行以下任意一种命令。需要 Python **3.9+**，无需 Git、pip 或提前克隆仓库。

PowerShell（5.1+，推荐 7）：

```powershell
irm https://raw.githubusercontent.com/icewolf-li/nodaoli-agent-kit/main/scripts/install.ps1 | iex
```

curl（Bash）：

```bash
curl -fsSL https://raw.githubusercontent.com/icewolf-li/nodaoli-agent-kit/main/scripts/install.sh | bash
```

wget（Bash）：

```bash
wget -qO- https://raw.githubusercontent.com/icewolf-li/nodaoli-agent-kit/main/scripts/install.sh | bash
```

默认从公开仓库 [icewolf-li/nodaoli-agent-kit](https://github.com/icewolf-li/nodaoli-agent-kit) 的 `main` 下载。首次安装包括 Codex / Claude Code 入口与全部精选 Skills；在已安装的项目重复运行会按原选择更新。

脚本流程：下载共享安装器与仓库 ZIP 到临时目录 → 将规则、Skills 和入口写入当前项目 → 清理下载目录。

| 文件或目录 | 首次执行 | 再次执行 |
| --- | --- | --- |
| `AGENTS.md`、`CLAUDE.md` | 创建或追加管理区块 | 只替换管理区块，保留项目说明 |
| `.agent/rules/`、选用的 `.agent/stack.md` | 复制规则 | 更新受管文件；本地修改有冲突时停止 |
| `.agents/skills/`、`.claude/skills/` | 复制选中的完整 Skill | 按原选择更新，保留无关 Skill |
| `.memory/` | 创建缺失的记忆模板 | 保留已有内容，仅补缺失模板 |
| `.agent/kit.json` | 记录来源与选择 | 更新安装记录 |
| `.gitignore` | 追加备份目录的忽略区块 | 更新该区块，保留原规则 |

将被覆盖的文件会先备份到 `.agent/backups/`。具体更新与定制方法见下方。

## 当前内容

```text
rules/                  通用协作、目录、编码、Git、项目记忆规则
skills/                 你自行选择的完整 Skill 目录（已收录 project-memory）
stacks/                 可选技术栈规则（目前只预留目录）
templates/              AGENTS.md / CLAUDE.md 入口与记忆模板
scripts/install.ps1     PowerShell 公网入口
scripts/install.sh      Bash 公网入口，支持 curl / wget
scripts/install.py      两个入口共用的安装逻辑，仅使用 Python 标准库
scripts/test_install.py 安装与更新行为测试，使用临时示例 Skill
docs/                   维护说明
```

第一版规则根据已确认的方向编写：中文协作、沿用项目结构、根目录保持整洁、保存按日记录的项目记忆、规则与 Skill 分开维护。不假定具体框架、版本或未确认的个人偏好。

## 指定安装参数

PowerShell 用 ScriptBlock 调用下载的脚本：

```powershell
& ([scriptblock]::Create((irm https://raw.githubusercontent.com/icewolf-li/nodaoli-agent-kit/main/scripts/install.ps1))) -ProjectPath 'D:\code\my-project' -NoSkills
```

带参数：

```bash
curl -fsSL https://raw.githubusercontent.com/icewolf-li/nodaoli-agent-kit/main/scripts/install.sh | bash -s -- --project './my-project' --no-skills
```

默认安装 Codex 与 Claude Code 两个入口。`-Agents codex` / `--agents codex` 可以只安装 Codex；`claude` 同理。

## 安装后的项目

```text
my-project/
├─ AGENTS.md                  通用规则读取入口，管理区块之外保留原内容
├─ CLAUDE.md                  通过 @path 导入通用规则
├─ .agent/
│  ├─ rules/                  规则副本
│  ├─ stack.md                选了 Stack 才生成
│  ├─ project.md              项目自行维护的补充规则（安装器不创建、不覆盖）
│  ├─ kit.json                来源、选择、下载摘要和受管文件哈希
│  └─ backups/                更新前的备份，自动加入项目 .gitignore
├─ .agents/skills/            Codex Skill 副本
├─ .claude/skills/            Claude Code Skill 副本
└─ .memory/
   ├─ README.md
   ├─ project-overview.md     长期概览与索引
   ├─ decisions.md
   ├─ architecture.md
   ├─ TODO.md
   └─ YYYY-MM-DD.md           Agent 有真实变化时追加，不生成虚构日记
```

Skills 是完整目录副本，Windows 不需要管理员权限或符号链接。两个客户端使用各自的项目发现目录；新装 Skill 后按客户端需要刷新或重新开始会话。[Codex Skills 文档](https://developers.openai.com/codex/skills)、[Claude Code Skills 文档](https://code.claude.com/docs/en/skills)、[CLAUDE.md 导入规则](https://code.claude.com/docs/en/memory)。

## 把常用 Skills 放进来

你自己选需要的 Skill，将整个文件夹复制到 `skills/<name>/`：

```text
skills/your-skill/SKILL.md
skills/your-skill/scripts/      # 有就一并放入
skills/your-skill/references/   # 有就一并放入
skills/your-skill/assets/       # 有就一并放入
```

SKILL.md 需要包含 `name` 与 `description` frontmatter。目录名用小写英文、数字、连字符，且不要嵌套第二层分类目录。复制整个 Skill，保留相对引用；依赖 MCP/插件的 Skill 仍需在目标环境连接对应工具。细节见 [skills/README.md](skills/README.md)。

首次默认安装仓库中全部精选 Skills。只选部分：

```powershell
& ([scriptblock]::Create((irm https://raw.githubusercontent.com/icewolf-li/nodaoli-agent-kit/main/scripts/install.ps1))) -Skill your-skill,another-skill
```

```bash
curl -fsSL https://raw.githubusercontent.com/icewolf-li/nodaoli-agent-kit/main/scripts/install.sh | bash -s -- --skills your-skill,another-skill
```

加入并推送源仓库后才能通过公网安装。当前已收录用户选择的 `project-memory`，基于 [ArcticZvan/project-memory](https://github.com/ArcticZvan/project-memory) 改为 `.memory/` 记忆目录，保留上游 MIT 许可证与来源记录，适用于本仓库的 Codex / Claude Code 入口。

首次默认会安装它。已安装过且之前没有选择 Skills 的项目，需要显式传 `-Update -Skill project-memory` 或 `--update --skills project-memory`（若已有其他 Skill，这里应传完整列表）。Skill 会在会话开始读概览与近期日志，在有意义的工作完成后追加日记，并追踪被替代或错误的旧结论；细节见 [来源与适配说明](docs/third-party/project-memory.md)。

## 更新与项目定制

在项目里重复运行安装命令即可更新。也可显式使用 `-Update` / `--update`，要求项目已安装：

```powershell
& ([scriptblock]::Create((irm https://raw.githubusercontent.com/icewolf-li/nodaoli-agent-kit/main/scripts/install.ps1))) -Update
```

```bash
curl -fsSL https://raw.githubusercontent.com/icewolf-li/nodaoli-agent-kit/main/scripts/install.sh | bash -s -- --update
```

- 更新默认沿用 `.agent/kit.json` 的 repo、ref、agent、skill 和 stack 选择，**不会自动加入新 Skill**。
- 如果旧项目的安装记录仍指向旧仓库地址，更新时额外传 `-Repo icewolf-li/nodaoli-agent-kit` / `--repo icewolf-li/nodaoli-agent-kit`，这次成功安装后会记录新来源。
- 改选择时显式传参，例如 `-Update -Skill new-skill`；此参数是完整选择列表，并非追加列表。
- AGENTS.md / CLAUDE.md 只替换 `<!-- agent-kit:start -->` 到 `<!-- agent-kit:end -->`；外部内容按原字节保留。缺失半边标记或标记重复时停止。
- 不覆盖已有 `.memory/` 记忆、`.agent/project.md`、无关规则或自定义 Skills。
- 若旧项目使用了其他记忆目录，将已有记忆合并到 `.memory/` 后再继续使用；安装器不自动移动旧目录。
- 未受管的同名规则或 Skill 文件发生冲突时停止，不擅自接管。
- 已受管文件被本地修改且与源仓库不同，默认停止。先回源仓库合并；确定要覆盖时传 `-Force` / `--force`，旧文件会备份。
- 所有将被覆盖的文件都会先备份到 `.agent/backups/<UTC时间>/`。备份保留，不自动清理。
- 仓库删除的文件、取消选择的 Skill 或旧 Stack **不会自动删除**，安装器列出遗留受管文件；确认后手动删除。若取消了 Stack，入口不再引用旧 stack.md。
- 不承诺跨文件更新是事务；写入期间若遇到磁盘/权限错误，保留已有备份，修复错误后重跑。

恢复备份：选定 `.agent/backups/` 的某次目录，把其中需要的文件按相对路径复制回项目。涉及变更选择时一并恢复该次 `.agent/kit.json`。先检查 Git diff，避免覆盖后续工作。

添加技术栈规则时在 `stacks/` 新建 Markdown，再用 `-Stack name` / `--stack name`。取消 Stack 使用 `-Stack ''` / `--stack ''`。通用规则改 `rules/`；项目专属说明写 `.agent/project.md` 或入口管理区块外。

可以用 `-Ref <tag或commit>` / `--ref <tag或commit>` 固定版本，同时将入口 URL 中 `main` 换成相同 ref。入口、共享安装器与数据应来自同一个公开来源；如果下载过程中 main 变化，安装器会停止并要求重试。`kit.json` 的 archive_sha256 是下载内容摘要，用于追踪内容，并非来源签名。

## 本地验证

在源仓库运行（不会读取本机已安装的 Skills）：

```powershell
python scripts/test_install.py
```

开发时不走网络：

```powershell
.\scripts\install.ps1 -SourcePath . -ProjectPath '.tmp\example-project' -NoSkills
```

```bash
bash scripts/install.sh --source "$PWD" --project "$PWD/.tmp/example-project" --no-skills
```

## 维护与发布更新

公开仓库是 [icewolf-li/nodaoli-agent-kit](https://github.com/icewolf-li/nodaoli-agent-kit)。修改源规则、Skills 或脚本后，审查变更，再提交推送到 `main`；公网命令读取的是已经推送的版本。

```powershell
git add .
git commit -m "Update personal agent kit"
git push -u origin main
```

当前 `origin` 已指向该仓库。换地址时使用 `git remote set-url origin <实际地址>`。源仓库每次更新后提交推送，业务项目再运行公网更新命令。
