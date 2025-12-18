# Git 提交信息中文乱码修复指南

## 问题描述

在 Windows PowerShell 中使用 Git 提交包含中文的提交信息时，可能会出现乱码，例如：
```
feat(v5.2.0): RAG SKU楠岃瘉鍔熻兘 - 涓ユ牸杩囨护璺⊿KU姹℃煋...
```

## 问题原因

1. PowerShell 默认编码不是 UTF-8
2. Git 提交信息在存储时使用了错误的编码
3. 即使后续配置了 UTF-8，历史提交信息已经以错误编码存储

## 已配置的修复（未来提交）

已执行以下 Git 配置，确保未来提交使用 UTF-8：

```bash
git config --global i18n.commitencoding utf-8
git config --global i18n.logoutputencoding utf-8
git config --global core.quotepath false
```

## 修复历史提交信息（可选）

### 方案 1：使用交互式 Rebase（推荐，但需要强制推送）

```bash
# 1. 切换到 main 分支
git checkout main

# 2. 开始交互式 rebase（修改最近 2 个提交）
git rebase -i HEAD~2

# 3. 在编辑器中，将要修改的提交前的 'pick' 改为 'reword'
# 例如：
# reword b1f94f1 feat(v5.2.0): RAG SKU验证功能...
# reword 25fa97b merge: 合并v5.2.0分支...

# 4. 保存并关闭编辑器，Git 会逐个提示你修改提交信息
# 输入正确的提交信息（使用英文或确保 UTF-8 编码）

# 5. 强制推送到远程（⚠️ 警告：会改写历史）
git push belle_ai main --force
```

### 方案 2：使用英文提交信息（最简单）

未来所有提交信息使用英文，避免编码问题：

```bash
git commit -m "feat(v5.2.0): RAG SKU validation - strict filtering to prevent cross-SKU contamination"
```

### 方案 3：使用 Git Notes（不修改历史）

```bash
# 添加注释说明正确的提交信息
git notes add -m "正确的提交信息：feat(v5.2.0): RAG SKU验证功能 - 严格过滤跨SKU污染，确保产品数据是唯一事实来源" b1f94f1
```

## 预防措施

### 1. 使用英文提交信息（推荐）

遵循 [Conventional Commits](https://www.conventionalcommits.org/) 规范：

```bash
feat(v5.2.0): RAG SKU validation
fix(v5.1.0): Intent engine conservative rules
docs: Add git encoding fix guide
```

### 2. 如果必须使用中文

确保 PowerShell 使用 UTF-8：

```powershell
# 在 PowerShell 中设置编码
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:LANG = "zh_CN.UTF-8"

# 然后提交
git commit -m "feat(v5.2.0): RAG SKU验证功能"
```

### 3. 使用 Git GUI 工具

使用 GitKraken、SourceTree 等 GUI 工具，它们通常能正确处理中文编码。

## 当前状态

- ✅ Git 全局配置已设置为 UTF-8
- ⚠️ 历史提交信息（v5.2.0）仍显示乱码
- ✅ 未来提交将使用正确的编码

## 建议

**对于已推送的提交：**
- 如果只有你一个人在使用这个仓库，可以使用方案 1 修复历史
- 如果有其他协作者，建议使用方案 3（Git Notes）或保持现状
- 未来使用英文提交信息，避免编码问题

**对于新提交：**
- 优先使用英文提交信息
- 如需使用中文，确保 PowerShell 编码设置为 UTF-8

