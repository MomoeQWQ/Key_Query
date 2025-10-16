# 技术文档 / Technical Notes

> 本文档概述 ST-VLS（Spatio-Temporal Secure Search with Verifiable Leakage Suppression）项目的系统设计、核心算法实现与实验结果，并提供中文/英文双语说明。

---

## 1. 概述 / Overview

- **目标 Goal**：在不可信多云环境中，实现对加密时空数据的多关键字检索、泄露抑制与结果可验证。The project demonstrates how encrypted spatio-temporal queries can be executed with leakage suppression and client-side verification across multiple CSPs.
- **核心技术 Core techniques**：Garbled Bloom Filter (GBF)、Distributed Multi-Point Function (DMPF) secret sharing、FX+HMAC 证明、PRP-based Cuckoo hashing，以及可选的 LLM 语义扩展。These components are packaged in the Python module `secure_search`.

---

## 2. 系统实体与目录结构 / Entities & Repository Layout

| 实体 / Entity | 说明 Description |
| --- | --- |
| 数据拥有者 DO | 构建密态索引、分发密钥；脚本 `online_demo/owner_setup.py`。 |
| 云服务商 CSP | 保持索引份额，响应查询；实现见 `online_demo/csp_server.py` 与 GUI 服务器。 |
| 客户端 Client | 生成查询计划、聚合结果并验证；参考 `online_demo/client.py` 与 `gui_demo/client_gui.py`。 |
| AI 扩展模块 | 可选的 LLM 扩展与关键词裁剪逻辑；位于 `secure_search/query_expansion.py`、`ai_pruning/`。 |

> 完整仓库结构请查阅根目录 `Readme.md` 的“Repository Layout”表格。

---

## 3. 密态索引流程 / Authenticated Index Pipeline

1. **数据预处理 Data preparation**：`prepare_dataset.py` 将 CSV 记录映射为包含经纬度、标签的 `SpatioTextualRecord`。
2. **GBF 编码 GBF encoding**：`convert_dataset.py` 为每条记录构建关键词/空间 GBF 数组。Keyword tokens are uppercase alphanumeric strings via `QueryUtils.tokenize_normalized`.
3. **一次性掩码 One-time pads**：`SetupProcess.Setup` 生成 `pad_i = F(Ke, str(i)||id_i)`，用以掩码 GBF 列数据并得到加密矩阵 `Ebp`, `EbW`。
4. **受限 PRF 密钥 Object keys**：通过 `FC_Cons`/`FC_Eval` 派生 `Kv`、`Ki`，用于后续 FX 计算。
5. **列认证标签 Column tags**：对每列计算

   ```
   sigma[j] = (⊕_i FX(K_i, col_i[j])) ⊕ HMAC(K_h, label_j || cat_ids)
   ```

   其中 `cat_ids` 为所有记录 ID 的拼接。
6. **产出索引 Output**：索引结构保存加密矩阵与 `sigma`；键材料 `(K_e, K_v, K_h)` 通过 `save_index_artifacts` 落盘。

---

## 4. 查询与验证 / Query & Verification Flow

1. **查询规范化 Normalisation**：`secure_search.query.prepare_query_plan` 将输入拆分为关键词与可选的空间范围 token。范围 `R` 会被离散化为栅格 cell（`CELL:R{row}_C{col}`）。
2. **Cuckoo 分桶 Bucketing**：针对每个 token 的 GBF 位置集合 `S(token)`，使用 PRP(seed) 生成 κ 个候选桶并选用负载较轻者，保持均匀访问模式。
3. **DMPF 份额生成 Secret sharing**：`DMPF.Gen` 在每个桶内生成按位选择函数份额，使 `U` 个 CSP 各自仅知一份布尔向量。
4. **CSP 侧聚合 CSP aggregation**：`online_demo/csp_server.py` 按份额选择列并执行按字节 XOR，得到密文向量与证明分片。
5. **客户端合并 Client combination**：`combine_csp_responses` 汇总所有 CSP 的结果；`decrypt_matches` 用 `pad_i` 还原 GBF 指纹并执行 AND/OR 逻辑组合。
6. **FX+HMAC 验证 Verification**：`run_fx_hmac_verification` 重算

   ```
   expected = (⊕_i FX(K_i, plaintext_i)) ⊕ (⊕_i FX(K_i, padAcc_i)) ⊕ N_{S,ID}
   ```

   并与 CSP 提供的证明比对，验证是否有遗漏或篡改。Proof size depends only on the security parameter λ.

---

## 5. AI 语义扩展 / AI-Assisted Expansion

- **客户端执行 On-client execution**：`secure_search.expansion_client.prepare_query_plan_with_expansion` 可调用 LLM（默认 Gemini）或本地同义词表对用户查询进行扩展。
- **泄露抑制 Leakage control**：扩展词集合会先按配置 (`suppression.max_r_blocks`) 截断，再进入秘密共享流程，避免访问模式暴露。
- **实验数据 Experiments**：`docs/experiments/query_expansion/` 存放效果图与增量命中率统计；脚本 `scripts/demo_query_expansion.py` 可复现。

---

## 6. 性能评测 / Performance Evaluation

- `docs/experiments/performance_study.py` 收集索引构建时间、查询延迟及多 CSP 扩展数据，输出 `metrics.json` 与三张核心图表：
  - Index build scaling
  - Query latency breakdown (baseline vs padding)
  - CSP scaling curve
- 关键结果 Key findings：
  - 单关键词检索 ≈ 2.5 s；三关键词 ≈ 7.5 s；五关键词 ≈ 12.6 s。
  - 启用泄露抑制后，长查询耗时下降约 20%。
  - CSP 数量从 1 扩展至 4，整体延迟仅增加约 2%。

---

## 7. 创新点 / Highlights

1. **多云协同 + 自验证 Multi-cloud with self-verification**：GBF + DMPF + FX/HMAC 组合在单轮交互内完成密态检索与结果完整性验证。
2. **AI 扩展与泄露抑制协同**：LLM 生成的扩展词在本地进行截断与随机化，兼顾召回率与隐私。
3. **可复现实验链路 Reproducible pipeline**：提供从脚本到图表的完整链条，方便论文撰写或系统迭代。

---

## 8. 配置与脚本索引 / Configuration & Scripts

- `conFig.ini`：调节 Bloom filter 尺寸 (`m1`, `m2`, `psi`)、哈希次数 (`k_spa`, `k_tex`)、抑制策略 (`max_r_blocks`) 以及 CSP 数量 (`U`)。
- 关键脚本 Key scripts：
  - `online_demo/owner_setup.py` - Build index artifacts.
  - `online_demo/run_all.py` - Launch 3 CSPs and a client for quick demo.
  - `gui_demo/server_gui.py`, `gui_demo/client_gui.py` - GUI entry points.
  - `scripts/pruning_benchmark.py` - Keyword pruning benchmark.
  - `docs/experiments/performance_study.py` - Performance evaluation.

---

## 9. 未来工作 / Future Work

- **动态更新 Dynamic updates**：实现增量索引刷新与权限撤销，降低重建成本。
- **安全增强 Security hardening**：在联网部署中加入 TLS、认证、随机 nonce 及向量化 XOR；探索与 TEE/差分隐私结合。
- **多模态查询 Multimodal queries**：扩展到图像/文本/空间联合检索，并评估联邦式部署。

> 若需要更多细节，请参考 `docs/` 目录下的实验结果、参考文献以及结题报告。

