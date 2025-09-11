import hashlib
from QueryUtils import pad_query_blocks, tokenize_normalized
import DMPF


def _hash_positions(item: str, size: int, hash_count: int) -> list:
    h1 = int(hashlib.sha256(item.encode('utf-8')).hexdigest(), 16)
    h2 = int(hashlib.md5(item.encode('utf-8')).hexdigest(), 16)
    return [(h1 + i * h2) % size for i in range(hash_count)]


def search_process(query, authenticated_index, suppression=None):
    """
    仅基于关键词 GBF 的按字节 XOR 聚合：
      - 每个查询词生成列选择集合（GBF 哈希位置）
      - DMPF 返回各方在每列的比特份额（XOR 后得到选择位）
      - 各方计算对象级向量份额：对被选择的列逐列按字节 XOR
      - 证明份额：对应 sigma 列按字节 XOR
    返回: (result_shares, proof_shares)
    """
    I_tex = authenticated_index['I_tex']
    m2 = authenticated_index['m2']
    U = authenticated_index['U']
    security_param = authenticated_index['security_param']
    k_tex = authenticated_index.get('k_tex', 4)

    toks = tokenize_normalized(query)
    tokens = toks or [query]
    # 可选：固定 R 块数量（此处只使用关键词块，padding 不影响逻辑）
    if suppression and suppression.get('enable_padding', True):
        max_r = suppression.get('max_r_blocks', 4)
        if len(tokens) > max_r:
            tokens = tokens[:max_r]

    n = len(I_tex["EbW"])  # 对象数
    byte_len = len(I_tex["EbW"][0][0]) if n and I_tex["EbW"][0] else 0

    result_shares = {l: [] for l in range(U)}
    proof_shares = {l: [] for l in range(U)}

    for tok in tokens:
        indices = _hash_positions(tok, m2, k_tex)
        keys = DMPF.Gen(security_param, indices, m2, num_parties=U)
        for l in range(U):
            # 计算选择掩码（比特份额）
            sel = [DMPF.Eval(keys[l], j) for j in range(m2)]
            # 对象级按字节 XOR 聚合
            vec = [b"\x00" * byte_len for _ in range(n)]
            for j in range(m2):
                if sel[j] == 1:
                    col_cells = [row[j] for row in I_tex["EbW"]]
                    for i in range(n):
                        vec[i] = bytes(a ^ b for a, b in zip(vec[i], col_cells[i]))
            # 证明份额（按字节 XOR）
            proof = b"\x00" * security_param
            for j in range(m2):
                if sel[j] == 1:
                    proof = bytes(a ^ b for a, b in zip(proof, I_tex["sigma"][j]))
            result_shares[l].append(vec)
            proof_shares[l].append(proof)

    return result_shares, proof_shares
