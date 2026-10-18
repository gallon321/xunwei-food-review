# MySQL 配置与数据迁移

默认数据库为 MySQL 8.0.16+，推荐 MySQL 8.4。字符集 utf8mb4，支持中文与表情。应用优先读取环境变量，也可读取本机 `instance/mysql.json` 的 MYSQL_HOST、MYSQL_PORT、MYSQL_USER、MYSQL_PASSWORD、MYSQL_DATABASE 字段；该文件已被 Git 忽略。当前本机连接已经写入此文件，直接运行 `start.ps1` 即可。其他机器可按下方步骤配置；应用不自动读取 `.env`。

## 使用已有 MySQL

由管理员创建一个空数据库及专用账号（将示例密码替换为自己的密码）：

```sql
CREATE DATABASE xunwei CHARACTER SET utf8mb4 COLLATE utf8mb4_bin;
CREATE USER 'xunwei'@'localhost' IDENTIFIED BY 'replace-with-your-password';
GRANT ALL PRIVILEGES ON xunwei.* TO 'xunwei'@'localhost';
```

```powershell
$env:MYSQL_HOST = '127.0.0.1'
$env:MYSQL_PORT = '3306'
$env:MYSQL_DATABASE = 'xunwei'
$env:MYSQL_USER = 'xunwei'
$mysqlCredential = Get-Credential -UserName xunwei -Message '请输入 MySQL 密码'
$env:MYSQL_PASSWORD = $mysqlCredential.GetNetworkCredential().Password
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

先在项目目录执行以下两种初始化方式之一：

- 保留现有数据：`python -m flask --app app migrate-sqlite --source xunwei.db`
- 全新安装：`python -m flask --app app init-db`，然后 `python -m flask --app app create-admin`；课程演示可改用 `init-db --demo`。

迁移命令要求目标业务表为空，源 SQLite 的版本为 2、3、4 或 5 且外键检查通过。旧版源库没有菜品评价表或浏览记录表时按空记录处理。导入保留 ID、密码哈希和会话版本，逐表核对记录数及字段值，通过后统一提交；失败回滚已导入数据，建表结构会保留。请在导入期间停止项目，避免并发业务写入。再次导入非空数据库会被拒绝，不会覆盖业务数据。迁移只读原 SQLite 文件。

启动：`python serve.py`，访问 `http://127.0.0.1:5000/health` 检查连接。

## 使用 Docker 新建 MySQL（可选）

已有本机 MySQL 时无需使用此方式。若 3306 已被占用，应先调整 compose.yaml 中的本机端口和 MYSQL_PORT。

在上述环境变量之外设置 MYSQL_ROOT_PASSWORD，再执行：

```powershell
$rootCredential = Get-Credential -UserName root -Message '设置容器 MySQL root 密码'
$env:MYSQL_ROOT_PASSWORD = $rootCredential.GetNetworkCredential().Password
docker compose up -d --wait
```

容器数据保存在 mysql_data 卷中。随后执行初始化或迁移命令。

## 备份、恢复与旧库维护

`python -m flask --app app backup-db` 为 MySQL 生成一致性快照 SQL，保存到项目 backups/。备份含账号哈希等业务信息，应妥善保管；备份期间不要执行 DDL 操作。

恢复时使用 MySQL 客户端连接一个空数据库，在客户端内执行 `SOURCE C:/完整路径/备份文件.sql;`。迁移前的 SQLite 文件也会保留，可以用原始版本继续读取。

需要维护旧 SQLite 库时，可临时设置 `$env:XUNWEI_DB_BACKEND='sqlite'`；改回 MySQL 时设置为 mysql。现有自动化功能测试使用隔离 SQLite 临时库，MySQL 驱动适配测试验证参数绑定、结果读取和更新语句；真实 MySQL 业务测试可运行 `scripts/test_mysql.py`，需先为配置账号授予一个独立空测试库的权限，并通过 MYSQL_TEST_DATABASE 指定其名称（必须以 _test 结尾）；脚本会清空该测试库中的项目表。
