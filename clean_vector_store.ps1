# 清理旧的向量索引文件
# 用于重新构建索引前清理旧数据

Write-Host "正在清理旧的向量索引文件..." -ForegroundColor Yellow

$indexFile = "vector_store\faiss.index"
$chunksFile = "vector_store\chunks.pkl"

if (Test-Path $indexFile) {
    Remove-Item $indexFile -Force
    Write-Host "✓ 已删除: $indexFile" -ForegroundColor Green
} else {
    Write-Host "⚠ 文件不存在: $indexFile" -ForegroundColor Gray
}

if (Test-Path $chunksFile) {
    Remove-Item $chunksFile -Force
    Write-Host "✓ 已删除: $chunksFile" -ForegroundColor Green
} else {
    Write-Host "⚠ 文件不存在: $chunksFile" -ForegroundColor Gray
}

Write-Host "`n清理完成！现在可以运行: python app/db/init_vector_store.py" -ForegroundColor Cyan

