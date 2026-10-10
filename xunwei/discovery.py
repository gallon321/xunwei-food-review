"""Calendar sales rankings and explainable, local personalized recommendations."""
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from flask import Blueprint, abort, g, render_template, request
from .db import get_db

bp = Blueprint('discovery', __name__)
PERIODS = {'day': '日榜', 'week': '周榜', 'month': '月榜'}


def today():
    return datetime.now(timezone(timedelta(hours=8))).date()


def period_start(period, current):
    if period == 'day':
        return current
    if period == 'week':
        return current - timedelta(days=current.weekday())
    return current.replace(day=1)


def ranked_restaurants(period='week', category='', source='manual', current=None):
    current = current or today()
    start = period_start(period, current)
    rows = get_db().execute('''
        SELECT r.*, SUM(s.quantity) AS sales, COUNT(*) AS recorded_days
        FROM restaurants r JOIN daily_sales s ON s.restaurant_id=r.id
        WHERE s.sale_date>=? AND s.sale_date<=? AND s.source=? AND (?='' OR r.category=?)
        GROUP BY r.id HAVING SUM(s.quantity)>0
        ORDER BY sales DESC, r.rating DESC, r.id ASC
    ''', (start.isoformat(), current.isoformat(), source, category, category)).fetchall()
    result = []
    last_sales, rank = None, 0
    for index, row in enumerate(rows, 1):
        if row['sales'] != last_sales:
            rank = index
        result.append(dict(row, rank=rank))
        last_sales = row['sales']
    return result


def recommend_restaurants(user_id=None, category='', budget=None, limit=6):
    db = get_db()
    current = today()
    rows = db.execute('''SELECT r.*, COUNT(rv.id) AS review_count
        FROM restaurants r LEFT JOIN reviews rv ON rv.restaurant_id=r.id AND rv.status='visible'
        WHERE (?='' OR r.category=?) AND (? IS NULL OR r.avg_price<=?)
        GROUP BY r.id''', (category, category, budget, budget)).fetchall()
    preferences = defaultdict(float)
    liked, disliked, prices = set(), set(), []
    if user_id:
        for row in db.execute('''SELECT r.* FROM favorites f JOIN restaurants r ON r.id=f.restaurant_id
                                 WHERE f.user_id=?''', (user_id,)):
            liked.add(row['id'])
            preferences[row['category']] += 3
            prices.append(row['avg_price'])
        # Only the user's latest visible rating for each restaurant influences taste.
        seen = set()
        for row in db.execute('''SELECT rv.rating,r.id,r.category,r.avg_price FROM reviews rv
            JOIN restaurants r ON r.id=rv.restaurant_id WHERE rv.user_id=? AND rv.status='visible'
            ORDER BY rv.created_at DESC,rv.id DESC''', (user_id,)):
            if row['id'] in seen:
                continue
            seen.add(row['id'])
            if row['rating'] >= 4:
                preferences[row['category']] += row['rating'] - 2
                prices.append(row['avg_price'])
                liked.add(row['id'])
            elif row['rating'] <= 2:
                disliked.add(row['id'])
    sales = {row['restaurant_id']: row['sales'] for row in db.execute('''
        SELECT restaurant_id,SUM(quantity) sales FROM daily_sales
        WHERE source='manual' AND sale_date>=? AND sale_date<=? GROUP BY restaurant_id
    ''', ((current - timedelta(days=6)).isoformat(), current.isoformat()))}
    max_sales = max(sales.values(), default=1) or 1
    max_preference = max(preferences.values(), default=1)
    personalized = bool(preferences)
    expected_price = sum(prices) / len(prices) if prices else None
    candidates = []
    for row in rows:
        if row['id'] in disliked:
            continue
        r = dict(row)
        # Bayesian smoothing avoids treating a single five-star review as certainty.
        quality = (r['rating'] * r['review_count'] + 3.5 * 5) / (r['review_count'] + 5) / 5
        affinity = preferences.get(r['category'], 0) / max_preference
        price_fit = 1 / (1 + abs(r['avg_price'] - expected_price) / max(expected_price, 1)) if expected_price is not None else 0
        score = .45 * quality + .35 * affinity + .10 * price_fit + .10 * sales.get(r['id'], 0) / max_sales
        if r['id'] in liked:
            score -= .12  # Favor discovery while retaining familiar options if needed.
        reasons = []
        if affinity:
            reasons.append(f"符合你偏好的{r['category']}")
        if budget is not None:
            reasons.append(f'人均在 ¥{budget} 预算内')
        elif expected_price is not None and price_fit >= .8:
            reasons.append('接近你常选的人均价位')
        if r['review_count'] and r['rating'] >= 4:
            reasons.append(f"食客评分 {r['rating']} 分")
        if sales.get(r['id'], 0):
            reasons.append('近 7 天有销量记录')
        if r['id'] in liked:
            reasons.append('你收藏或好评过的餐厅')
        r.update(reasons=reasons or ['发现一家新餐厅'], recommendation_score=score)
        candidates.append(r)
    selected, counts = [], defaultdict(int)
    while candidates and len(selected) < limit:
        best = max(candidates, key=lambda r: (r['recommendation_score'] - .08 * counts[r['category']], -r['id']))
        selected.append(best)
        counts[best['category']] += 1
        candidates.remove(best)
    return selected, personalized


def categories():
    return [r[0] for r in get_db().execute('SELECT DISTINCT category FROM restaurants ORDER BY category')]


@bp.get('/rankings')
def rankings():
    period = request.args.get('period', 'day')
    source = request.args.get('source', 'manual')
    if period not in PERIODS or source not in ('manual', 'demo'):
        abort(400)
    category = request.args.get('category', '').strip()
    current = today()
    rows = ranked_restaurants(period, category, source, current)
    return render_template('rankings.html', restaurants=rows, period=period, periods=PERIODS,
                           source=source, category=category, categories=categories(),
                           start=period_start(period, current), end=current,
                           total_sales=sum(r['sales'] for r in rows))


@bp.get('/recommendations')
def recommendations():
    category = request.args.get('category', '').strip()
    raw_budget = request.args.get('budget', '').strip()
    budget = None
    if raw_budget:
        try:
            budget = int(raw_budget)
        except ValueError:
            abort(400)
        if not 0 <= budget <= 100000:
            abort(400)
    rows, personalized = recommend_restaurants(g.user['id'] if g.user else None, category, budget, 12)
    return render_template('recommendations.html', restaurants=rows, personalized=personalized,
                           category=category, budget=budget, categories=categories())
