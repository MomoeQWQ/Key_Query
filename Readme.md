# Spatio-Textual Secure Search System (VPBRQSupL-inspired)

本项目实现了一个“可验证、抑制泄露”的空间-文本加密检索系统，灵感来源于 IEEE TIFS 2024《Beyond Result Verification: Efficient Privacy-Preserving Spatial Keyword Query With Suppressed Leakage》。系统以混淆布隆过滤器（GBF）、分布式多点函数（DMPF）、前缀受限 PRF（FC）和 XOR 同态 PRF（FX）为核心，支持在加密索引上进行多关键字查询，并完成“结果正确性”轻量验证，证明大小与数据规模无关。

---

## 主要特性

- 抑制泄露的密态查询
  - 关键词采用 GBF 编码；云端按字节 XOR 聚合仅返回对象级向量分享与轻量证明份额。
  - DMPF 以“按位选择比特分享”隐藏访问/搜索模式，参与方结果按位 XOR 合并。
- 轻量结果验证（FX+HMAC 等式）
  - 客户端用 Kv→Ki 派生密钥，对解密后的对象向量进行 FX 聚合，并与 HMAC 聚合项组成等式校验。
  - 证明大小与对象数量无关。
- 端到端 Demo
  - `offline_demo.py`：关键词路径演示（仅 W*）。
  - `offline_demo_spatial.py`：联合查询演示（R ∩ W*），包含范围离散为网格 cell、PRP+Cuckoo+DMPF 小域聚合、解密与严格验证。
- 关键词标准化
  - 统一大小写与字符集（仅字母数字），保证数据侧与查询侧一致性。

---

## 仓库结构

- `GBF.py`：GBF 指纹/添加/查询。
- `DMPF.py`：按位选择比特分享的 DMPF（`Gen(security_param, indices, domain_size, U)` / `Eval(key,j)`）。
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

## 工作流（关键词查询）

1. 预处理
   - 读取 CSV（如 `us-colleges-and-universities.csv`），抽取 `IPEDSID/Geo Point/NAME/ADDRESS/CITY/STATE`。
   - 标准化分词（大写+仅字母数字），逐词写入关键词 GBF；空间 GBF 保留接口。
2. 索引构建（Setup）
   - 一次性加密：`Ke` 生成每对象 pad，按列异或得到 `I_tex`（加密 GBF 矩阵）。
   - 前缀受限 PRF：`Kv = FC.Cons(K_main, v)`，`Ki = FC.Eval(Kv, i)`。
   - 列标签：`sigma[j] = XOR_i FX(Ki, I[:,j]) XOR HMAC(Kh,(j+m1)||cat_ids)`。
3. 查询（Search）
   - 标准化查询词；每词算 GBF 位置集合 S。
- DMPF 生成按位选择比特分享；云端对选列执行按字节 XOR，返回“对象级向量份额”与“证明份额”。
- 引入 PRP-based Cuckoo hashing：将选列集合分桶，在每个桶内用小域 DMPF，减少域规模并提升效率（关键词与空间路径均适用）。
4. 合并与解密（客户端）
   - XOR 合并各方份额，得到每词的对象级聚合向量与证明；
   - 用 `Ke` 在相同选列上累积 pad 并解密；与 `fingerprint(token)` 对比（AND 语义）得到命中对象；
5. 严格验证（FX+HMAC）
- 校验 `combined_proof == XOR_i FX(Ki,res[i]) XOR XOR_i FX(Ki,pad_acc(i)) XOR N_S,ID`（对每个 token；关键词与空间 cell 统一处理）。

---

## 性能提示

- 完整校验包含大量 HMAC/PRF 与按字节 XOR，Python 端 Demo 会牺牲速度以保证正确性与可读性。
- 提速思路（可选）：仅遍历选列、将 `I_tex/sigma` 向量化成 `numpy.uint8`、缓存 Ki/PRF 块、预存关键词 pad 段等。

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

- 引入空间范围（R）与关键词联合查询（当前 Demo 仅关键词）。
- 更高效的实现：向量化、缓存、并行化与 C 扩展。
- 适配更多数据集与动态更新。

---

## 许可证与联系

- 许可证：MIT
- 联系方式：
  - 邮箱：pjc040127@gmail.com
  - GitHub：https://github.com/MomoeQWQ/Key_Query
