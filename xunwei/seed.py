from datetime import datetime, timedelta

def seed_data(db, extra_only=False):
    """写入示例餐厅、推荐菜与点评。"""
    now = datetime.now()
    restaurants = [
        {
            "name": "蜀香居", "category": "川菜", "address": "锦江区春熙路 88 号",
            "phone": "028-8888 6666", "avg_price": 68,
            "description": "地道川菜老店，麻辣鲜香，回锅肉一绝，每日现炒现卖。",
            "rating": 4.5, "taste": 4.6, "env": 4.3, "service": 4.4,
            "emoji": "🌶️", "gradient": "linear-gradient(135deg, #ff9a5a, #e6533f)",
            "dishes": [("回锅肉", 38, 328), ("水煮鱼", 68, 276), ("毛血旺", 58, 201), ("麻婆豆腐", 28, 154)],
            "reviews": [
                ("张三", 5, 5, 4, 5, "麻辣鲜香，回锅肉肥而不腻，服务也热情，下次还来。", 2),
                ("李四", 5, 5, 4, 4, "水煮鱼份量足，鱼肉嫩滑，就是排队有点久。", 5),
                ("王五", 4, 4, 4, 4, "味道不错，辣度偏重，能吃辣的朋友会很喜欢。", 9),
                ("赵六", 5, 5, 5, 5, "每次来都要排队，值得！毛血旺料很足。", 13),
                ("孙七", 3, 3, 3, 3, "口味偏重，环境一般，性价比中规中矩。", 18),
                ("周八", 4, 4, 3, 4, "麻婆豆腐下饭神器，米饭还能免费续。", 24),
            ],
        },
        {
            "name": "粤味轩", "category": "粤菜", "address": "天河区珠江新城华夏路 12 号",
            "phone": "020-6666 8888", "avg_price": 120,
            "description": "精致粤式酒楼，讲究火候与食材本味，广受街坊好评。",
            "rating": 4.7, "taste": 4.7, "env": 4.8, "service": 4.6,
            "emoji": "🍤", "gradient": "linear-gradient(135deg, #43c6ac, #2a7faa)",
            "dishes": [("白切鸡", 78, 245), ("虾饺", 42, 189), ("煲仔饭", 48, 143), ("老火靓汤", 58, 97)],
            "reviews": [
                ("陈姐", 5, 5, 5, 5, "白切鸡皮爽肉滑，蘸料绝了，环境也很雅致。", 1),
                ("刘先生", 5, 5, 5, 4, "虾饺皮薄馅足，虾肉弹牙，早茶首选。", 6),
                ("林小姐", 4, 4, 5, 4, "煲仔饭锅巴香脆，就是上菜稍慢。", 11),
                ("黄叔", 5, 5, 4, 5, "老火靓汤熬得够火候，喝得出真材实料。", 16),
                ("郑女士", 4, 4, 4, 5, "服务周到，环境舒服，适合家庭聚餐。", 21),
            ],
        },
        {
            "name": "和风居酒屋", "category": "日料", "address": "福田区中心城一楼 08 铺",
            "phone": "0755-3333 2222", "avg_price": 150,
            "description": "深夜食堂般的居酒屋，刺身新鲜，鳗鱼饭香糯，氛围感十足。",
            "rating": 4.6, "taste": 4.6, "env": 4.7, "service": 4.5,
            "emoji": "🍣", "gradient": "linear-gradient(135deg, #c471ed, #6a4fb5)",
            "dishes": [("三文鱼刺身", 88, 213), ("鳗鱼饭", 68, 178), ("天妇罗", 58, 122), ("味噌汤", 18, 66)],
            "reviews": [
                ("小野", 5, 5, 5, 5, "刺身非常新鲜，入口即化，师傅刀工一流。", 3),
                ("阿杰", 5, 5, 5, 4, "鳗鱼饭酱汁香甜，米饭粒粒分明，强烈推荐。", 7),
                ("Momo", 4, 4, 5, 5, "环境很有日式氛围，天妇罗酥脆不油腻。", 12),
                ("大山", 5, 5, 4, 4, "深夜来一杯清酒配烤串，太治愈了。", 19),
                ("小雯", 4, 4, 4, 4, "味噌汤暖暖的，就是价格略高。", 26),
            ],
        },
        {
            "name": "La Vie 法餐厅", "category": "西餐", "address": "朝阳区三里屯路 33 号",
            "phone": "010-9999 0000", "avg_price": 280,
            "description": "浪漫法式餐厅，主厨精选鹅肝与惠灵顿牛排，适合约会。",
            "rating": 4.3, "taste": 4.2, "env": 4.8, "service": 4.3,
            "emoji": "🥂", "gradient": "linear-gradient(135deg, #f6d365, #b8860b)",
            "dishes": [("惠灵顿牛排", 238, 156), ("香煎鹅肝", 168, 132), ("法式蜗牛", 98, 88), ("焦糖布丁", 45, 71)],
            "reviews": [
                ("Anna", 5, 5, 5, 4, "环境浪漫，惠灵顿牛排火候刚刚好，仪式感满满。", 4),
                ("Kevin", 4, 4, 5, 4, "鹅肝入口绵密，摆盘精美，适合纪念日。", 8),
                ("Lily", 4, 4, 5, 4, "法式蜗牛味道正宗，服务稍显生硬。", 14),
                ("Tom", 3, 3, 4, 3, "价格偏高，味道中规中矩，胜在环境。", 22),
                ("Sophie", 5, 4, 5, 5, "焦糖布丁惊艳，服务生推荐得很到位。", 28),
            ],
        },
        {
            "name": "潮汕牛肉火锅", "category": "火锅", "address": "海珠区江南西路 45 号",
            "phone": "020-7777 6666", "avg_price": 95,
            "description": "现切现涮的潮汕牛肉，手打牛肉丸弹牙，汤底清甜。",
            "rating": 4.4, "taste": 4.5, "env": 4.2, "service": 4.3,
            "emoji": "🥩", "gradient": "linear-gradient(135deg, #e8643f, #8e2f1f)",
            "dishes": [("吊龙", 58, 234), ("手打牛肉丸", 32, 198), ("胸口朥", 48, 121), ("粿条", 15, 84)],
            "reviews": [
                ("潮叔", 5, 5, 4, 5, "牛肉丸弹牙爆汁，吊龙十秒即熟，鲜到掉眉毛。", 2),
                ("小林", 4, 4, 4, 4, "汤底清甜，胸口朥脆爽，值得专程来吃。", 6),
                ("阿豪", 5, 5, 4, 4, "现切牛肉就是不一样，粿条泡汤一绝。", 10),
                ("小美", 4, 4, 3, 4, "味道好，就是饭点太挤，环境一般。", 17),
                ("老陈", 4, 4, 4, 4, "性价比高，牛骨汤底可以免费加。", 25),
            ],
        },
        {
            "name": "江南小馆", "category": "江浙菜", "address": "西湖区湖滨路 6 号",
            "phone": "0571-5555 4444", "avg_price": 75,
            "description": "清新雅致的江浙本帮菜，龙井虾仁与东坡肉是招牌。",
            "rating": 4.2, "taste": 4.3, "env": 4.4, "service": 4.0,
            "emoji": "🦐", "gradient": "linear-gradient(135deg, #56c596, #2a9d8f)",
            "dishes": [("龙井虾仁", 98, 176), ("东坡肉", 58, 142), ("西湖醋鱼", 88, 104), ("小笼包", 32, 91)],
            "reviews": [
                ("苏姨", 4, 4, 4, 4, "龙井虾仁清淡鲜香，很有江南风味。", 3),
                ("小江", 5, 5, 4, 4, "东坡肉入口即化，甜而不腻，配米饭绝了。", 7),
                ("江南客", 4, 4, 5, 4, "环境清雅，小笼包汤汁饱满，就是上菜慢。", 12),
                ("小周", 3, 3, 4, 3, "西湖醋鱼偏甜，服务一般。", 18),
                ("阿姨", 4, 4, 4, 3, "口味清淡健康，适合带长辈来。", 23),
            ],
        },
        {
            "name": "巷子口烤肉", "category": "烧烤", "address": "渝中区解放碑步行街 21 号",
            "phone": "023-1111 2222", "avg_price": 65,
            "description": "烟火气十足的市井烧烤，现点现烤，深夜撸串好去处。",
            "rating": 4.0, "taste": 4.2, "env": 3.8, "service": 3.9,
            "emoji": "🍢", "gradient": "linear-gradient(135deg, #ff9966, #ff5e62)",
            "dishes": [("羊肉串", 38, 167), ("烤五花肉", 28, 143), ("烤茄子", 18, 96), ("锡纸金针菇", 16, 78)],
            "reviews": [
                ("老王", 4, 5, 3, 4, "羊肉串肥瘦相间，烤得滋滋冒油，香！", 1),
                ("烧烤迷", 4, 4, 3, 3, "五花肉焦香，环境是路边摊风格，有氛围。", 5),
                ("小张", 5, 5, 3, 4, "烤茄子入味，深夜来几串配啤酒太爽了。", 9),
                ("路人甲", 3, 3, 3, 3, "味道尚可，环境比较简陋，服务一般。", 15),
                ("夜宵党", 4, 4, 3, 4, "锡纸金针菇很嫩，性价比高。", 22),
            ],
        },
        {
            "name": "甜心烘焙", "category": "甜品", "address": "鼓楼区中山路 99 号",
            "phone": "025-8888 9999", "avg_price": 45,
            "description": "治愈系甜品店，舒芙蕾现做现卖，提拉米苏是招牌。",
            "rating": 4.8, "taste": 4.9, "env": 4.7, "service": 4.8,
            "emoji": "🍰", "gradient": "linear-gradient(135deg, #fbc2eb, #f78fb3)",
            "dishes": [("舒芙蕾", 38, 289), ("提拉米苏", 32, 246), ("芒果千层", 36, 178), ("手冲咖啡", 28, 112)],
            "reviews": [
                ("甜甜", 5, 5, 5, 5, "舒芙蕾松软到不像话，入口即化，幸福感爆棚！", 1),
                ("小鹿", 5, 5, 5, 5, "提拉米苏微苦回甘，用料很足，会回购。", 4),
                ("Amy", 5, 5, 5, 5, "芒果千层果肉超多，环境粉粉的超适合拍照。", 8),
                ("CC", 4, 4, 5, 5, "手冲咖啡香气足，服务小姐姐很温柔。", 13),
                ("小朱", 5, 5, 4, 5, "甜品控的天堂，每一款都不踩雷。", 20),
            ],
        },
    ]

    extra_restaurants = [
        {
            'name': '晨光咖啡馆', 'category': '咖啡', 'address': '成都市武侯区玉林西路 18 号',
            'phone': '028-5555 0101', 'avg_price': 38,
            'description': '虚构样本店铺。街角咖啡馆，提供手冲咖啡和轻食，适合午后小坐。',
            'emoji': '☕', 'gradient': 'linear-gradient(135deg, #c79b72, #76513b)',
            'dishes': [('拿铁', 28, 86), ('冰美式', 22, 72), ('鸡肉三明治', 32, 45)],
            'reviews': [('咖啡小白', 5, 5, 4, 5, '演示点评：拿铁奶香柔和，座位舒适。', 1), ('午后客', 4, 4, 5, 4, '演示点评：适合看书，三明治分量刚好。', 5)],
        },
        {
            'name': '巷里小笼面馆', 'category': '小吃快餐', 'address': '杭州市拱墅区大关路 26 号',
            'phone': '0571-5555 0102', 'avg_price': 26,
            'description': '虚构样本店铺。现包小笼和热汤面，适合早餐与工作日简餐。',
            'emoji': '🥟', 'gradient': 'linear-gradient(135deg, #f3c875, #d99346)',
            'dishes': [('鲜肉小笼', 18, 132), ('葱油拌面', 16, 110), ('牛肉汤面', 28, 68)],
            'reviews': [('早起吃饭', 5, 5, 4, 4, '演示点评：小笼汤汁足，葱油面很香。', 2), ('上班族', 4, 4, 4, 5, '演示点评：出餐快，午餐价格实惠。', 7)],
        },
        {
            'name': '湘里人家', 'category': '湘菜', 'address': '长沙市开福区湘江中路 56 号',
            'phone': '0731-5555 0103', 'avg_price': 72,
            'description': '虚构样本店铺。鲜辣湘味家常菜，招牌剁椒鱼头适合朋友聚餐。',
            'emoji': '🌶️', 'gradient': 'linear-gradient(135deg, #f69b6e, #c94b39)',
            'dishes': [('剁椒鱼头', 88, 124), ('农家小炒肉', 42, 103), ('手撕包菜', 22, 61)],
            'reviews': [('湘味食客', 5, 5, 4, 5, '演示点评：鱼头鲜嫩，剁椒香而有层次。', 3), ('饭搭子', 4, 5, 4, 4, '演示点评：小炒肉很下饭，可以选择辣度。', 8)],
        },
        {
            'name': '青禾素食', 'category': '素食', 'address': '南京市秦淮区长乐路 36 号',
            'phone': '025-5555 0104', 'avg_price': 58,
            'description': '虚构样本店铺。以时令蔬菜、豆制品和菌菇入菜，清淡也有滋味。',
            'emoji': '🥬', 'gradient': 'linear-gradient(135deg, #94c78c, #4f8058)',
            'dishes': [('菌菇煲', 48, 92), ('时蔬豆腐', 32, 78), ('杂粮饭', 12, 53)],
            'reviews': [('青菜爱好者', 5, 5, 5, 4, '演示点评：菌菇煲鲜香，蔬菜很新鲜。', 1), ('轻食日记', 4, 4, 5, 5, '演示点评：环境安静，杂粮饭口感不错。', 6)],
        },
        {
            'name': '海风蒸鲜馆', 'category': '海鲜', 'address': '青岛市市南区澳门路 42 号',
            'phone': '0532-5555 0105', 'avg_price': 138,
            'description': '虚构样本店铺。主打清蒸海鲜与海鲜粥，适合家庭聚餐。',
            'emoji': '🦀', 'gradient': 'linear-gradient(135deg, #72c9df, #337eaa)',
            'dishes': [('清蒸鲈鱼', 98, 112), ('蒜蓉扇贝', 58, 89), ('海鲜粥', 48, 67)],
            'reviews': [('海边食客', 5, 5, 4, 5, '演示点评：清蒸鱼肉细嫩，调味清爽。', 2), ('周末聚餐', 4, 4, 5, 4, '演示点评：海鲜粥料足，适合全家来吃。', 9)],
        },
        {
            'name': '首尔石锅屋', 'category': '韩餐', 'address': '深圳市南山区南海大道 66 号',
            'phone': '0755-5555 0106', 'avg_price': 82,
            'description': '虚构样本店铺。石锅拌饭、泡菜汤与韩式炸鸡，提供双人套餐。',
            'emoji': '🍲', 'gradient': 'linear-gradient(135deg, #e6a48c, #ae6558)',
            'dishes': [('石锅拌饭', 42, 116), ('泡菜豆腐汤', 38, 94), ('韩式炸鸡', 58, 73)],
            'reviews': [('拌饭达人', 5, 5, 4, 4, '演示点评：锅巴香脆，配菜丰富。', 3), ('小饭团', 4, 4, 5, 5, '演示点评：炸鸡酥脆，泡菜汤酸辣开胃。', 6)],
        },
    ]
    for r in extra_restaurants:
        for key, index in [('rating', 1), ('taste', 2), ('env', 3), ('service', 4)]:
            r[key] = round(sum(review[index] for review in r['reviews']) / len(r['reviews']), 1)
    added = 0
    for r in (extra_restaurants if extra_only else restaurants + extra_restaurants):
        if db.execute('SELECT 1 FROM restaurants WHERE name=?', (r['name'],)).fetchone():
            continue
        cur = db.execute(
            """INSERT INTO restaurants
               (name, category, address, phone, description, avg_price,
                rating, taste_score, environment_score, service_score, emoji, gradient)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (r["name"], r["category"], r["address"], r["phone"], r["description"],
             r["avg_price"], r["rating"], r["taste"], r["env"], r["service"],
             r["emoji"], r["gradient"]),
        )
        rid = cur.lastrowid
        added += 1
        for name, price, rc in r["dishes"]:
            db.execute(
                "INSERT INTO dishes (restaurant_id, name, price, recommend_count) VALUES (?, ?, ?, ?)",
                (rid, name, price, rc),
            )
        for author, rating, taste, env, service, content, days in r["reviews"]:
            ts = (now - timedelta(days=days)).strftime("%Y-%m-%d %H:%M")
            db.execute(
                """INSERT INTO reviews
                   (restaurant_id, author, rating, taste_score, environment_score,
                    service_score, content, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (rid, author, rating, taste, env, service, content, ts),
            )
    db.commit()
    return added
