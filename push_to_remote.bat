@echo off
echo ========================================
echo 推送代码到远程仓库
echo ========================================
echo.

echo [1/3] 推送 v5.3.0 分支...
git push origin v5.3.0
if %errorlevel% neq 0 (
    echo 警告: v5.3.0 推送失败，请检查权限
) else (
    echo ✓ v5.3.0 推送成功
)
echo.

echo [2/3] 切换到 main 分支并推送...
git checkout main
git push origin main
if %errorlevel% neq 0 (
    echo 警告: main 推送失败，请检查权限
) else (
    echo ✓ main 推送成功
)
echo.

echo [3/3] 切换到 v6.0.0 分支并推送...
git checkout v6.0.0
git push -u origin v6.0.0
if %errorlevel% neq 0 (
    echo 警告: v6.0.0 推送失败，请检查权限
) else (
    echo ✓ v6.0.0 推送成功
)
echo.

echo ========================================
echo 推送完成！
echo ========================================
pause

