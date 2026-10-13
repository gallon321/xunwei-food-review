# Apifox：寻味点评

导入文件为本目录的 `openapi.json`（OpenAPI 3.0.3）。它记录真实 Flask 路由，不新增接口，不读取或导出数据库、密码、Cookie、密钥或业务记录。

## 导入

新项目名称：**寻味点评**。选择 OpenAPI / Swagger 文件导入 `openapi.json`。已有项目可从“项目设置 → 导入数据”导入，优先预览并使用智能合并，不删除已有接口。

官方说明：https://docs.apifox.com/import-openapi-swagger

如果浏览器扩展不允许代选文件，可以由用户手动上传，或运行 `python scripts/serve_openapi.py` 临时提供 `http://127.0.0.1:8765/openapi.json`，从项目内选择 URL 导入。临时服务仅监听本机，仅提供此文档，并只允许 `https://app.apifox.com` 跨域读取；导入完成后按 Ctrl+C 关闭，不绑定为自动同步数据源。

## 调试

1. 在本机启动项目：`python serve.py`。环境基础 URL：`http://127.0.0.1:5000`。云端调试服务无法直接访问你电脑的 localhost，需使用本机客户端或本地请求代理。
2. 首先运行 `GET /health`，应返回 `{"status":"ok","version":"1.0.0"}`。
   桌面版导入后可能勾选可选参数但未填写值。排行榜的 `period` 填 `day`、`week` 或 `month`，`source` 填 `manual` 或 `demo`；也可以取消勾选，让服务端使用默认值。发送 `period=&source=` 会返回 400，OpenAPI 的 schema default 不代表客户端一定会自动填入。推荐接口不限定预算时取消勾选 `budget`。
3. 开启 Cookie 管理。运行 `GET /login`，保留返回的 `session` Cookie，从 HTML 的隐藏字段 `name="csrf_token"` 或 `window.XUNWEI.csrf` 提取 CSRF token。
4. 运行 `POST /login`，Body 选择 `x-www-form-urlencoded`，填写 username、password；通过 `X-CSRF-Token` 请求头或 `csrf_token` 表单字段发送 token。不要把真实账号凭据写入共享用例。
5. 登录成功会清除旧 CSRF token。保留最新 Cookie，再次 `GET /`，提取新 token，才能操作收藏、点评或管理后台。
6. JSON 请求 `POST /favorites/migrate` 必须使用请求头 `X-CSRF-Token`。收藏切换接口同时发送 `X-Requested-With: XMLHttpRequest` 才返回 JSON。

大部分接口是 HTML 页面或表单操作，不是 REST JSON API。若想观察真实 302 响应，关闭自动跟随重定向；302 可能是成功、未登录或校验失败，需结合 Location 和页面提示判断。管理员接口需管理员会话。删除、改密、状态切换、生成演示销量会修改数据，禁止在真实记录上随意测试。

## 更新导入文件

在项目根目录运行 `python scripts/export_openapi.py`。新增路由时需补充脚本中的 META；未知路由会报错，防止静默遗漏。HEAD、OPTIONS 和静态资源路由不作为业务接口导出。
