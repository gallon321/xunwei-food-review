from datetime import datetime
from flask import (Blueprint, current_app as app, abort, flash, g, jsonify,
                   redirect, render_template, request, session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash
from .db import get_db
from .security import login_required, admin_required, safe_next
from .services import recalculate_restaurant

bp = Blueprint("catalog", __name__)

SORT_OPTIONS = [
    ("rating", "综合排序"),
    ("review_count", "点评最多"),
    ("price_asc", "人均从低到高"),
    ("price_desc", "人均从高到低"),
    ("rating_asc", "评分从低到高"),
]

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
        where.append("r.category = ?")
        params.append(category)
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
    order_sql = order_map.get(sort, order_map["rating"])

    total = db.execute(f"SELECT COUNT(*) FROM restaurants r {where_sql}", params).fetchone()[0]
    page = min(page, max(1, (total + per_page - 1) // per_page))
    rows = db.execute(
        f"""SELECT r.*, COUNT(rv.id) AS review_count
            FROM restaurants r
            LEFT JOIN reviews rv ON rv.restaurant_id = r.id AND rv.status='visible'
            {where_sql}
            GROUP BY r.id
            ORDER BY {order_sql} LIMIT ? OFFSET ?"""
        , params + [per_page, (page - 1) * per_page],
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

    categories = [row["category"] for row in
                  db.execute("SELECT DISTINCT category FROM restaurants ORDER BY category")]
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
        q=q, category=category, sort=sort, sort_options=SORT_OPTIONS,
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

    dishes = db.execute(
        "SELECT * FROM dishes WHERE restaurant_id = ? ORDER BY recommend_count DESC",
        (rid,),
    ).fetchall()
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
        "detail.html", r=r, dishes=dishes, reviews=reviews,
        dist=dist, total=total, page=page,
        pages=max(1, (total + per_page - 1) // per_page), is_favorite=is_favorite,
    )
