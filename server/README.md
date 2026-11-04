# FastAPI + SQLite 后端

为同目录的 Vue 工程提供数据，数据库文件：`data/market.db`（`code/market-app/data/market.db`）。

## 一键启动（推荐）

在 `code/market-app` 目录执行：

```powershell
npm run demo
```

或双击 `start-demo.cmd`。

脚本会自动：

1. 检查 Python / FastAPI / Node 依赖；
2. 数据库不存在时自动初始化；
3. 启动 FastAPI（127.0.0.1:8000）；
4. 启动 Vite（127.0.0.1:5173）；
5. 关闭前端时自动停止本次启动的 FastAPI。

## 手动启动

```powershell
cd D:\318-Work\UP\ai\价格预测\code\market-app\server
pip install -r requirements.txt

python seed.py --reset
uvicorn app:app --host 127.0.0.1 --port 8000 --reload
```

前端另开终端：

```powershell
cd D:\318-Work\UP\ai\价格预测\code\market-app
npm run dev
```

- API 文档：http://127.0.0.1:8000/docs
- 健康检查：http://127.0.0.1:8000/api/health
- 如果 `dist` 存在，后端也会直接托管构建后的 Vue 页面。

## 数据表

- `market_sources`、`materials`、`material_aliases`
- `source_material_configs`、`source_regions`（网站物料采集配置、省市字典）
- `source_sync_settings`（网站总开关、是否接入自动解析）
- `market_quotes`（含 `product_id`）、`v_quote_rolling`
- `pricing_templates`、`pricing_template_factors`
- `pricing_params`、`pricing_param_sources`
- `calc_schedules`、`calc_runs`、`calc_results`
- `operation_logs`、`api_call_logs`、`sync_state`

## 主要接口

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/bootstrap` | 一次返回页面所需的全部数据（含 `collectConfigs`） |
| GET | `/api/quotes` | 行情台账分页查询：`page`、`pageSize`（10/20/50/100）、`source`、`category`、`startDate`、`endDate`、`keyword` |
| GET | `/api/health` | 健康检查 |
| GET | `/api/sync/status` | 同步状态：配额、上次结果、逐物料明细（前端轮询用） |
| GET | `/api/collect/regions` | 省市字典（首次或过期时拉取富宝） |
| POST | `/api/collect/regions/refresh` | 强制刷新省市字典 |
| GET | `/api/collect/configs` | 采集配置列表 + 同步状态 |
| GET | `/api/collect/overview` | 按网站汇总开关、物料数、今日同步数 |
| POST | `/api/collect/run` | 手动触发行情采集（后台低频执行） |
| POST | `/api/sources/{id}/toggle` | 网站同步总开关 |
| POST | `/api/collect/configs/batch-toggle` | 按网站批量启用/停用物料 |
| POST | `/api/collect/search` | 关键词 + 省市搜索富宝产品（1 次搜索 + 1 次批量解析） |
| POST | `/api/collect/configs` | 新增配置（市可空、网站物料自动创建；`syncHistory=true` 时保存后立即回补） |
| PUT | `/api/collect/configs/{id}` | 修改配置 |
| POST | `/api/collect/configs/{id}/toggle` | 启用/停用 |
| POST | `/api/collect/configs/{id}/verify` | 重新校验富宝产品 |
| POST | `/api/collect/configs/{id}/backfill` | 后台低频回补历史 |
| DELETE | `/api/collect/configs/{id}` | 软删除配置（行情保留） |
| GET | `/api/collect/token` | 富宝 token 状态（掩码、有效期、是否有效、是否启用自动续期）；过期且已配置账号时会顺带自动登录 |
| POST | `/api/collect/token` | 前台录入 `AUTH_COOKIE`，写入 `auth_token.txt`（无 BOM），记录操作日志 |
| POST | `/api/collect/token/refresh` | 用已保存账号立即重新登录，刷新 token |
| GET | `/api/collect/credentials` | 富宝账号登录状态（只返回掩码用户名，不返回密码） |
| POST | `/api/collect/login` | 用户账号登录：验证用户名/密码并获取 token，再用 Windows DPAPI 加密保存到 `cred.dat`，同时启用自动续期 |
| POST | `/api/collect/credentials` | 同上（兼容旧调用） |
| DELETE | `/api/collect/credentials` | 退出账号并关闭自动续期（已获取 token 保留到自然过期） |
| POST | `/api/mappings/{id}/toggle` | 启用/停用映射（计价规则；不影响行情采集） |
| POST | `/api/mappings` | 新增映射（系统物料 XT + 爬虫采集配置 + 调整值/系数） |
| PUT | `/api/mappings/{id}` | 编辑映射的调整值/系数/状态 |
| POST | `/api/mappings/batch-import` | 批量导入：系统物料编码, productId, 调整值, 系数 |
| POST | `/api/pricing-params` | 新增定价参数（旧模型，已停用，仅保留兼容） |
| PUT | `/api/pricing-params/{id}` | 保存物料定价参数（旧模型） |
| GET | `/api/pricing-rules` | 物料计价规则（按网站物料分组，含上一完整周均价与预览售价） |
| POST | `/api/materials` | 新增物料（默认公司系统物料 XTxxxxx，同名同类型幂等） |
| POST | `/api/pricing-rules` | 新增网站物料 → 公司系统物料规则 |
| PUT | `/api/pricing-rules/{id}` | 保存规则的固定调整值/调价系数/状态 |
| POST | `/api/pricing-rules/group/{sourceConfigId}/coefficient` | 统一本组调价系数 |
| PUT | `/api/templates/{id}` | 保存定价模板 |
| POST | `/api/results/{id}/review` | 复核/驳回单条结果 |
| POST | `/api/results/batch-approve` | 批量复核通过 |
| POST | `/api/schedules/{id}/run` | 执行计价并生成批次/结果 |

所有写操作都会同步写 `operation_logs`。

## 数据路径

- 数据库：`code/market-app/data/market.db`
- 爬虫 CSV / 同步状态：项目根目录 `data/`（`SOURCE_DATA_DIR`）
- 抓取后增量导入：

```powershell
python code\market-app\server\sync_db.py
```

或直接运行 `code\sync_f139.ps1`，它会依次执行：抓取 -> SQLite -> 静态 HTML。

## 说明

- 当前行情数据由 `data/f139_历史_diid163321.csv`、`data/f139_历史_diid32105.csv` 导入；
- 网站物料：WB00001 清远机生铝（289 个交易日）、WB00002 佛山黄杂铜（287 个交易日）；
- 公司系统物料：XT00001 铝、XT00002 轻杂铝、XT00003 铝质车底盘、XT00004 废电线、XT00005 混铝铜废电线；
- `market_quotes` 用唯一索引保证同一来源、diid、价格分类、日期只存一行；
- 物料计价规则存于 `material_pricing_rules`：`计算售价 =（上一完整周均价 + 固定调整值）× 调价系数`，保留两位小数；
- 上一完整周 = 周一至周日，只用周一至周五的报价计算周均价（周六日无价格更新）；
- 台账的 `rolling_7d_avg` 仅用于逐日展示，不参与计价。

## 同步状态与配额

- 每日调用上限统一取 `source_sync_settings.daily_cap`（富宝当前 20），初始化与日常共用同一个“今日已调用”计数；
- 每日同步对全部启用物料只发 **1 次批量历史请求**（`productIds` 逗号拼接，窗口近 7 天，周一核对 13 天），不再按物料逐个请求；
- 只有真正抓取成功时才更新 `last_snapshot_at`，不会再出现“没有请求也显示刚同步”；
- `last_run_result` 取值：`success / partial / failed / skipped`；逐物料结果写入 `last_run_materials` 与 `last_run_summary`；
- 配额用尽时 `POST /api/collect/run` 与回补接口直接返回 409，不会发起外部请求；
- 手动采集后前端轮询 `/api/sync/status`（含 `collectRunning`），结束后自动刷新并提示成功 / 部分完成 / 失败；
- 回补天数 N = `今天−N ~ 今天`，每 60 天一个窗口（N=30 → 1 次，N=300 → 6 次，N=365 → 7 次）；
- 把 N 调大时会在已有历史基础上继续往更早补，不会删除已有数据；调小只更新展示天数；
- 编辑配置保存时若天数调大，同样会自动启动续补（`PUT /api/collect/configs/{id}` 带 `syncHistory=true`）。
