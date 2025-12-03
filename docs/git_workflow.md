# Git 工作流程说明

## 分支策略

### 分支结构
- **main**: 主分支，包含所有稳定版本的代码
- **develop/v2.0.x**: 开发分支，用于特定版本的开发工作

## 工作流程

### 1. 创建开发分支

```bash
# 从 main 分支创建新的开发分支
git checkout main
git pull belle_ai main  # 确保 main 是最新的
git checkout -b develop/v2.0.2
```

### 2. 在开发分支上工作

```bash
# 确认当前在开发分支
git branch  # 应该显示 * develop/v2.0.2

# 进行开发工作...
# 修改代码、添加功能、修复bug等

# 提交更改
git add .
git commit -m "feat: 添加新功能"
# 或
git commit -m "fix: 修复bug"
```

### 3. 开发完成后合并到 main

```bash
# 1. 确保开发分支的代码已经提交
git status  # 应该显示 "working tree clean"

# 2. 切换到 main 分支
git checkout main

# 3. 拉取最新的 main 代码（如果有其他人也在开发）
git pull belle_ai main

# 4. 合并开发分支到 main
git merge develop/v2.0.2

# 5. 如果有冲突，解决冲突后：
git add .
git commit -m "merge: 合并 develop/v2.0.2 到 main"

# 6. 推送到远程
git push belle_ai main

# 7. 可选：删除本地开发分支（如果不再需要）
git branch -d develop/v2.0.2
```

## 版本管理

### 版本号规则
- 主版本号：重大架构变更（v1.0.0 → v2.0.0）
- 次版本号：新功能添加（v2.0.1 → v2.0.2）
- 修订版本号：bug修复（v2.0.2 → v2.0.3）

### 版本号位置
- `app/core/config.py` 中的 `app_version` 字段

## 提交信息规范

### 提交类型
- `feat`: 新功能
- `fix`: 修复bug
- `docs`: 文档更新
- `style`: 代码格式调整（不影响功能）
- `refactor`: 代码重构
- `test`: 测试相关
- `chore`: 构建/工具链相关

### 示例
```
feat: 添加用户行为分析功能
fix: 修复向量搜索精确度问题
docs: 更新API文档
chore: 升级依赖包版本
```

## 当前分支状态

- **main**: v2.0.1（稳定版本）
- **develop/v2.0.2**: v2.0.2（开发中）

## 注意事项

1. **不要直接在 main 分支上开发**
   - 所有开发工作都在开发分支进行
   - main 分支只接受合并

2. **定期同步 main 分支**
   - 开发过程中，定期从 main 合并最新代码到开发分支
   ```bash
   git checkout develop/v2.0.2
   git merge main  # 将 main 的更新合并到开发分支
   ```

3. **提交前检查**
   - 确保代码可以正常运行
   - 确保没有敏感信息（如 API Key）
   - 确保 `.env` 文件在 `.gitignore` 中

4. **版本标签（可选）**
   ```bash
   # 在 main 分支上打标签
   git checkout main
   git tag v2.0.2
   git push belle_ai v2.0.2
   ```

