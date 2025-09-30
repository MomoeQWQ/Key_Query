# Online Demo (Client + CSPs)

## Steps / 操作步骤
1. Prepare AUI and keys / 生成索引
`
python online_demo/owner_setup.py
`
调用 secure_search.build_index_from_csv 生成 online_demo/aui.pkl 与 online_demo/K.pkl。修改 FX/HMAC 或配置后，请重跑本步骤。

2. Start CSP servers and run client / 启动 CSP 与客户端
`
python online_demo/run_all.py "ORLANDO; R: 28.3,-81.5,28.7,-81.2"
`
启动三个 CSP（8001/8002/8003）并运行客户端。期望看到 [client] Verify: pass，打印最多 20 条匹配。

Keyword-only / 仅关键词：
`
echo ORLANDO | python online_demo/run_all.py
`

### Custom options / 自定义参数
`
python online_demo/client.py \
  --aui online_demo/aui.pkl \
  --keys online_demo/K.pkl \
  --config conFig.ini \
  --csp http://127.0.0.1:8001 http://127.0.0.1:8002 http://127.0.0.1:8003 \
  --query "ORLANDO; R: 28.3,-81.5,28.7,-81.2"
`
支持自定义索引文件路径与 CSP 端点列表。

## Design / 设计要点
- CSP (csp_server.py) 读取 ui.pkl 并暴露 /eval，返回 XOR 份额与 FX 证明份额。
- Client (client.py) 使用 secure_search.query.prepare_query_plan 完成分词、空间离散化与 PRP+Cuckoo+DMPF 份额生成。
- 使用 combine_csp_responses 合并响应，decrypt_matches 解密匹配，
un_fx_hmac_verification 验证 FX+HMAC 等式。

## Configuration / 配置
- Bloom filter 尺寸/哈希数、安全参数 lambda
- Cuckoo 参数 cuckoo.*
- 网格参数 spatial_grid.*

## GUI Alternative / 图形界面
1) python gui_demo/server_gui.py —— 选择 ui.pkl、设端口并启动；
2) python gui_demo/client_gui.py —— 选择 ui.pkl/K.pkl/conFig.ini/数据集，填写端点与查询并运行。

CLI 与 GUI 共用 secure_search 接口。


## Multi-keyword Query / ????????
- ?????????? AND????`ORLANDO ENGINEERING UNIVERSITY`?
- ???????`...; R: 28.3,-81.5,28.7,-81.2`???????? cell??? OR?
