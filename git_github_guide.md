# Git 和 GitHub 常用操作指南

## 基础设置

### 设置 Git 用户信息
```bash
git config --global user.name "你的名字"
git config --global user.email "你的邮箱"
```

### 生成 SSH 密钥
```bash
ssh-keygen -t rsa -b 4096 -C "你的邮箱"
```
然后将生成的公钥（通常在 `~/.ssh/id_rsa.pub`）添加到 GitHub 账户。

## 本地仓库操作

### 初始化仓库
```bash
git init
```

### 检查状态
```bash
git status
```

### 添加文件到暂存区
```bash
# 添加特定文件
git add filename.ext

# 添加所有变更
git add .
```

### 提交更改
```bash
git commit -m "提交信息"
```

### 查看提交历史
```bash
# 基本历史
git log

# 简洁历史
git log --oneline

# 图形化历史
git log --graph --oneline --all
```

### 查看文件差异
```bash
git diff
```

## 分支操作

### 查看分支
```bash
# 查看本地分支
git branch

# 查看所有分支（包括远程）
git branch -a
```

### 创建分支
```bash
git branch 分支名称
```

### 切换分支
```bash
git checkout 分支名称

# 创建并切换分支
git checkout -b 新分支名称
```

### 合并分支
```bash
# 先切换到目标分支
git checkout main

# 然后合并
git merge 源分支名称
```

### 删除分支
```bash
# 删除已合并的分支
git branch -d 分支名称

# 强制删除分支
git branch -D 分支名称
```

## 远程仓库操作

### 克隆仓库
```bash
git clone https://github.com/username/repository.git
```

### 添加远程仓库
```bash
git remote add origin https://github.com/username/repository.git
```

### 查看远程仓库
```bash
git remote -v
```

### 从远程获取更新
```bash
# 获取更新但不合并
git fetch

# 获取特定分支更新
git fetch origin 分支名
```

### 拉取更新并合并
```bash
git pull

# 指定远程和分支
git pull origin main
```

### 推送到远程
```bash
git push

# 首次推送并设置上游
git push -u origin main

# 推送到特定分支
git push origin 分支名
```

### 删除远程分支
```bash
git push origin --delete 分支名
```

## 撤销与恢复

### 撤销工作区修改
```bash
git checkout -- 文件名
```

### 撤销暂存区修改
```bash
git reset HEAD 文件名
```

### 修改最后一次提交
```bash
git commit --amend
```

### 回退到指定提交
```bash
# 保留修改，只撤销提交
git reset --soft 提交ID

# 撤销提交并清除暂存区，保留工作区修改
git reset --mixed 提交ID

# 完全回退，工作区也回退
git reset --hard 提交ID
```

### 撤销已推送的提交（慎用）
```bash
git revert 提交ID
```

## 高级操作

### 临时保存工作
```bash
# 保存当前工作
git stash

# 查看保存的工作
git stash list

# 恢复保存的工作
git stash pop

# 清除所有保存的工作
git stash clear
```

### 变基操作
```bash
git rebase main
```

### 标签管理
```bash
# 创建标签
git tag v1.0.0

# 创建带注释的标签
git tag -a v1.0.0 -m "1.0.0 版本发布"

# 查看标签
git tag

# 推送标签到远程
git push origin v1.0.0

# 推送所有标签
git push origin --tags
```

### 查看文件修改历史
```bash
git blame 文件名
```

## GitHub 特有操作

### Fork 仓库
在 GitHub 页面点击 "Fork" 按钮

### 创建 Pull Request (PR)
1. 从主仓库 Fork 到自己账户
2. 克隆 Fork 的仓库到本地
3. 创建新分支并进行修改
4. 推送分支到 Fork 的仓库
5. 在 GitHub 页面点击 "New pull request"

### 同步 Fork 的仓库
```bash
# 添加上游远程仓库
git remote add upstream https://github.com/original_owner/original_repository.git

# 获取上游更新
git fetch upstream

# 合并上游更新到本地 main 分支
git checkout main
git merge upstream/main
```

### 处理 PR 冲突
1. 从 PR 页面获取更改
2. 本地解决冲突
3. 提交解决结果
4. 推送到 PR 分支

### GitHub Actions 基础
在仓库中创建 `.github/workflows/` 目录和 YAML 文件来定义工作流

### GitHub Pages 发布
在仓库设置中启用 GitHub Pages，选择源分支

## 常用工作流

### 功能分支工作流
1. 从 main 创建功能分支
2. 在功能分支上开发并提交
3. 完成后创建 PR
4. 审查并合并

### GitFlow 工作流
使用 main、develop、feature/、release/、hotfix/ 等分支进行更复杂的版本管理

### GitHub Flow
1. 创建分支
2. 添加提交
3. 开启 PR
4. 讨论和审查
5. 部署测试
6. 合并

## 常见工作场景操作

### 从零开始：克隆远程仓库到空目录
```bash
# 1. 创建并进入一个空目录
mkdir my_project
cd my_project

# 2. 克隆远程仓库
git clone https://github.com/username/repository.git .
# 注意末尾的点，表示克隆到当前目录

# 3. 查看远程分支
git branch -a

# 4. 切换到开发分支（如果有）
git checkout develop
```

### 第一次提交本地项目到 GitHub
```bash
# 1. 在 GitHub 上创建一个新的空仓库，不要初始化

# 2. 在本地项目目录初始化 Git
cd 你的项目目录
git init

# 3. 添加所有文件
git add .

# 4. 提交文件
git commit -m "初始提交"

# 5. 添加远程仓库
git remote add origin https://github.com/username/repository.git

# 6. 推送到远程仓库
git push -u origin main  # 或 master，取决于你的默认分支名
```

### 分支开发工作流
```bash
# 1. 确保本地 main 分支是最新的
git checkout main
git pull

# 2. 创建并切换到功能分支
git checkout -b feature/new-feature

# 3. 进行开发并多次提交
git add .
git commit -m "实现了 X 功能"
# ... 继续开发 ...
git add .
git commit -m "优化了 X 功能"

# 4. 将功能分支推送到远程
git push -u origin feature/new-feature

# 5. 在 GitHub 上创建 Pull Request

# 6. 审查通过后，在 GitHub 上合并

# 7. 拉取更新后的主分支
git checkout main
git pull

# 8. 删除本地功能分支
git branch -d feature/new-feature

# 9. 删除远程功能分支（可选）
git push origin --delete feature/new-feature
```

### 修复线上 bug 的紧急分支
```bash
# 1. 确保 main 分支是最新的
git checkout main
git pull

# 2. 创建修复分支
git checkout -b hotfix/bug-fix

# 3. 修复 bug 并提交
git add .
git commit -m "修复了 XX bug"

# 4. 推送修复分支
git push -u origin hotfix/bug-fix

# 5. 创建 PR 并快速合并

# 6. 更新本地 main 并删除修复分支
git checkout main
git pull
git branch -d hotfix/bug-fix
```

### 放弃本地修改并重置到远程版本
```bash
# 完全重置（谨慎使用，会丢失所有未提交的更改）
git fetch origin
git reset --hard origin/main
```

### 在不同分支间切换但保留未完成的修改
```bash
# 1. 保存当前工作状态
git stash

# 2. 切换分支
git checkout other-branch

# 3. 做一些其他工作...

# 4. 返回原分支
git checkout previous-branch

# 5. 恢复之前的工作状态
git stash pop
```

### 解决合并冲突的实际操作
```bash
# 当 git pull 或 git merge 出现冲突时

# 1. 查看冲突文件
git status

# 2. 编辑冲突文件，查找并解决所有冲突标记
# <<<<<<<, =======, >>>>>>> 标记

# 3. 解决后添加文件
git add 已解决冲突的文件

# 4. 继续合并过程
git merge --continue
# 或
git commit -m "解决合并冲突"
```

### 协作处理 Pull Request
```bash
# 1. 从 PR 创建者的分支拉取更改到本地
git fetch origin pull/ID/head:pr-branch-name
git checkout pr-branch-name

# 2. 审查代码

# 3. 如需要修改，直接修改并提交
git add .
git commit -m "改进 PR 中的 XX"

# 4. 推送回 PR 创建者的分支（如果有权限）
git push origin pr-branch-name
```

### 查看特定文件的历史修改
```bash
# 查看文件的所有更改历史
git log --follow -p -- 文件路径

# 查看谁修改了文件的每一行
git blame 文件路径
```

## 常见问题解决

### 解决合并冲突
当 Git 提示冲突时，编辑冲突文件，解决冲突标记（`<<<<<<<`，`=======`，`>>>>>>>`），然后提交

### .gitignore 设置
创建 .gitignore 文件，列出不需要追踪的文件和目录

### 大文件处理
使用 Git LFS (Large File Storage) 处理大文件 