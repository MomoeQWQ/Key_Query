# Spatio-Textual Secure Search System (VPBRQSupL-inspired)

本项目实现了一个“可验证、抑制泄露”的空间-文本加密检索系统，灵感来源于 IEEE TIFS 2024《Beyond Result Verification: Efficient Privacy-Preserving Spatial Keyword Query With Suppressed Leakage》。系统以混淆布隆过滤器（GBF）、分布式多点函数（DMPF）、前缀受限 PRF（FC）和 XOR 同态 PRF（FX）为核心，支持在加密索引上进行多关键字查询，并完成“结果正确性”轻量验证，证明大小与数据规模无关。

---

## 主要特性

- 加密索引：GBF 将空间与关键词统一编码，Ke 派生的对象级 OTP 保证列式数据加密后仍可被云端按 XOR 合并。
- 查询隐私：PRP-based Cuckoo + DMPF 构造小域选择份额，多个 CSP 仅处理随机化的列份额，不暴露客户端真实访问模式。
- 结果验证：FX+HMAC 等式让客户端在聚合份额后验证云端行为，证明大小与对象数量无关，兼容空间与关键词双通道。
- 全链路演示：同时提供 offline_demo.py、offline_demo_spatial.py 与 online_demo 客户端+CSP 全流程脚本，便于复现论文方案。

---

## 仓库结构

- `GBF.py`：GBF 指纹/添加/查询。
- `DMPF.py`：按位选择比特分享的 MPF（`Gen(security_param, indices, domain_size, U)` / `Eval(key,j)`）。
- `SetupProcess.py`：构建认证索引（I_spa/I_tex）、一次性加密（Ke）、列聚合标签（sigma）、Kv→Ki 派生、XOR 同态 PRF FX。
- `SearchProcess.py`：仅关键词部分的按字节 XOR 聚合与证明份额生成（可扩展空间部分）。
- `convert_dataset.py`：记录对象化，标准化分词后逐词写入关键词 GBF；空间 GBF 保持接口。
- `QueryUtils.py`：查询编码/填充、规范化工具（`tokenize_normalized`）。
- `verification.py`：
  - `build_integrity_tags/verify_integrity`：离线完整性标签（HMAC 列标签）。
  - `verify_fx_hmac`：严格验证（FX(Ki,·)+HMAC 等式）。
- 演示入口：`offline_demo.py`（仅关键词）、`offline_demo_spatial.py`（空间∩关键词）。
- `conFig.ini`：参数配置。

---

## 安装与运行

- 依赖：Python 3.10+，`pandas`

```bash
pip install pandas
```

- 运行 Demo（非交互输入）

```bash
echo ORLANDO | python -u offline_demo.py
echo "ORLANDO; R: 28.3,-81.5,28.7,-81.2" | python -u offline_demo_spatial.py
```

或传参/交互：

```bash
python -u offline_demo.py "ORLANDO"
```

---

## 在线 Demo（Client + CSP）

1. `python online_demo/owner_setup.py`：重建 `aui.pkl`/`K.pkl`，确保 FX+HMAC 验证使用的 `sigma` 与最新代码同步。
2. `python online_demo/run_all.py "ORLANDO; R: 28.3,-81.5,28.7,-81.2"`：自动启动 3 台 CSP 服务端，客户端生成 PRP+Cuckoo+DMPF 选列份额并执行 FX+HMAC 验证。
   - 可用 `echo ORLANDO | python online_demo/run_all.py` 快捷验证仅关键词的查询。
3. 运行结果会显示 `[client] Verify: pass`/`fail` 及前 20 条匹配数据，用于验证整个流程。
4. 如果修改 Setup/verification 中的 FX/HMAC 计算或 sigma 生产逻辑，需重新执行 `owner_setup.py` 以生成新的 AUI/K。

---

## 配置说明（conFig.ini）

- `general.lambda`：安全参数（字节数，默认 16）。
- `general.s`：前缀长度参数（用于 FC 受限密钥）。
- `keyword_bloom_filter.size/hash_count/psi`：关键词 GBF 长度、哈希个数、单元比特数。
- `spatial_bloom_filter.*`：空间 GBF 参数（当前 Demo 未启用，可扩展）。
- `suppression.enable_padding/max_r_blocks/enable_blinding`：查询块填充与盲化开关（默认开启）。
- `spatial_grid.cell_size_lat/cell_size_lon`：将范围 R 离散为网格 cell token 的网格大小（单位度）。
- `cuckoo.*`：PRP-based Cuckoo 参数
  - `kappa_kw/load_kw/seed_kw`：关键词路径的候选桶数/负载系数/种子
  - `kappa_spa/load_spa/seed_spa`：空间路径的候选桶数/负载系数/种子

---

## 工作流（空间 + 关键词查询）

1. 预处理
   - 读取 CSV 数据，标准化分词，构造 “原始对象 + space/keyword GBF” 的 DB 项。
2. 索引构建 (Setup)
   - 使用 `Ke` 生成对应对象的 OTP，将 GBF 分段按列加密，得到 `I_spa`/`I_tex`。
   - 通过 `Kv` 派生 `Ki = FC_eval(Kv, i)`，并配合 FX 生成列标签 `sigma`，同时保留原始 GBF 段用于 FX 计算。
3. 查询准备 (Client)
   - 解析用户查询，获取规范化关键词 token 及空间区域 grid（`CELL:*`）。
   - 使用 PRP-based Cuckoo 选取小域列集合，并对关键词/空间路径分别执行 DMPF 分份。
4. CSP 评估
   - 每个 CSP 根据 `party_id` 份额访问 `I_spa`/`I_tex`，按 XOR 聚合对象向量和 `sigma` 份额，返回 Base64 编码结果。
5. 客户端合并与解密
   - XOR 合并各 CSP 份额，对每个 token 累加 pad 后解密对应 GBF 段，借助 `fingerprint` 判定命中。
   - 关键词 token 内部取 AND，空间 token 取 OR，组合得到最终结果。
6. FX+HMAC 验证
   - 逐 token 验证 `combined_proof` 是否等于 FX(Ki, 明文向量)、FX(Ki, pad 修正) 与 HMAC 项的 XOR 结果，确认云端未作弊。

---

## 性能提示

- 完整校验包含大量 HMAC/PRF 与按字节 XOR，Python 端 Demo 会牺牲速度以保证正确性与可读性。
- 可选的提速思路：仅遍历选列、将 `I_tex/sigma` 向量化成 `numpy.uint8`、缓存 Ki/PRF 块、预存关键词 pad 段等。

---

## 开发迭代记录

- v0（初始）
  - GBF、DMPF（数值型）、加密索引与简单查询；结果采用“非零即命中”的演示逻辑。
- v1（离线完整性）
  - `verification.py` 增加 HMAC 列标签与校验；新增 `offline_demo.py`。
- v2（抑制泄露）
  - 查询块填充（padding）、结果盲化（blinding）；README/结构梳理。
- v3（论文对齐：密态 XOR 路径）
  - DMPF 改为“按位选择比特分享”；`SearchProcess` 改为按字节 XOR 聚合；Demo 解密与指纹比对，输出可读列表，仅包含相关项。
- v4（严格验证）
  - 实现 FX(Ki,·)+HMAC 等式验证；用 `Kv→Ki`、FX XOR 同态与 HMAC 聚合项完成轻量证明校验（与对象规模无关）。

---

## 未来工作

- 增量更新与撤销：提供动态数据后的 pad/sigma 重计算方案。
- 网络部署：添加 TLS/认证层和防重放机制，提升 CSP 之间的通讯安全性。
- 性能工程：向量化 PRF/HMAC、采用并行或 C/C++ 扩展以支撑大数据量。

## 许可证与联系

- 许可证：MIT
- 联系方式：
  - 邮箱：pjc040127@gmail.com
  - GitHub：https://github.com/MomoeQWQ/Key_Query
