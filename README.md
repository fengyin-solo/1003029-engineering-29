# 通信基站运维管理平台

面向通信基站站点入网、动力环境监控、天馈巡检、发电保障与退网拆站的一体化基站运维管理后台。

这是一个前后端分离的管理平台：前端 Vue 3 + Vite + TypeScript，后端 FastAPI（Python）。
两边各自独立启动，前端 dev server 已关掉自动打开页面，启动后按终端打印的地址手工打开。

## 目录结构

```text
.
├── frontend/                 Vue 3 + Vite + TypeScript 前端
│   ├── src/views/            每个业务模块一个页面
│   ├── src/api/              统一请求封装
│   ├── src/stores/           会话与筛选状态
│   └── vite.config.ts        dev server 配置（open: false）
├── backend/                  FastAPI（Python） 后端
│   ├── app/routers/          每个业务模块一组接口
│   ├── app/services/         业务规则与状态流转
│   └── app/store.py          内存数据仓库与示例数据
├── .gitignore
└── docker-compose.yml
```

## 启动

### 后端

```bash
cd backend
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
./run.sh
```

健康检查：`curl http://127.0.0.1:8000/api/health`（活没活）
就绪检查：`curl http://127.0.0.1:8000/api/ready`（好没好，见下文「就绪探测」）

### 前端

```bash
cd frontend
npm install
npm run dev
```

前端默认监听 `http://127.0.0.1:5173/`，dev server 不会自动打开浏览器，
需要自己访问。`/api` 由 vite 代理到后端 `http://127.0.0.1:8000`。

页面有就绪门：探到后端 `/api/ready` 通过才挂载，没通过时显示等待页并自动重试，
不用手动刷新。

## 就绪探测

服务"好没好"不看终端，看就绪地址：`GET /api/ready`。

- 200 表示就绪；503 表示未就绪。响应里 `failed` 点出没过的是哪项，`checks` 带逐项明细。
- 检查按 `port → deps → proxy` 顺序成链，前一项没过，后面的项记为待探测：
  - `port`：后端配置的监听地址（`APP_HOST:APP_PORT`）可连接；
  - `deps`：`requirements.txt` 里的依赖装齐、版本达标；
  - `proxy`：前端 dev server（`APP_PROXY_URL`）的 `/api` 代理确实指回本服务
    （代理转发时带 `x-proxied-by` 标记头，防止把地址直接指到后端造成误报）。
- 断点续探：已通过的项进程内缓存，重试只从未通过的项接着探；探测全部只读，
  重复调用不会重复装依赖、不会重复拉起任何服务。

同一个就绪结论，这些入口看到的一致：

| 入口 | 用法 |
| --- | --- |
| 直连后端 | `curl http://127.0.0.1:8000/api/ready` |
| 经前端代理 | `curl http://127.0.0.1:5173/api/ready` |
| 本地命令 | `make ready`（即 `python -m app.readiness`，未就绪时退出码非 0） |
| docker-compose | backend 容器的 healthcheck 跑的就是这套检查 |

换机器/换端口时用环境变量对齐：`APP_HOST`、`APP_PORT`、`APP_PROXY_URL`（后端），
`VITE_PROXY_TARGET`（前端代理目标），取值见 `.env.example`。默认值不变，
老启动命令（`run.sh`、`make backend`、`npm run dev`）不用改。

## 业务模块

| 模块 | 目录 | 业务对象 | 主要字段 |
| --- | --- | --- | --- |
| 基站台账 | `site` | 基站 | 基站编号、基站名称、基站类型 |
| 铁塔管理 | `tower` | 铁塔 | 铁塔编号、铁塔类型、设计高度 |
| 动力配套 | `power` | 电源设备 | 设备编号、设备类型、额定功率 |
| 蓄电池组 | `battery` | 蓄电池组 | 电池组编号、电池类型、额定容量 |
| 发电机组 | `genset` | 发电机组 | 机组编号、机组型号、额定功率 |
| 开关电源 | `rectifier` | 开关电源 | 电源编号、额定功率、所属站点 |
| 空调管理 | `ac` | 空调 | 空调编号、空调类型、制冷量 |
| 天馈系统 | `antenna` | 天馈设备 | 天馈编号、天线类型、工作频段 |
| 传输设备 | `transmission` | 传输设备 | 设备编号、传输类型、带宽容量 |
| 馈线巡检 | `feeder` | 馈线 | 馈线编号、所属站点、馈线长度 |
| 防雷接地 | `lightningprot` | 防雷装置 | 装置编号、所属站点、接地电阻 |
| 消防设施 | `firealarm` | 消防设施 | 设施编号、设施类型、所属站点 |
| 门禁管理 | `dooraccess` | 门禁记录 | 门禁编号、所属站点、开门方式 |
| 巡检作业 | `patrol` | 巡检任务 | 任务编号、巡检站点、巡检人员 |
| 油料管理 | `fuel` | 油料记录 | 记录编号、所属站点、油料类型 |
| 场租合同 | `rental` | 场租合同 | 合同编号、站点名称、出租方 |
| 电费管理 | `electricbill` | 电费记录 | 记录编号、所属站点、电表读数 |
| 拆站管理 | `demolition` | 拆站任务 | 任务编号、拆除站点、拆除原因 |
| 应急通信 | `emergency` | 应急保障 | 保障编号、保障类型、保障地点 |
| 节能改造 | `energyeff` | 节能项目 | 项目编号、所属站点、改造内容 |

## 约定

- 每个模块的前端页面在 `frontend/src/views/<模块>/index.vue`，后端接口在
  `backend/app/routers/<模块>.py`，业务规则在 `backend/app/services/<模块>.py`。
- 列表接口统一返回 `{ items, total, page, size }`，动作接口统一返回 `{ ok, message }`。
- 状态流转只允许在 `app/services` 里改，路由层不做业务判断。
- 就绪结论只认 `/api/ready` 这一套检查（`backend/app/readiness.py`）；
  新加的入口（脚本、流水线、健康检查）复用它，不另写一套判断。
