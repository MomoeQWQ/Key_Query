# Spatio-Textual Secure Search System (VPBRQSupL-inspired)

## Overview / 项目概述
Prototype implementation of a verifiable, leakage‑suppressed spatial keyword search scheme inspired by the 2024 IEEE TIFS paper "Beyond Result Verification: Efficient Privacy-Preserving Spatial Keyword Query With Suppressed Leakage". Data is encoded with Garbled Bloom Filters (GBF); queries rely on PRP-based Cuckoo hashing, Distributed Multi-Point Function (DMPF) shares, and FX+HMAC proofs so that multiple CSPs can answer encrypted queries while the client verifies correctness.

该项目复现 2024 年 IEEE TIFS 论文《Beyond Result Verification: Efficient Privacy-Preserving Spatial Keyword Query With Suppressed Leakage》的核心思路，实现可验证、抑制泄露的空间+关键词检索原型。系统采用 GBF 编码，结合 PRP+Cuckoo 分桶、DMPF 份额与 FX+HMAC 证明，在多方 CSP 场景中既隐藏访问模式，又能让客户端严格验证结果正确性。

## Highlights / 核心特性
- Encrypted index / 加密索引：SetupProcess 通过 F(Ke, ·) 为每条记录派生一次性填充，按列加密空间/文本 GBF 段，并生成列标签 sigma。
- Query privacy / 查询隐私：secure_search.query 封装 PRP+Cuckoo 分桶 + DMPF，使 CSP 仅见随机化列选择并返回 XOR 份额。
- Lightweight verification / 轻量验证：erification.verify_fx_hmac 结合 Kv→Ki 与 HMAC，证明大小与数据规模无关。
- Modular package / 模块化封装：新增 secure_search 包，暴露索引与查询 API，便于 CLI、GUI 与服务端复用。
- GUI demos / 图形界面：gui_demo 提供基于 Tkinter 的客户端与 CSP 控制台，模拟 C/S 部署流程。

## Repository Layout / 仓库结构
- secure_search/
  - indexing.py：索引构建/保存/加载（build/save/load）
  - query.py：查询计划、CSP 响应合并、解密、FX+HMAC 验证
- online_demo/：命令行在线演示（CSP + client）
- gui_demo/：图形化客户端与 CSP 控制台
- offline_demo.py、offline_demo_spatial.py：离线关键词或空间+关键词演示
- 核心模块：GBF.py、DMPF.py、SetupProcess.py、erification.py、QueryUtils.py、convert_dataset.py

## Setup / 环境准备
1. Python 3.10+
2. Install / 安装依赖：
`
pip install pandas
`

## Build the Index / 构建索引
`
python online_demo/owner_setup.py
`
Loads the CSV and writes online_demo/aui.pkl + online_demo/K.pkl。修改 SetupProcess/erification 或配置后请重跑本步骤。

## Command-Line Demos / 命令行演示
- Offline keyword / 离线关键词：
`
python offline_demo.py "ORLANDO"
`
- Offline spatial+keyword / 离线空间+关键词：
`
python offline_demo_spatial.py "ORLANDO; R: 28.3,-81.5,28.7,-81.2"
`
- Online CSP + client / 在线 CSP 与客户端：
`
python online_demo/run_all.py "ORLANDO; R: 28.3,-81.5,28.7,-81.2"
`
启动 3 个 CSP（8001/8002/8003）并运行客户端。仅关键词测试可：
`
echo ORLANDO | python online_demo/run_all.py
`

## GUI Workflow / 图形界面流程
1) python gui_demo/server_gui.py：选择 ui.pkl，设置端口并启动服务器。
2) python gui_demo/client_gui.py：选择 ui.pkl、K.pkl、conFig.ini 与数据集，填写端点与查询，运行查看 FX+HMAC 验证与前 20 条匹配。

## API Cheat Sheet / API 速查
`
from secure_search import (
    build_index_from_csv,
    save_index_artifacts,
    load_index_artifacts,
    prepare_query_plan,
    combine_csp_responses,
    decrypt_matches,
    run_fx_hmac_verification,
)
`
`
aui, keys = build_index_from_csv(csv_path, config_path)
plan = prepare_query_plan(query_text, aui, config)
combined_vecs, combined_proofs = combine_csp_responses(plan, responses, aui)
_, hits = decrypt_matches(plan, combined_vecs, aui, keys)
ok = run_fx_hmac_verification(plan, combined_vecs, combined_proofs, aui, keys)
`

## Notes / 注意事项
- 原型使用 Python http.server；生产应增加 TLS、鉴权、随机数与向量化 XOR。
- 修改 pad/密钥派生逻辑会影响 sigma，需重新生成索引（重跑 owner_setup）。

## License / 许可证
MIT


## Multi-keyword Query / ????????
- ???????????? AND????`ORLANDO ENGINEERING UNIVERSITY`?
- ??????????? `R: lat_min,lon_min,lat_max,lon_max`???`ORLANDO ENGINEERING; R: 28.3,-81.5,28.7,-81.2`?
- ??????? AND??? cell ??? OR???????????? AND?
