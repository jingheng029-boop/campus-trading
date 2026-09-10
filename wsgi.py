# -*- coding: utf-8 -*-
"""
PythonAnywhere 部署配置文件
"""

import os
import sys

# 添加项目路径
path = os.path.dirname(os.path.abspath(__file__))
if path not in sys.path:
    sys.path.insert(0, path)

# 切换到项目目录
os.chdir(path)

# 导入并运行Flask应用
from app import app as application

# 让 PythonAnywhere 能找到应用的 router
# 如果你有特定的 router，设置如下：
# router = application