# 精选 Skills

这里先留空。只把你确定要复用的 Skill 放进来，不自动扫描或导入电脑上的已安装 Skills。

每个 Skill 使用独立目录，目录名建议为小写英文加连字符：

```text
skills/
  your-skill/
    SKILL.md
    scripts/       # 有就一起复制
    references/    # 有就一起复制
    assets/        # 有就一起复制
```

操作方法：

1. 自己选择需要的 Skill，把整个目录复制到 `skills/<name>/`；不要只复制 SKILL.md。
2. 确认 SKILL.md 开头有 YAML frontmatter 的 `name` 和 `description`，说明何时使用以及怎么执行。
3. 将私有绝对路径改成可配置路径或相对资源路径；检查许可证与引用来源。插件提供的 Skill 可能还需要对应插件的工具，复制文件不会安装插件。
4. 不放 `.git/`、缓存、`.env`、凭据、个人数据；安装器会拒绝符号链接和重解析点，请放真实资源文件。
5. 提交并推送到源仓库后，新项目安装时才能从公网获取它。

默认首次安装源仓库中所有包含 SKILL.md 的一级子目录；用 `-Skill name1,name2` 或 `--skills name1,name2` 限定选择，`-NoSkills` 或 `--no-skills` 只安装规则。

升级默认沿用项目上次选择，不自动添加后来新增的 Skills。修改选择时显式传参；旧副本不自动删除，需要你确认后手动移除。

项目中的 Skill 副本修改后，先回源仓库合并，再更新项目。安装器会对本地已修改的受管文件报冲突；显式覆盖时会备份。
