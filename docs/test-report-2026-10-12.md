# 寻味点评测试记录（2026-10-12）

## 结论

已完成 Apifox Windows 桌面版冒烟测试及本地自动回归。本次覆盖范围内未发现业务功能回归；发现一项 Apifox 空参数调试配置问题，填写合法值后复测通过。不能据此保证全项目绝对没有 bug。

## Apifox 桌面实测

项目“寻味点评”，开发环境 `http://127.0.0.1:5000`，真实本机请求，不使用 Mock。

| 请求 | 结果 |
| --- | --- |
| GET /health | 200，JSON 为 status=ok / version=1.0.0，响应校验通过 |
| GET / | 200，HTML，响应校验通过 |
| GET /rankings?period=day&category= | 200，响应校验通过 |
| GET /rankings?period=week&category= | 200，响应校验通过 |
| GET /rankings?period=month&category= | 200，响应校验通过 |
| GET /recommendations（未发送可选 budget） | 200，HTML，响应校验通过 |
| GET /rankings?period=&source=&category= | 400；客户端勾选参数但未填写导致，合法参数复测通过 |

排行榜 source 未发送时使用 manual。日周月排名数据正确性由自动测试的固定日期边界及并列排名断言验证，桌面冒烟只验证连通性和响应，不等同于前端交互或排序正确性全覆盖。桌面调试参数仅在当前请求中调整，未保存共享接口定义。

## 自动回归

执行：`D:/python/python.exe -m unittest discover -s tests -v`。

34 项测试全部通过，耗时 16.539 秒。其中原有 31 项与新增 3 项真实 HTTP 测试分开运行也通过。

- 原有回归：注册登录、权限、收藏、点评生命周期、内容审核、菜品、销量验证及更新、自然日周月边界、并列排序、推荐偏好及负反馈、CSRF、登录限流、旧会话撤销、迁移备份、OpenAPI 路由覆盖等。
- 新增 `tests/test_http.py`：临时 SQLite 数据库 + Waitress 随机本机端口，通过真实 HTTP 传输及 CookieJar 验证公共页面、JSON/HTML 响应、安全响应头、400/403/404/302、CSRF 缺失、登录与登出、收藏幂等迁移、点评增改删、管理员读写、销量及餐厅增改删。
- HTTP 写入只发生在临时数据库；不向现有业务数据库写入测试点评、餐厅或销量。测试结束关闭服务器并清理临时数据。

## 限制和后续

登录、收藏和后台写入没有在 Apifox 桌面逐项执行，以上由自动回归及真实 HTTP 测试覆盖。未做并发压力、浏览器兼容、所有前端按钮交互、生产环境部署、第三方依赖安全审计。未同步 GitHub。

Apifox 导入后默认勾选空的可选参数，可能让“直接发送”失败；具体填写或取消勾选方式见 `docs/apifox.md`。本轮没有修改业务代码以放宽参数验证。
