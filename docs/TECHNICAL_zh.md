# 技术文档（中文）

## 概述

本项目实现来源于 VPBRQSupL 思想的“可验证、抑制泄露”的空间-文本加密检索原型。核心组件包括：
- 混淆布隆过滤器（GBF）
- 分布式多点函数（DMPF，采用按位选择比特分享）
- 前缀受限 PRF（FC.Cons/FC.Eval）与 XOR 同态 PRF（FX）

Demo 当前实现“关键词部分”的密态查询、解密匹配与严格验证（FX+HMAC 等式），空间部分保留接口，可平滑扩展。

---

## 数据编码

- 关键词与空间维度均可用 GBF 表示；Demo 仅使用关键词 GBF。
- 关键词文本先“标准化分词”：大写 + 仅保留字母数字，丢弃其他字符；随后逐词加入 GBF。
- GBF 参数：长度 `m`、哈希个数 `k`、单元位数 `psi`（字节数为 `psi/8`）。

---

## Setup（索引构建）

设数据库包含 `n` 个对象，ID 集合为 `{id_i}`。

1) 一次性加密（Ke）
- 对每个对象 `i`：`pad_i = F(Ke, (str(i)||id_i), (m1+m2)*bytes)`。
- 关键词矩阵 `I_tex` 通过对各列与 `pad_i` 的列片段异或得到（按字节 XOR）。

2) 受限 PRF（FC）与对象密钥 Ki
- 选择前缀 `v`，计算 `Kv = FC.Cons(K_main, v)`；
- `Ki = FC.Eval(Kv, i)`。

3) XOR 同态 PRF（FX）
- 对输入位串 `u`，`FX(K, u) = ⨁_{u_b=1} PRF(K, b)`；
- 满足 `FX(K, u⊕v) = FX(K, u) ⊕ FX(K, v)`。

4) 列聚合标签（sigma）
- 对每一列 `j`：
  - `sigma[j] = (⨁_i FX(Ki, I[:,j])) ⊕ HMAC(Kh, (j+m1)||cat_ids)`，
  - 其中 `cat_ids = id_1||…||id_n`。

最终得到认证索引（含加密矩阵与 `sigma`）。

---

## 查询（关键词 + 空间路径）

1) 规范化查询词；对每个词 `t` 计算 GBF 位置集合 `S(t)`。
2) 将范围 `R` 离散为网格 cell token（`CELL:R{row}_C{col}`），每个 cell 也有对应的 `S(cell)`。
3) PRP-based Cuckoo 分桶：将 `S(token)` 分配到 `M≈load*|S|` 个桶，每个元素有 `κ` 个候选桶（由 PRP(ζ, ·) 决定），选负载最轻的桶存放。
4) DMPF 小域聚合：
- 对每个桶，在“桶大小”的小域内生成按位选择比特分享，并对该桶内选列执行按字节 XOR 聚合（结果与证明）；
- 跨桶 XOR 得到 token 级别结果与证明。
5) 客户端合并
- 对每个 token（关键词与空间 cell），将各方份额按字节 XOR 合并；关键词取 AND，空间 cell 取 OR，最终为 AND(keywords) ∩ OR(spatial)。

---

## 解密与匹配

- 对词 `t` 与对象 `i`：
- 计算 `pad_acc(i,t)`：对 `pad_i` 在所选列（关键词或空间）的片段按字节 XOR 的累积；
  - 明文向量 `plain(i,t) = combined_vec(i,t) ⊕ pad_acc(i,t)`；
- 若 `plain(i,t)` 等于 `GBF.fingerprint(t)`，则对象 `i` 对该 token 匹配；多个关键词按 AND，多个空间 cell 按 OR，最终取 AND(keywords) ∩ OR(spatial)。

---

## 严格验证（FX+HMAC 等式）

对每个查询词 `t`，选择集合为 `S(t)`，验证：

```
combined_proof(t)
  = (⨁_i FX(Ki, plain(i,t))) ⊕ (⨁_i FX(Ki, pad_acc(i,t))) ⊕ N_S,ID
```

其中：
- `Ki = FC.Eval(Kv, i)`；
- `N_S,ID = ⨁_{j ∈ S(t)} HMAC(Kh, (j+m1)||cat_ids)`；
- `combined_proof(t)` 为各方证明份额 XOR 合并结果。

该验证与数据规模无关，仅与词个数、`lambda` 有关。

---

## 泄露抑制

- 访问模式：DMPF 跨多方分享，各方仅见份额；
- 搜索模式：DMPF 份额含随机性；可选固定查询块数量（padding）与结果盲化（合并时抵消）。

---

## 参数与权衡

- 增大 `m/k/psi` 可降低 FP，但增加 CPU 与内存；
- `lambda` 控制 PRF/HMAC 输出长度；
- Python Demo 为了清晰而牺牲速度：可通过“仅遍历选列、向量化 XOR、缓存 `Ki` 与 `pad` 片段”等方式提速。

---

## 迭代历程（Changelog）

- v0：GBF + 数值型 DMPF，非零即命中的演示路径。
- v1：增加 HMAC 列标签与离线校验；引入 `offline_demo.py`。
- v2：抑制泄露（padding/blinding），清理结构。
- v3：论文对齐（XOR 路径）：DMPF 按位选择、按字节 XOR 聚合、解密与指纹对比，列表仅含相关项。
- v4：严格验证（FX(Ki,·)+HMAC 等式），XOR 同态 FX 与完整等式校验。

---

## 空间部分扩展（展望）

- 采用空间 GBF（自有 `m1/k1`）并复用当前 DMPF + XOR 聚合框架；
- 或按论文引入 PRP-based Cuckoo hashing + DMPF 的优化方案，范围内检索效率更高。

---

## 注意事项

- Demo 代码更注重可读性与正确性，实际部署建议在 XOR 聚合、FX 计算与 pad 处理处进行向量化/缓存/并行化。
- 标准化规则需在数据侧与查询侧严格一致，否则会出现“明文匹配为真/密态路径为假”的偏差。
