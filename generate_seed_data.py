#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成 V1 版本的种子数据 SQL 文件
"""
import json
import random
from datetime import datetime, timedelta

# 设置随机种子以保证可重现性（可选）
random.seed(42)

# 数据池定义
product_names = ['运动鞋', '小白鞋', '高跟鞋', '凉鞋', '短靴', '长靴', '乐福鞋', '玛丽珍鞋', 
                 '切尔西靴', '马丁靴', '帆布鞋', '板鞋', '老爹鞋', '跑鞋', '休闲鞋', '单鞋',
                 '豆豆鞋', '芭蕾舞鞋', '牛津鞋', '德比鞋']
colors = ['黑色', '白色', '米色', '棕色', '灰色', '红色', '蓝色', '粉色', '卡其色', '驼色']
materials = ['真皮', 'PU', '帆布', '网面', '麂皮', '合成革', '羊皮', '牛皮']
scenes = ['通勤', '休闲', '运动', '约会', '逛街', '旅行', '商务']
seasons = ['春季', '夏季', '秋季', '冬季', '春秋', '四季']
tags_pool = ['百搭', '舒适', '时尚', '增高', '通勤', '轻便', '软底', '防滑', '透气', '经典', 
             '复古', '英伦', '学院风', '韩版', '日系', '欧美', '简约', '优雅', '甜美', '帅气']

guide_surnames = ['张', '李', '王', '刘', '陈', '杨', '赵', '黄', '周', '吴', '徐', '孙', 
                  '马', '朱', '胡', '林', '郭', '何', '高', '罗']
guide_given_names = ['丽', '敏', '静', '芳', '红', '艳', '娟', '娜', '霞', '玲', '雪', '梅',
                     '兰', '菊', '竹', '月', '星', '云', '雨', '晴']
shop_names = ['百丽专柜', '天美意专柜', '他她专柜', '思加图专柜', '百思图专柜', '森达专柜',
              '百丽旗舰店', '天美意旗舰店', '他她旗舰店', '思加图旗舰店']
levels = ['junior', 'senior', 'expert']

# 生成商品数据
products = []
skus = []
for i in range(1, 101):
    sku = f'8WZ{i:02d}CM{i%10}'
    skus.append(sku)
    
    name_parts = [
        random.choice(product_names),
        random.choice(['女', '男', '']),
        random.choice(['2024', '2023', '2022']),
        random.choice(['新款', '经典款', '限量款']),
        random.choice(['时尚', '经典', '简约', '复古', '英伦', '韩版'])
    ]
    name = ''.join([p for p in name_parts if p])
    
    price = round(random.uniform(200, 2000), 2)
    
    # 生成标签（2-5个）
    num_tags = random.randint(2, 5)
    tags = random.sample(tags_pool, num_tags)
    
    # 生成属性
    attributes = {
        'color': random.choice(colors),
        'material': random.choice(materials),
        'scene': random.choice(scenes),
        'season': random.choice(seasons)
    }
    
    products.append((sku, name, price, json.dumps(tags, ensure_ascii=False), 
                     json.dumps(attributes, ensure_ascii=False)))

# 生成导购数据
guides = []
guide_ids = []
for i in range(1, 51):
    guide_id = f'guide_{i:03d}'
    guide_ids.append(guide_id)
    
    name = random.choice(guide_surnames) + random.choice(guide_given_names)
    shop_name = random.choice(shop_names)
    level = random.choice(levels)
    
    guides.append((guide_id, name, shop_name, level))

# 生成用户ID
user_ids = [f'user_{i:03d}' for i in range(1, 101)]

# 生成用户行为日志（符合分布要求）
behaviors = []
event_types_dist = ['browse'] * 70 + ['enter_buy_page'] * 5 + ['click_size_chart'] * 10 + ['favorite'] * 10 + ['share'] * 5

base_time = datetime.now() - timedelta(days=30)

for i in range(1000):
    user_id = random.choice(user_ids)
    guide_id = random.choice(guide_ids)
    sku = random.choice(skus)
    event_type = random.choice(event_types_dist)
    
    # 停留时长：browse 5-60秒，enter_buy_page 30-120秒，其他 3-20秒
    if event_type == 'browse':
        stay_seconds = random.randint(5, 60)
    elif event_type == 'enter_buy_page':
        stay_seconds = random.randint(30, 120)
    else:
        stay_seconds = random.randint(3, 20)
    
    # 时间分布：最近30天
    days_ago = random.randint(0, 30)
    hours_ago = random.randint(0, 23)
    minutes_ago = random.randint(0, 59)
    occurred_at = base_time + timedelta(days=days_ago, hours=hours_ago, minutes=minutes_ago)
    
    behaviors.append((user_id, guide_id, sku, event_type, stay_seconds, 
                     occurred_at.strftime('%Y-%m-%d %H:%M:%S')))

# 生成 SQL 文件
sql_content = """-- ============================================
-- AI Smart Guide Service V1 - Seed Data
-- ============================================
-- 生成时间: {gen_time}
-- 商品数量: {product_count}
-- 导购数量: {guide_count}
-- 用户行为日志数量: {behavior_count}
-- ============================================

""".format(
    gen_time=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    product_count=len(products),
    guide_count=len(guides),
    behavior_count=len(behaviors)
)

# 插入商品数据
sql_content += "-- 1. 插入商品数据 (products)\n"
sql_content += "INSERT INTO products (sku, name, price, tags, attributes, created_at, updated_at) VALUES\n"
product_values = []
for sku, name, price, tags, attrs in products:
    created_at = (datetime.now() - timedelta(days=random.randint(1, 365))).strftime('%Y-%m-%d %H:%M:%S')
    # 转义单引号
    name_escaped = name.replace("'", "''")
    product_values.append(f"('{sku}', '{name_escaped}', {price}, '{tags}', '{attrs}', '{created_at}', '{created_at}')")
sql_content += ',\n'.join(product_values) + ";\n\n"

# 插入导购数据
sql_content += "-- 2. 插入导购数据 (guides)\n"
sql_content += "INSERT INTO guides (guide_id, name, shop_name, level, created_at) VALUES\n"
guide_values = []
for guide_id, name, shop_name, level in guides:
    created_at = (datetime.now() - timedelta(days=random.randint(30, 365))).strftime('%Y-%m-%d %H:%M:%S')
    # 转义单引号
    name_escaped = name.replace("'", "''")
    shop_escaped = shop_name.replace("'", "''")
    guide_values.append(f"('{guide_id}', '{name_escaped}', '{shop_escaped}', '{level}', '{created_at}')")
sql_content += ',\n'.join(guide_values) + ";\n\n"

# 插入用户行为日志（分批处理，避免单条 SQL 过长）
sql_content += "-- 3. 插入用户行为日志 (user_behavior_logs)\n"
# 每批 200 条，分 5 批插入
batch_size = 200
for batch_idx in range(0, len(behaviors), batch_size):
    batch = behaviors[batch_idx:batch_idx + batch_size]
    sql_content += f"INSERT INTO user_behavior_logs (user_id, guide_id, sku, event_type, stay_seconds, occurred_at) VALUES\n"
    behavior_values = []
    for user_id, guide_id, sku, event_type, stay_seconds, occurred_at in batch:
        behavior_values.append(f"('{user_id}', '{guide_id}', '{sku}', '{event_type}', {stay_seconds}, '{occurred_at}')")
    sql_content += ',\n'.join(behavior_values) + ";\n\n"

# 写入文件
import os
os.makedirs('sql', exist_ok=True)
with open('sql/seed_data.sql', 'w', encoding='utf-8') as f:
    f.write(sql_content)

print(f"✅ 种子数据生成完成！")
print(f"   - 商品: {len(products)} 条")
print(f"   - 导购: {len(guides)} 条")
print(f"   - 用户行为日志: {len(behaviors)} 条")
print(f"   - 文件已保存到: sql/seed_data.sql")
print(f"   - 文件大小: {os.path.getsize('sql/seed_data.sql')} bytes")

