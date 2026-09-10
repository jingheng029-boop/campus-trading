#!/bin/bash
#校园二手交易平台 - PythonAnywhere 一键部署脚本
#运行方式: bash deploy.sh

echo "🚀 开始部署到 PythonAnywhere..."

# 获取当前目录
DEPLOY_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DEPLOY_DIR"

# 替换为你的 PythonAnywhere 用户名
YOUR_USERNAME="your_username"

echo "📋 请确认部署信息:"
echo "   项目目录: $DEPLOY_DIR"
echo "   用户名: $YOUR_USERNAME"
echo ""

# 检查是否安装了依赖
if [ ! -d "venv" ]; then
    echo "📦 创建虚拟环境..."
    python3.11 -m venv venv
fi

echo "📥 安装依赖..."
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo ""
echo "✅ 依赖安装完成！"
echo ""
echo "📝 接下来请在 PythonAnywhere Web 界面配置："
echo ""
echo "1. 点击 Web 标签"
echo "2. 点击 Add a new web app"
echo "3. 选择 Manual configuration"
echo "4. 选择 Python 3.11"
echo ""
echo "5. 配置 Code 部分："
echo "   - Source code: $DEPLOY_DIR"
echo "   - Working directory: $DEPLOY_DIR"
echo ""
echo "6. 编辑 WSGI 文件，添加："
echo "
import os
import sys

path = '$DEPLOY_DIR'
if path not in sys.path:
    sys.path.insert(0, path)

os.chdir(path)

activate_this = os.path.join(path, 'venv', 'bin', 'activate_this.py')
with open(activate_this) as f:
    exec(f.read(), dict(__file__=activate_this))

from app import app as application
"
echo ""
echo "7. 配置静态文件："
echo "   URL: /static/ -> $DEPLOY_DIR/static"
echo ""
echo "8. 点击 Reload 按钮"
echo ""
echo "🎉 部署完成！访问 https://$YOUR_USERNAME.pythonanywhere.com"