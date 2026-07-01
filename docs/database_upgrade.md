# 数据库迁移与升级说明

## 目标

本项目自本次更新起使用 `Flask-Migrate + Alembic` 管理数据库结构变更。

适用规则：

- 服务器上的数据库数据保留，不重建、不覆盖。
- 本地测试数据库仅用于验证，不需要迁移到服务器。
- 以后每次服务器更新代码后，通过 `flask db upgrade` 应用结构变更。

## 首次接入迁移体系

如果服务器数据库是本项目旧版本留下的现有库，第一次上线这套迁移体系时执行：

```powershell
$env:FLASK_APP = "wsgi:app"
flask db stamp bc5a66367a8f
flask db upgrade
```

说明：

- `stamp` 只写入迁移版本号，不改动现有表结构。
- `upgrade` 会执行本次新增的标准化迁移。

## 后续常规更新

以后每次服务器更新代码后执行：

```powershell
$env:FLASK_APP = "wsgi:app"
flask db upgrade
```

## 新环境初始化

如果是全新环境，可选两种方式：

1. 导入仓库根目录的 `specimen_db.sql`
2. 然后执行：

```powershell
$env:FLASK_APP = "wsgi:app"
flask db stamp 5a5921108376
```

或者由开发侧继续补充后续从零建库的完整迁移链路。

## 本次标准化迁移内容

- `page_content.created_at` 新增并回填历史数据
- `specimen_category.code` 改为非空，历史空值自动回填为 `CAT{id}`
- `specimen.latin_name` 新增索引
- `specimen.longitude` / `specimen.latitude` 统一为 `Numeric(10, 6)`

## 运行入口

生产环境不要直接运行 `python run.py`。

推荐：

```powershell
waitress-serve --listen=127.0.0.1:8443 wsgi:app
```
