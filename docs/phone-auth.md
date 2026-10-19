# 本地手机验证码登录与注册

启动项目后，在原有登录、注册页面点击“使用手机验证码登录/注册”。输入中国大陆11位手机号，点击“获取验证码”，页面会显示随机6位演示验证码，输入后提交即可。手机号注册会创建独立账号；已有用户名账号不会自动关联手机号。

这是本地演示短信，不会向手机发送真实短信，不依赖 Redis 或短信服务商。默认启用；设置 `XUNWEI_SMS_DEMO=0` 可关闭。`XUNWEI_ENV=production` 下强制禁止展示演示验证码，未配置真实发送器时获取验证码会返回503。

启动入口 `python app.py` 或 `python serve.py` 会创建、升级数据库。如果已有服务在运行，请重启。也可执行 `.venv\Scripts\python.exe -m flask --app app init-db` 手动升级。数据库版本升级到6，新增手机号关联、验证码和发送限流三张表，兼容 MySQL 与 SQLite，保留已有账号和数据。SQLite 升级按原有机制自动备份。

验证码有效期5分钟、最多尝试5次，成功校验后立即失效，登录与注册用途隔离。验证码以 HMAC 摘要存储，不保存明文。同一手机号每分钟最多1次、每小时10次，同一IP每小时30次。原有用户名密码登录继续可用。手机账号不设置用户密码，可继续通过验证码登录。

接口均使用表单参数，POST 需要同一会话 CSRF token：

| 地址 | 方法 | 参数 |
| --- | --- | --- |
| `/auth/sms/send` | POST | `phone`、`purpose`（login/register）、`csrf_token` |
| `/phone/register` | GET/POST | POST：`phone`、`code`、`csrf_token`，可选 `next` |
| `/phone/login` | GET/POST | POST：`phone`、`code`、`csrf_token`，可选 `next` |

后续如需真实短信，可在应用配置中设置 `SMS_DEMO=False` 和 `SMS_SENDER` 可调用函数。函数接收 `(phone, code)`，发送失败须抛出异常，应用将使本次验证码失效。当前版本按需求仅启用本地演示模式。
