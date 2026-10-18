from datetime import datetime
from flask import (Blueprint, current_app as app, abort, flash, g, jsonify,
                   redirect, render_template, request, session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash
from .db import get_db
from .security import login_required, admin_required, safe_next
from .services import recalculate_restaurant, record_visit
from .hours import OPEN_SQL, business_hours, current_time

bp = Blueprint("catalog", __name__)


@bp.app_context_processor
def hours_context():
    # A single clock snapshot for every card rendered in the request.
    now = current_time()
    return dict(business_hours=lambda row: business_hours(row, now))

# 大类用于浏览，restaurants.category 保留具体菜系，供搜索和推荐使用。
SHOP_GROUPS = {
    '中餐': ('中餐', '川菜', '粤菜', '江浙菜', '湘菜', '鲁菜', '徽菜', '闽菜', '东北菜', '新疆菜', '北京菜', '海鲜'),
    '日韩料理': ('日韩料理', '日料', '日本料理', '韩餐', '韩国料理'),
    '西餐': ('西餐', '法餐', '意大利菜', '牛排', '披萨'),
    '火锅烧烤': ('火锅烧烤', '火锅', '烧烤', '烤肉'),
    '小吃快餐': ('小吃快餐', '小吃', '快餐', '面馆', '早餐'),
    '咖啡甜品': ('咖啡甜品', '咖啡', '甜品', '奶茶', '烘焙', '饮品'),
    '轻食素食': ('轻食素食', '轻食', '素食', '沙拉'),
}


def shop_group(category):
    return next((name for name, members in SHOP_GROUPS.items() if category in members), '其他美食')


def shop_group_summary():
    grouped = {}
    for row in get_db().execute('''SELECT category, COUNT(*) AS shop_count,
            SUM(avg_price) AS price_total FROM restaurants GROUP BY category ORDER BY category'''):
        name = shop_group(row['category'])
        group = grouped.setdefault(name, dict(category=name, shop_count=0, price_total=0, subcategories=[]))
        group['shop_count'] += row['shop_count']
        group['price_total'] += row['price_total'] or 0
        group['subcategories'].append(row['category'])
    for group in grouped.values():
        group['avg_price'] = round(group['price_total'] / group['shop_count'])
    return [grouped[name] for name in (*SHOP_GROUPS, '其他美食') if name in grouped]

SORT_OPTIONS = [
    ("rating", "综合排序"),
    ("review_count", "点评最多"),
    ("price_asc", "人均从低到高"),
    ("price_desc", "人均从高到低"),
    ("rating_asc", "评分从低到高"),
]


def category_summary():
    """按现有店铺统计分类；新增或调整店铺后即时更新。"""
    return get_db().execute("""SELECT category, COUNT(*) AS shop_count,
        ROUND(AVG(avg_price)) AS avg_price FROM restaurants
        GROUP BY category ORDER BY shop_count DESC, category""").fetchall()


@bp.get('/categories')
def categories():
    groups = shop_group_summary()
    return render_template('categories.html', groups=groups,
                           shop_total=sum(row['shop_count'] for row in groups))

# ---------------------------------------------------------------- 首页
@bp.route("/")
def index():
    db = get_db()
    q = (request.args.get("q") or "").strip()
    category = (request.args.get("category") or "").strip()
    location = (request.args.get("location") or "").strip()[:200]
    sort = request.args.get("sort") or "rating"
    page = max(request.args.get("page", 1, type=int), 1)
    per_page = 6

    where, params = [], []
    favorites_only = request.args.get("favorites") == "1"
    guest_ids = request.args.get("ids", "")[:2000]
    if favorites_only:
        if g.user:
            where.append("EXISTS (SELECT 1 FROM favorites f WHERE f.restaurant_id=r.id AND f.user_id=?)")
            params.append(g.user["id"])
        else:
            ids = [int(v) for v in guest_ids.split(",") if v.isascii() and v.isdigit() and len(v) < 10][:100]
            where.append("r.id IN (" + ",".join("?" for _ in ids) + ")" if ids else "0=1")
            params.extend(ids)
    if q:
        where.append(
            "(r.name LIKE ? OR r.category LIKE ? OR r.address LIKE ? "
            "OR r.description LIKE ? OR EXISTS (SELECT 1 FROM dishes d "
            "WHERE d.restaurant_id = r.id AND d.name LIKE ?))"
        )
        like = f"%{q}%"
        params += [like, like, like, like, like]
    if category:
        # 同时兼容大类入口与原有具体菜系链接。
        members = next((group['subcategories'] for group in shop_group_summary()
                        if group['category'] == category), [category])
        where.append('r.category IN (' + ','.join('?' for _ in members) + ')')
        params.extend(members)
    if location:
        where.append("r.address LIKE ?")
        params.append(f"%{location}%")

    where_sql = ("WHERE " + " AND ".join(where)) if where else ""
    order_map = {
        "rating": "r.rating DESC, review_count DESC",
        "review_count": "review_count DESC, r.rating DESC",
        "price_asc": "r.avg_price ASC, r.rating DESC",
        "price_desc": "r.avg_price DESC, r.rating DESC",
        "rating_asc": "r.rating ASC, review_count DESC",
    }
    order_sql = 'is_open DESC, ' + order_map.get(sort, order_map["rating"]) + ', r.id ASC'
    now = current_time()

    total = db.execute(f"SELECT COUNT(*) FROM restaurants r {where_sql}", params).fetchone()[0]
    page = min(page, max(1, (total + per_page - 1) // per_page))
    rows = db.execute(
        f"""SELECT r.*, COUNT(rv.id) AS review_count, {OPEN_SQL} AS is_open
            FROM restaurants r
            LEFT JOIN reviews rv ON rv.restaurant_id = r.id AND rv.status='visible'
            {where_sql}
            GROUP BY r.id
            ORDER BY {order_sql} LIMIT ? OFFSET ?"""
        , [now] * 4 + params + [per_page, (page - 1) * per_page],
    ).fetchall()

    # 附加每家的招牌推荐菜（按推荐数取前 3）
    dishes = db.execute(
        "SELECT restaurant_id, name FROM dishes ORDER BY recommend_count DESC"
    ).fetchall()
    dish_map = {}
    for d in dishes:
        dish_map.setdefault(d["restaurant_id"], []).append(d["name"])

    restaurants = [dict(r) for r in rows]
    for r in restaurants:
        r["top_dishes"] = dish_map.get(r["id"], [])[:3]

    groups = shop_group_summary()
    categories = [row['category'] for row in groups]
    favorite_ids = []
    if g.user:
        favorite_ids = [row[0] for row in db.execute(
            "SELECT restaurant_id FROM favorites WHERE user_id=?", (g.user["id"],))]

    from .discovery import ranked_restaurants
    ranking_preview = ranked_restaurants('day')[:3]
    ranking_source = 'manual'
    if not ranking_preview:
        ranking_preview = ranked_restaurants('day', source='demo')[:3]
        ranking_source = 'demo'

    return render_template(
        "index.html", restaurants=restaurants, categories=categories,
        category_counts={row['category']: row['shop_count'] for row in groups},
        q=q, category=category, sort=sort, sort_options=SORT_OPTIONS,
        active_group=shop_group(category) if category and category not in SHOP_GROUPS else category,
        location=location,
        total=total, page=page, pages=max(1, (total + per_page - 1) // per_page),
        favorite_ids=favorite_ids,
        favorites_only=favorites_only, guest_ids=guest_ids,
        ranking_preview=ranking_preview, ranking_source=ranking_source,
    )


# ---------------------------------------------------------------- 详情
@bp.route("/restaurant/<int:rid>")
def detail(rid):
    db = get_db()
    r = db.execute("SELECT * FROM restaurants WHERE id = ?", (rid,)).fetchone()
    if r is None:
        abort(404)
    record_visit(rid)

    dishes = db.execute(
        """SELECT d.*, COUNT(dr.id) AS review_count, ROUND(AVG(dr.rating),1) AS rating
        FROM dishes d LEFT JOIN dish_reviews dr ON dr.dish_id=d.id AND dr.status='visible'
        WHERE d.restaurant_id=? GROUP BY d.id ORDER BY d.recommend_count DESC,d.id""",
        (rid,),
    ).fetchall()
    dish_previews = {}
    for review in db.execute('''SELECT * FROM (
        SELECT dr.*,u.username AS display_author,
        ROW_NUMBER() OVER (PARTITION BY dr.dish_id ORDER BY dr.created_at DESC,dr.id DESC) AS position
        FROM dish_reviews dr JOIN users u ON u.id=dr.user_id
        JOIN dishes d ON d.id=dr.dish_id WHERE d.restaurant_id=? AND dr.status='visible'
        ) recent WHERE position<=2 ORDER BY dish_id,position''', (rid,)):
        dish_previews.setdefault(review['dish_id'], []).append(review)
    page = max(request.args.get("page", 1, type=int), 1)
    per_page = app.config["REVIEWS_PER_PAGE"]
    total = db.execute("SELECT COUNT(*) FROM reviews WHERE restaurant_id=? AND status='visible'", (rid,)).fetchone()[0]
    page = min(page, max(1, (total + per_page - 1) // per_page))
    reviews = db.execute(
        """SELECT rv.*, COALESCE(u.username, rv.author) AS display_author
           FROM reviews rv LEFT JOIN users u ON u.id=rv.user_id
           WHERE rv.restaurant_id = ? AND rv.status='visible'
           ORDER BY rv.created_at DESC, rv.id DESC LIMIT ? OFFSET ?""",
        (rid, per_page, (page - 1) * per_page),
    ).fetchall()

    dist = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    all_ratings = db.execute("SELECT rating FROM reviews WHERE restaurant_id=? AND status='visible'", (rid,)).fetchall()
    for rv in all_ratings:
        dist[rv["rating"]] += 1
    is_favorite = bool(g.user and db.execute(
        "SELECT 1 FROM favorites WHERE user_id=? AND restaurant_id=?", (g.user["id"], rid)).fetchone())

    return render_template(
        "detail.html", r=r, dishes=dishes, dish_previews=dish_previews, reviews=reviews,
        dist=dist, total=total, page=page,
        pages=max(1, (total + per_page - 1) // per_page), is_favorite=is_favorite,
    )


@bp.get('/restaurant/<int:rid>/dish/<int:did>')
def dish_detail(rid, did):
    db = get_db()
    restaurant = db.execute('SELECT * FROM restaurants WHERE id=?', (rid,)).fetchone()
    dish = db.execute('''SELECT d.*,COUNT(dr.id) AS review_count,ROUND(AVG(dr.rating),1) AS rating
        FROM dishes d LEFT JOIN dish_reviews dr ON dr.dish_id=d.id AND dr.status='visible'
        WHERE d.id=? AND d.restaurant_id=? GROUP BY d.id''', (did, rid)).fetchone()
    if restaurant is None or dish is None:
        abort(404)
    record_visit(rid)
    total = dish['review_count']
    per_page = app.config['REVIEWS_PER_PAGE']
    pages = max(1, (total + per_page - 1) // per_page)
    page = min(max(request.args.get('page', 1, type=int), 1), pages)
    reviews = db.execute('''SELECT dr.*,u.username AS display_author FROM dish_reviews dr
        JOIN users u ON u.id=dr.user_id WHERE dr.dish_id=? AND dr.status='visible'
        ORDER BY dr.created_at DESC,dr.id DESC LIMIT ? OFFSET ?''',
        (did, per_page, (page - 1) * per_page)).fetchall()
    return render_template('dish_detail.html', r=restaurant, dish=dish, reviews=reviews,
                           page=page, pages=pages, total=total)
