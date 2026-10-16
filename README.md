# 寻味 · 美食点评

面向中文用户的餐厅发现与点评项目，使用 Python、Flask、MySQL、Jinja2 和原生 CSS/JavaScript。包含用户端及管理员后台，支持沿用原 Demo 数据。


## MySQL 数据库（当前默认）

项目默认连接 MySQL，SQLite 仅保留用于原数据迁移和隔离测试。请先阅读 [MySQL 配置与迁移](docs/mysql.md)，配置连接后再执行下方初始化或启动命令。

已有 `xunwei.db` 时，先运行 `python -m flask --app app migrate-sqlite --source xunwei.db` 导入到空 MySQL 库，然后启动项目；不要先导入演示数据。迁移保留用户、密码哈希、餐厅、点评、收藏和销量，并校验全部导入数据，原文件保持不变。

## 快速体验

需要 Python 3.11 或以上。在项目目录执行：

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS / Linux: source .venv/bin/activate
python -m pip install -r requirements.txt
python -m flask --app app init-db --demo
python scripts/seed_sales.py
python serve.py
```

打开 [首页](http://127.0.0.1:5000/)，或直接查看 [演示销量榜](http://127.0.0.1:5000/rankings?source=demo)。演示账号为 `admin / admin123` 和 `foodie / foodie123`。推荐页可按菜系和预算筛选；登录后收藏或点评，推荐将结合个人偏好。

仓库只包含源码，不上传本地数据库、密钥、备份或依赖目录。以上初始化步骤会在本地创建虚构餐厅、点评和随机演示销量，不需要下载现有业务数据库。

## 功能

- 餐厅/菜品搜索、分类、排序、跨页收藏筛选与详情评分。
- 店铺分类目录（`/categories`）：按中餐、日韩料理、西餐、火锅烧烤、小吃快餐、咖啡甜品、轻食素食七个大类展示数量与平均人均价格，点击后筛选店铺。川菜、粤菜等具体菜系保留在店铺资料中，支持原有搜索与推荐；未识别的菜系归入“其他美食”。后台可选择已有菜系或填写新菜系。
- 注册登录、个人中心、账号设置、密码修改和旧会话失效。
- 点评发布、编辑、删除与管理员隐藏/恢复；评分实时重算。
- 管理员餐厅增删改、菜品增删改、用户启停、历史点评审核与操作日志。
- 数据库版本迁移、升级前自动备份、命令行备份和健康检查。
- 参数绑定、密码哈希、CSRF、权限校验、登录失败次数限制。
- 日、周、月餐厅销量排行榜，菜系筛选、同销量并列、录入与演示数据分开统计。
- 智能推荐：结合收藏、最近的可见点评、菜系偏好、人均价位、口碑和近 7 天录入销量，展示推荐理由，支持菜系与预算筛选。

## 排行榜与智能推荐

首页或导航栏进入“销量排行榜”和“智能推荐”。日榜统计北京时间当天，周榜从周一开始，月榜从每月 1 日开始，均统计至今天；销量单位为完成订单的“单”。

管理员进入后台的“销量管理”，按餐厅、日期录入当天销量。同日重复保存会替换总量，填 0 将当天销量归零。当前没有支付或订单系统，销量来自管理员录入，不代表平台自动验证的交易。

课程展示可在销量管理点击“生成演示销量”，生成最近 35 天虚构数据，再选择排行榜的“演示销量”。演示数据不会混入录入销量榜、不会影响推荐；生产模式禁止生成演示数据。录入同餐厅同日期的真实销量会替换该演示记录。

推荐使用本地可解释的加权排序，无需外部 AI 接口。基础权重为平滑口碑 45%、菜系偏好 35%、常选价位 10%、近 7 天录入销量 10%；对已收藏/好评餐厅适度降权以鼓励发现，并对重复菜系适度降权。收藏和 4~5 星点评建立偏好，最近可见的 1~2 星点评将对应餐厅排除，隐藏点评不参与。没有行为记录的用户按口碑和热度推荐；筛选条件始终生效。

## 本机运行

本机已有 SQLite 数据库时，按上方 MySQL 指南显式导入；启动只初始化当前配置的数据库。Windows 当前开发环境可使用：

```powershell
D:\python\python.exe -m pip install -r requirements.txt
D:\python\python.exe serve.py
```

也可运行 `./start.ps1`。默认地址为 [http://127.0.0.1:5000](http://127.0.0.1:5000)，健康检查为 `/health`。
启动脚本优先使用项目 `.venv`，其次系统 Python，最后尝试本机 `D:\python\python.exe`。
保留 `python app.py` 作为开发入口；正式服务使用 Waitress 的 `serve.py`。

原 Demo 账号保持可用：`admin / admin123`、`foodie / foodie123`。升级后需重新登录。
新版本可在“设置”修改密码。现有商家和历史示例点评均为虚构演示内容。

## 全新安装

演示初始化包含 14 家虚构店铺。新增样本包括晨光咖啡馆、巷里小笼面馆、湘里人家、青禾素食、海风蒸鲜馆、首尔石锅屋，覆盖咖啡、小吃快餐、湘菜、素食、海鲜和韩餐，每家配有 3 道招牌菜和 2 条演示点评。
已有本地数据库可先运行 `python -m flask --app app backup-db`，再运行 `python -m flask --app app seed-shops` 补充这 6 家店铺；同名店铺会跳过，重复执行不新增重复记录。该命令不创建演示账号，生产模式禁止执行。店铺分类来自当前店铺资料，新增、改分类和删除店铺后自动更新。

建议 Python 3.11 或以上，当前在 Windows / Python 3.14 上验收。

Windows 一键安装：运行 `./setup.ps1 -Demo` 导入虚构餐厅和演示账号；运行 `./setup.ps1` 则初始化空项目并提示创建管理员。安装完成后运行 `./start.ps1`。

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m flask --app app init-db
.\.venv\Scripts\python.exe -m flask --app app create-admin
.\.venv\Scripts\python.exe serve.py
```

`create-admin` 会提示输入用户名和密码。默认初始化空数据库，不创建固定密码的管理员。
若需要示例餐厅及演示账号，可在开发环境显式运行 `python -m flask --app app init-db --demo`。
勿删除业务库来升级；已经初始化的示例餐厅即使全部删除，也不会在重启后重新出现。

## 配置

MySQL 配置可从本机 instance/mysql.json 读取，系统环境变量优先覆盖；不自动加载 .env。

| 环境变量 | 用途 |
| --- | --- |
| XUNWEI_DB_BACKEND | 默认 mysql；sqlite 仅用于旧库维护/测试 |
| MYSQL_HOST / MYSQL_PORT | 默认 127.0.0.1 / 3306 |
| MYSQL_USER / MYSQL_PASSWORD | MySQL 用户名（默认 xunwei）和密码 |
| MYSQL_DATABASE | MySQL 库名，默认 xunwei；需事先创建 |
| XUNWEI_DATABASE | 仅 sqlite 后端使用的文件路径 |
| SECRET_KEY | 会话签名密钥；生产环境必须设置至少 32 字符的随机值 |
| XUNWEI_ENV | production 启用生产校验及 Secure Cookie |
| XUNWEI_HOST | 服务监听地址，默认 127.0.0.1 |
| XUNWEI_PORT | 端口，默认 5000 |

本地未设置 SECRET_KEY 时，在 `instance/secret.key` 持久化随机密钥；该文件不应提交或共享。
生产部署使用全新数据库、独立管理员、HTTPS 反向代理及固定随机密钥；`production` 模式禁止导入演示账号。
本次仅交付本地项目与启动能力，尚未部署公网。

## 备份与测试

```powershell
python -m flask --app app backup-db
python -m unittest discover -s tests -v
```

MySQL 备份保存到项目 `backups/` 的 `.sql` 文件，恢复到空库的方法见 MySQL 指南。SQLite 后端仍生成 `.db` 备份。备份期间不要执行建表或改表操作。
自动化测试均使用临时数据库。

## 目录结构

```text
app.py                  Flask CLI / 开发兼容入口
serve.py                Waitress 启动入口
start.ps1               Windows 启动脚本
xunwei/
  __init__.py           应用工厂、配置、异常处理、健康检查
  db.py                 数据库连接与初始化
  migrations.py         版本迁移与一致性备份
  security.py           会话、权限、CSRF
  services.py           评分重算与操作日志
  accounts.py           账号、个人中心、密码管理
  catalog.py            餐厅浏览与详情
  discovery.py          销量榜与本地个性化推荐
  reviews.py            点评业务
  favorites.py          收藏与游客数据合并
  admin.py              餐厅、菜品、用户管理与审核
  cli.py                初始化、管理员创建、备份命令
  seed.py               开发示例数据
templates/              用户端与后台模板
static/                 样式及前端交互
scripts/seed_sales.py   生成最近 35 天随机演示销量，不覆盖已有记录
tests/                  业务与项目回归测试
docs/                   设计说明与验收流程
```

详见 [课程项目说明](docs/course-report.md)、[项目设计](docs/architecture.md) 和 [验收步骤](docs/acceptance.md)。

## Apifox 接口文档

[OpenAPI 导入文件](docs/openapi.json) 覆盖现有 HTTP 路由，包含参数、表单/JSON 请求、HTML/JSON 响应及会话和 CSRF 说明。运行 `python scripts/export_openapi.py` 可重新生成，具体导入和调试步骤见 [Apifox 使用说明](docs/apifox.md)。文档不包含真实账号凭据或数据库记录。

## 课程展示与交付

运行 `./scripts/package.ps1` 会生成 `dist/xunwei-source-1.0.0.zip`。源码包包含项目代码、示例数据生成逻辑、文档和测试，不包含本机数据库、密码密钥、虚拟环境或备份。接收方解压后按“全新安装”操作即可重建演示环境。

建议展示顺序：游客搜索与收藏 → 普通用户点评和个人中心 → 管理员审核、菜品管理与操作记录。可结合 [验收步骤](docs/acceptance.md) 演示主要业务流。
