#!/usr/bin/env python3
#数据库初始化/更新脚本
#为Goods表添加original_price字段

import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), 'campus_trading.db')

if not os.path.exists(db_path):
    print(f"❌ 数据库文件不存在: {db_path}")
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# 检查original_price字段是否已存在
cursor.execute("PRAGMA table_info(goods)")
columns = [column[1] for column in cursor.fetchall()]

if 'original_price' not in columns:
    print("📦 添加 original_price 字段...")
    cursor.execute("ALTER TABLE goods ADD COLUMN original_price FLOAT")
    conn.commit()
    print("✅ 字段添加成功！")
else:
    print("✅ original_price 字段已存在")

conn.close()
print("✨ 数据库更新完成！")