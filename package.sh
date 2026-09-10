#!/bin/bash
#校园二手交易平台 - 一键打包脚本（不含 venv）

echo "📦 开始打包项目..."

# 切换到项目目录
cd "$(dirname "$0")"

# 删除旧的打包文件
rm -f campus_trading_deploy.zip

# 创建临时目录
mkdir -p temp_deploy

# 复制需要部署的文件（排除 venv）
cp app.py temp_deploy/
cp requirements.txt temp_deploy/
cp -r templates temp_deploy/
cp -r static temp_deploy/
mkdir -p temp_deploy/static/uploads
mkdir -p temp_deploy/static/chat

# 打包
cd temp_deploy
zip -r ../campus_trading_deploy.zip .
cd ..

# 清理临时目录
rm -rf temp_deploy

echo "✅ 打包完成！"
echo "📁 生成文件: campus_trading_deploy.zip ($(ls -lh campus_trading_deploy.zip | awk '{print $5}'))"
echo ""
echo "下一步："
echo "1. 登录 PythonAnywhere"
echo "2. 上传 campus_trading_deploy.zip"
echo "3. 解压后运行 deploy.sh"