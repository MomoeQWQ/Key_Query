# ST-VLS 隐私保护时空关键词检索项目说明

ST-VLS（Spatio-Temporal Secure Search with Verifiable Leakage Suppression）是一个融合可搜索加密、分布式多方计算与轻量级验证的研究型原型系统。项目展示了在不可信多云环境下，如何在保持数据与查询隐私的前提下完成时空多关键词检索，并由客户端对云端返回的结果进行自助式验证。系统同时提供可选的 LLM 语义扩展能力，用于提升查询召回率。

---

## 功能亮点

- **认证密态索引**：利用 Garbled Bloom Filter（GBF）编码关键词和空间 token，通过一次性掩码与 FX+HMAC 标签确保密文列的完整性与机密性。
- **泄露抑制查询**：结合 PRP-based Cuckoo 分桶与 Distributed Multi-Point Function（DMPF）份额，使各个 CSP 只能看到随机化的列选择，从而抑制访问模式泄露。
- **客户端验证**：FX + HMAC 证明在常数长度内实现结果可验证，客户端可检测遗漏或篡改的记录。
- **AI 语义扩展**：可选的 LLM 管道在本地完成关键词扩展，并配合截断与掩码策略控制额外泄露。
- **多种演示形式**：提供命令行脚本、GUI 程序以及实验脚本，便于从索引构建到性能评估的全流程验证。

---

## 仓库结构概览

| 路径 | 说明 |
| --- | --- |
| `secure_search/` | 核心包：索引构建（`indexing.py`）、查询流程（`query.py`）、验证、GBF/DMPF 基元，以及 AI 工具（`query_expansion.py`、`expansion_client.py`、`pruning_client.py`）。 |
| `online_demo/` | 命令行端到端演示，包括数据拥有者建索引、CSP 服务端与客户端。 |
| `gui_demo/` | 基于 Tkinter 的可视化演示入口，支持图形化启动 CSP 与发起查询。 |
| `docs/` | 技术文档、实验报告、图表及双语说明。 |
| `docs/experiments/` | 性能实验脚本与生成的指标/图像。 |
| `ai_pruning/` | 关键词裁剪相关的 LightGBM 训练与推理脚本。 |
| `ai_clients/` | 可选的 LLM 适配器，例如 Google Gemini。 |
| `scripts/` | 数据预处理、查询扩展、裁剪基准等辅助脚本。 |
| `GBF.py`、`DMPF.py`、`SetupProcess.py`、`verification.py`、`QueryUtils.py`、`convert_dataset.py` | 核心算法基元。 |
| `conFig.ini` | 示例配置文件，可调节布隆过滤器参数、抑制策略与 CSP 数量。 |
| `us-colleges-and-universities.csv` | 默认使用的公开数据集。 |

详细目录说明可参考英文 `Readme.md` 中的“Repository Layout”表格。

---

## 环境与依赖

1. 推荐使用 Python 3.10 或更高版本。
2. 安装基础依赖：
   ```bash
   pip install -r requirements.txt
   ```
   如未提供依赖清单，可手动安装 `pandas`、`numpy`、`matplotlib`、`lightgbm` 等库。
3. **可选（LLM 扩展）**：如需启用 Gemini 扩展，安装 `google-generativeai` 并设置环境变量 `GEMINI_API_KEY`。若希望替换为其他模型，可修改 `secure_search/query_expansion.py`。
4. 建议使用虚拟环境（`venv`/`conda`）隔离依赖。

---

## 数据与索引构建

1. 根据需求调整 `conFig.ini` 中的布隆过滤器参数（`m1`、`m2`、`psi`）、哈希次数（`k_spa`、`k_tex`）、抑制策略（`max_r_blocks`）以及 CSP 数量 `U`。
2. 运行索引构建脚本：
   ```bash
   python online_demo/owner_setup.py --csv us-colleges-and-universities.csv --config conFig.ini --out online_demo
   ```
   该脚本会生成 `aui.pkl`（认证索引）与 `K.pkl`（密钥材料）。若数据、配置或算法有所变动，请重新生成。

---

## 演示程序

### 离线测试

- 仅关键词：
  ```bash
  python offline_demo.py "ORLANDO"
  ```
- 关键词 + 空间范围：
  ```bash
  python offline_demo_spatial.py "ORLANDO; R: 28.3,-81.5,28.7,-81.2"
  ```

### 在线多 CSP 演示

```bash
python online_demo/run_all.py "ORLANDO; R: 28.3,-81.5,28.7,-81.2"
```

也可通过标准输入发送查询：
```bash
echo ORLANDO | python online_demo/run_all.py
```

如需单独启动服务，可先运行 `online_demo/csp_server.py`（指定 `--aui` 和 `--keys`），随后调用 `online_demo/client.py`。

### GUI 工作流

1. 启动 CSP GUI：
   ```bash
   python gui_demo/server_gui.py
   ```
   选择 `aui.pkl`，配置端口后点击 **Start servers**。
2. 启动客户端 GUI：
   ```bash
   python gui_demo/client_gui.py
   ```
   填写 `aui.pkl`、`K.pkl`、`conFig.ini`，可选加载 CSV 以查看明文结果，提交查询后即可查看验证状态与命中列表。

---

## API 快速上手

```python
from config_loader import load_config
from secure_search import (
    build_index_from_csv,
    save_index_artifacts,
    load_index_artifacts,
    prepare_query_plan,
    prepare_query_plan_with_expansion,
    combine_csp_responses,
    decrypt_matches,
    run_fx_hmac_verification,
)

cfg = load_config("conFig.ini")
aui, keys = build_index_from_csv("us-colleges-and-universities.csv", "conFig.ini")
plan = prepare_query_plan("ORLANDO ENGINEERING", aui, cfg)
# 或者启用语义扩展：
# plan = prepare_query_plan_with_expansion("ORLANDO ENGINEERING", aui, cfg)
```

`online_demo/client.py` 展示了如何序列化查询计划、与各 CSP 通信及验证返回结果。

---

## AI 语义扩展与关键词裁剪

- **语义扩展**：`secure_search.expansion_client.prepare_query_plan_with_expansion` 可调用 LLM 或本地同义词表扩展关键词集合。示例脚本位于 `scripts/demo_query_expansion.py`，生成的增量命中统计图保存在 `docs/experiments/query_expansion/`。
- **关键词裁剪**：`ai_pruning/` 提供 LightGBM 训练与推理工具，用于估计关键词的重要度。参考 `scripts/pruning_benchmark.py` 进行复现。
- 所有扩展词都会在本地按照配置截断并随机化，以确保不会额外暴露用户查询模式。

---

## 性能实验

主要实验由 `docs/experiments/performance_study.py` 运行，输出：

- `docs/experiments/metrics.json`：索引构建时间、查询延迟、多 CSP 扩展等原始数据；
- `docs/experiments/figures/`：索引规模、查询分解、CSP 数量影响等图表。

结果表明：单关键词查询耗时约 2.5 秒，三关键词约 7.5 秒；开启泄露抑制后，长查询耗时下降约 20%；CSP 数量从 1 扩展到 4，整体延迟仅增加约 2%。

---

## 配置与自定义

- `conFig.ini`：调节索引参数、抑制策略与 CSP 数量。
- `prepare_dataset.py` / `convert_dataset.py`：如需适配其他数据集，请在此定义新的字段映射与编码逻辑。
- 部署建议：在生产环境加入 TLS、身份认证、随机 nonce 以及向量化 XOR 加速。

---

## 参考文档

- 英文主 README：`Readme.md`
- 技术说明（中英双语）：`docs/TECHNICAL_zh.md`
- 结题报告与实验附录：请参阅 `docs/` 与 `References/` 目录。

---

如在使用过程中遇到问题，建议首先阅读上述文档，并依据 `scripts/`、`docs/experiments/` 中的示例进行复现与排错。
