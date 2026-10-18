"""Export the existing Flask routes for Apifox; never accesses business records."""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from xunwei import create_app


def string(**options):
    return dict(type='string', **options)


def integer(**options):
    return dict(type='integer', **options)


def query(name, schema, description=''):
    return dict(name=name, **{'in': 'query'}, required=False, schema=schema, description=description)


PAGE = query('page', integer(minimum=1, default=1), '分页页码')
CATEGORY = query('category', string(), '菜系；留空表示不限')
SCORE = integer(minimum=1, maximum=5, example=5)
REVIEW = dict(rating=SCORE, taste_score=SCORE, environment_score=SCORE,
              service_score=SCORE, content=string(minLength=5, maxLength=500, example='菜品味道很好，服务也很热情。'))
RESTAURANT = dict(name=string(maxLength=80), category=string(maxLength=30),
                  address=string(maxLength=200), phone=string(maxLength=40),
                  opening_time=string(description='每日开始营业时间 HH:MM（北京时间），与 closing_time 同填或同空'),
                  closing_time=string(description='每日结束营业时间 HH:MM；早于开始表示次日结束，相同表示全天营业'),
                  description=string(maxLength=2000), avg_price=integer(minimum=0, maximum=100000),
                  emoji=string(maxLength=12), theme=string(enum=['warm', 'green', 'purple', 'pink'], default='warm'))
AUTH = dict(username=string(), password=string(format='password'), next=string(description='站内跳转路径，默认首页'))
HTML = {'description': 'HTML 页面（不是 JSON）', 'content': {'text/html': {'schema': string()}}}
REDIRECT = {'description': '重定向；302 不一定代表操作成功，须查看目标页面提示。',
            'headers': {'Location': {'schema': string(), 'description': '站内跳转目标'}}}

# endpoint: (summary, tag, query parameters, POST fields, required fields, access, notes)
META = {
    'catalog.dish_detail': ('菜品详情与评价', '菜品', [PAGE], None, [], 'public', '展示菜品价格、可见评价的平均评分和分页评价；无评价时不显示分数。'),
    'reviews.add_dish_review': ('发布菜品评价', '菜品', [], dict(rating=SCORE, content=REVIEW['content']), ['rating', 'content'], 'user', '菜品必须属于路径指定的店铺；评分为 1~5 星，内容 5~500 字，独立于店铺评分。校验失败重定向并提示。'),
    'reviews.delete_dish_review': ('删除菜品评价', '菜品', [], {}, [], 'owner', '仅本人或管理员可删除，菜品评分即时更新。'),
    'admin.dish_reviews': ('管理菜品评价', '菜品', [PAGE], None, [], 'admin', '展示指定店铺全部菜品评价，含隐藏评价，每页 20 条。'),
    'admin.toggle_dish_review': ('隐藏或恢复菜品评价', '菜品', [], {}, [], 'admin', '隐藏评价不展示且不参与平均分，操作记录写入审计日志。'),
    'catalog.categories': ('店铺分类目录', '餐厅', [], None, [], 'public', '按店铺分类展示店铺数量及平均人均价格，点击分类进入餐厅筛选列表。返回 HTML。'),
    'health': ('健康检查', '系统', [], None, [], 'public', '返回 JSON，检查数据库可连接。'),
    'favicon': ('站点图标占位', '系统', [], None, [], 'public', '返回空响应。'),
    'catalog.index': ('餐厅搜索列表', '餐厅', [query('q', string(), '餐厅、菜品或地址关键词'), CATEGORY,
        query('location', string(maxLength=200), '地址关键词'), query('sort', string(enum=['rating', 'review_count', 'price_asc', 'price_desc', 'rating_asc'], default='rating')),
        PAGE, query('favorites', string(enum=['0', '1'], default='0')),
        query('ids', string(maxLength=2000), '游客收藏的餐厅 ID，逗号分隔；仅 favorites=1 时生效')], None, [], 'public', '返回服务端渲染的餐厅列表 HTML。category 支持具体菜系或中餐、日韩料理、西餐、火锅烧烤、小吃快餐、咖啡甜品、轻食素食、其他美食大类；排行榜和推荐仍按具体菜系筛选。'),
    'catalog.detail': ('餐厅详情与点评', '餐厅', [PAGE], None, [], 'public', '返回 HTML；page 对点评列表分页。'),
    'discovery.rankings': ('日周月销量排行榜', '发现', [query('period', string(enum=['day', 'week', 'month'], default='day')),
        query('source', string(enum=['manual', 'demo'], default='manual')), CATEGORY], None, [], 'public', '按北京时间自然日、自然周（周一开始）、自然月累计；演示与正式销量分开。返回 HTML。'),
    'discovery.recommendations': ('智能推荐', '发现', [CATEGORY, query('budget', integer(minimum=0, maximum=100000), '人均预算上限')], None, [], 'optional', '匿名可访问；登录后结合个人收藏和点评。返回 HTML。'),
    'accounts.register': ('注册账号', '账号', [], AUTH, ['username', 'password'], 'public', '用户名 3–20 字符，密码 8–72 字符；成功后登录并重定向。常见校验失败返回 200 HTML，用户名并发冲突可能返回 400。'),
    'accounts.login': ('登录账号', '账号', [query('next', string(), '站内跳转路径')], AUTH, ['username', 'password'], 'public', '密码错误返回 200 HTML；成功返回 302 和会话 Cookie。登录后原 CSRF 失效，必须重新 GET 页面提取。失败次数过多返回 429。'),
    'accounts.logout': ('退出登录', '账号', [], {}, [], 'public', '清除会话并重定向。仍需 CSRF。'),
    'accounts.profile': ('个人中心', '账号', [query('tab', string(enum=['favorites','history','reviews'], default='favorites')), PAGE], None, [], 'user', '我的收藏、最近 100 家店铺浏览记录，以及店铺和菜品历史点评；每页 6 条。仅查看当前账号数据。'),
    'accounts.clear_history': ('清空浏览记录', '账号', [], {}, [], 'user', '仅清空当前账号的全部浏览记录，不影响收藏和点评。'),
    'accounts.remove_history': ('移除浏览记录', '账号', [], {}, [], 'user', '仅移除当前账号对指定店铺的浏览记录。'),
    'accounts.settings': ('账号设置 / 修改密码', '账号', [], dict(current_password=string(format='password'), password=string(format='password', minLength=8, maxLength=72), confirm_password=string(format='password')), ['current_password', 'password', 'confirm_password'], 'user', '密码修改后所有旧会话失效，需重新登录。校验失败返回 400 HTML。'),
    'favorites.toggle_favorite': ('切换餐厅收藏', '收藏', [], {}, [], 'user', '发送 X-Requested-With: XMLHttpRequest 才返回 JSON；否则重定向个人页。未登录重定向登录页。重复调用会取消收藏，不是幂等操作。'),
    'favorites.migrate_favorites': ('导入游客收藏', '收藏', [], dict(ids={'type': 'array', 'items': integer(minimum=1, maximum=2147483647), 'maxItems': 100, 'example': [1, 3]}), [], 'user', 'JSON 请求；只处理前 100 个 ID，忽略不存在的餐厅，重复收藏不会叠加。CSRF 必须放在请求头。'),
    'reviews.add_review': ('发布点评', '点评', [], REVIEW, ['rating', 'content'], 'user', '未提供分项评分时使用综合分；错误和成功都可能重定向，以页面提示为准。'),
    'reviews.edit_review': ('编辑点评', '点评', [], REVIEW, list(REVIEW), 'owner', '仅点评本人或管理员可编辑；无权限 403。校验失败返回 200 HTML。'),
    'reviews.delete_review': ('删除点评', '点评', [], {}, [], 'owner', '仅点评本人或管理员可删除；会修改业务数据，请勿用真实记录测试。'),
    'admin.admin_dashboard': ('管理后台概览', '管理后台', [query('review_page', integer(minimum=1, default=1))], None, [], 'admin', '点评列表分页；返回 HTML。'),
    'admin.admin_restaurant_new': ('新建餐厅', '管理后台', [], RESTAURANT, ['name', 'category', 'address'], 'admin', 'avg_price 缺省为 0；theme 转换为内置配色。字段无效返回 400。'),
    'admin.admin_restaurant_edit': ('编辑餐厅', '管理后台', [], RESTAURANT, ['name', 'category', 'address'], 'admin', '完整表单替换，不是局部更新；未传可选文本字段会清空。字段无效返回 400。'),
    'admin.admin_restaurant_delete': ('删除餐厅', '管理后台', [], {}, [], 'admin', '会删除业务记录，请勿用真实餐厅测试。'),
    'admin.admin_review_toggle': ('切换点评可见状态', '管理后台', [], {}, [], 'admin', 'visible 与 hidden 切换，并重算评分；重复调用会反转状态。'),
    'admin.admin_user_toggle': ('切换用户启用状态', '管理后台', [], {}, [], 'admin', '启用或停用用户并使其旧会话失效；不能停用当前管理员。'),
    'admin.dishes': ('餐厅菜品管理', '管理后台', [], dict(name=string(minLength=1, maxLength=80), price=integer(minimum=0, maximum=100000), dish_id=integer(minimum=1)), ['name', 'price'], 'admin', '不传 dish_id 为新增，传入为编辑；校验失败返回 200 HTML。'),
    'admin.delete_dish': ('删除餐厅菜品', '管理后台', [], {}, [], 'admin', '餐厅与菜品 ID 必须匹配；会删除业务记录。'),
    'admin.sales': ('每日销量管理', '销量管理', [PAGE], dict(restaurant_id=integer(minimum=1), sale_date=string(format='date', description='YYYY-MM-DD；不允许未来日期'), quantity=integer(minimum=0, maximum=1000000)), ['restaurant_id', 'sale_date', 'quantity'], 'admin', '同一餐厅同一天覆盖总量，不叠加；source 保存为 manual。GET 返回分页管理页面。'),
    'admin.sales_demo': ('生成演示销量', '销量管理', [], {}, [], 'admin', '仅非生产环境允许；生成近期 35 天演示销量，不覆盖已有记录。此操作会写入数据。'),
    'admin.audit_log': ('审计日志列表', '管理后台', [PAGE], None, [], 'admin', '分页查询操作日志，返回 HTML。'),
}


def build_spec():
    # Testing factory creates no files and does not initialize any database.
    app = create_app({'TESTING': True, 'SECRET_KEY': 'documentation-only'})
    spec = {
        'openapi': '3.0.3',
        'info': {'title': '寻味点评', 'version': '1.0.0', 'description':
            '现有 Flask 项目的真实 HTTP 接口，不新增 /api 路由。大部分接口返回 HTML 或 302；仅健康检查和收藏相关接口返回 JSON。\n\n'
            '鉴权：Flask session Cookie，不使用 Bearer Token。所有 POST 默认需要同一会话的 CSRF token；可放 X-CSRF-Token 请求头或表单 csrf_token。'
            '先 GET /login 并保存 Cookie，从 HTML 隐藏字段 csrf_token 或 window.XUNWEI.csrf 取得 token。登录成功后重新 GET 页面获取新 token。'
            'Apifox 中开启 Cookie 保持，调试时关闭自动重定向可观察原始 302。不要把真实密码、Cookie 或 token 保存到共享文档。'},
        'servers': [{'url': 'http://127.0.0.1:5000', 'description': '本地寻味服务；需在同一电脑运行'}],
        'tags': [{'name': tag} for tag in ['系统', '餐厅', '发现', '账号', '收藏', '点评', '管理后台', '销量管理']],
        'paths': {},
        'components': {'securitySchemes': {
            'SessionCookie': {'type': 'apiKey', 'in': 'cookie', 'name': 'session', 'description': '登录后由服务端设置，使用 Cookie 管理器保存。'},
            'CsrfToken': {'type': 'apiKey', 'in': 'header', 'name': 'X-CSRF-Token', 'description': '从同一会话的 HTML 提取；也可用表单 csrf_token。'}},
            'schemas': {'Health': {'type': 'object', 'required': ['status', 'version'], 'properties': {'status': string(enum=['ok']), 'version': string(example='1.0.0')}},
                        'FavoriteState': {'type': 'object', 'required': ['active', 'count'], 'properties': {'active': {'type': 'boolean'}, 'count': integer(minimum=0)}},
                        'FavoriteCount': {'type': 'object', 'required': ['count'], 'properties': {'count': integer(minimum=0)}}}},
    }
    for rule in sorted(app.url_map.iter_rules(), key=lambda r: r.rule):
        if rule.endpoint == 'static':
            continue
        summary, tag, queries, fields, required, access, notes = META[rule.endpoint]
        path = re.sub(r'<(?:int:)?(\w+)>', r'{\1}', rule.rule)
        for method in sorted(rule.methods - {'HEAD', 'OPTIONS'}):
            post = method == 'POST'
            operation = {'summary': summary + ('（页面）' if method == 'GET' and fields is not None else ''),
                         'operationId': rule.endpoint.replace('.', '_') + '_' + method.lower(),
                         'tags': [tag], 'description': notes,
                         'parameters': [{'name': name, 'in': 'path', 'required': True, 'schema': integer(minimum=1), 'example': 1}
                                        for name in sorted(rule.arguments)] + (queries if not post else []),
                         'responses': {}, 'security': []}
            responses = operation['responses']
            if method == 'GET':
                responses['200'] = HTML.copy()
            if post:
                operation['description'] += ('\n\n需同一会话 Cookie，并在 X-CSRF-Token 头传入 token。' if rule.endpoint == 'favorites.migrate_favorites'
                    else '\n\n所有 POST 需同一会话 Cookie 与 CSRF token；表单字段 csrf_token 和头 X-CSRF-Token 二选一。')
                operation['security'] = [{'CsrfToken': []}]
                body_fields = dict(fields)
                if rule.endpoint != 'favorites.migrate_favorites':
                    body_fields['csrf_token'] = string(description='如已发送 X-CSRF-Token，此字段可省略')
                schema = {'type': 'object', 'properties': body_fields}
                if required:
                    schema['required'] = required
                media = 'application/json' if rule.endpoint == 'favorites.migrate_favorites' else 'application/x-www-form-urlencoded'
                operation['requestBody'] = {'required': bool(required), 'content': {media: {'schema': schema}}}
                if media != 'application/json':
                    responses['302'] = REDIRECT.copy()
            if access in ('user', 'owner', 'admin'):
                operation['security'] = [{'SessionCookie': [], **({'CsrfToken': []} if post else {})}]
                operation['description'] += '\n\n权限：' + {'user': '已登录用户', 'owner': '点评本人或管理员', 'admin': '管理员'}[access] + '。'
                if access != 'admin':
                    responses['302'] = REDIRECT.copy()
            elif access == 'optional':
                operation['security'] = [{}, {'SessionCookie': []}]
            responses['400'] = dict(HTML, description='无效参数或 CSRF 校验失败；HTML 错误页')
            responses['403'] = dict(HTML, description='权限不足；HTML 错误页')
            if rule.arguments:
                responses['404'] = dict(HTML, description='记录不存在；HTML 错误页')
            responses['500'] = dict(HTML, description='服务内部错误；HTML 错误页')
            if post and rule.endpoint in ('accounts.login', 'accounts.register', 'accounts.settings', 'reviews.edit_review', 'admin.dishes'):
                responses['200'] = HTML.copy()
            if rule.endpoint == 'accounts.login' and post:
                responses['429'] = dict(HTML, description='登录尝试过于频繁；HTML 错误页')
            if rule.endpoint == 'favorites.toggle_favorite':
                operation['parameters'].append({'name': 'X-Requested-With', 'in': 'header', 'required': False,
                    'schema': string(enum=['XMLHttpRequest']), 'example': 'XMLHttpRequest', 'description': '发送此头返回 JSON，否则 302'})
            if rule.endpoint in ('health', 'favorites.toggle_favorite', 'favorites.migrate_favorites'):
                model, example = {'health': ('Health', {'status': 'ok', 'version': '1.0.0'}),
                    'favorites.toggle_favorite': ('FavoriteState', {'active': True, 'count': 1}),
                    'favorites.migrate_favorites': ('FavoriteCount', {'count': 2})}[rule.endpoint]
                responses['200'] = {'description': 'JSON 响应', 'content': {'application/json': {'schema': {'$ref': '#/components/schemas/' + model}, 'example': example}}}
            if rule.endpoint == 'favicon':
                responses.clear()
                responses['204'] = {'description': '空响应'}
            spec['paths'].setdefault(path, {})[method.lower()] = operation
    return spec


if __name__ == '__main__':
    target = ROOT / 'docs' / 'openapi.json'
    spec = build_spec()
    target.write_text(json.dumps(spec, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    count = sum(len(operations) for operations in spec['paths'].values())
    print(f'Exported {len(spec["paths"])} paths / {count} operations to {target}')
