import pandas as pd
import prepare_dataset
import configparser
from SetupProcess import Setup   # 使用已实现的 Setup 函数，其输入为 DB 列表和配置字典
from SearchProcess import search_process  # 已实现的本地查询功能
from convert_dataset import convert_dataset
import hmac, hashlib

def F(key, data, output_len):
    """
    F: {0,1}^λ × {0,1}^* → {0,1}^{output_len}
    使用 HMAC-SHA256 实现，输出 output_len 字节。
    """
    out = hmac.new(key, data, hashlib.sha256).digest()
    if len(out) >= output_len:
        return out[:output_len]
    else:
        full = b""
        counter = 0
        while len(full) < output_len:
            full += hmac.new(key, data + counter.to_bytes(4, 'big'), hashlib.sha256).digest()
            counter += 1
        return full[:output_len]

def combine_results(result_shares):
    """
    将各参与方的结果分享按位置异或组合，
    得到最终聚合结果列表（每个查询块对应一个大整数）。
    假设每个参与方的结果列表长度相同。
    """
    parties = sorted(result_shares.keys())
    num_blocks = len(result_shares[parties[0]])
    
    final_results = []
    for i in range(num_blocks):
        xor_sum = 0
        for party in parties:
            xor_sum ^= result_shares[party][i]
        final_results.append(xor_sum)
    return final_results

def decrypt_all_results(final_query_result, DB, Ke, config):
    """
    对最终查询结果中的每个聚合结果进行解密，
    还原出对应记录的明文内积值。
    
    参数:
      final_query_result: 一个列表，每个元素为一个大整数（聚合结果，按位异或后的值）
      DB: convert_dataset 得到的记录列表，每个记录具有属性 id、x、y、keywords
      Ke: Setup 阶段生成的一次性加密密钥（字节串），即 K[0]
      config: 配置参数字典，用于获得 m1、m2、psi 等参数
      
    解密过程：
      对于 DB 中第 i 条记录（记录序号从1开始），计算：
         pad = F(Ke, (str(i+1) + str(DB[i].id)).encode('utf-8'), total_len)
      其中 total_len = (m1 + m2) * (psi // 8)。
      然后 plaintext = aggregated_result XOR pad。
      
    返回:
      一个列表，每个元素为解密后的明文内积值。
    """
    m1 = config["spatial_bloom_filter"]["size"]
    m2 = config["keyword_bloom_filter"]["size"]
    psi = config["keyword_bloom_filter"]["psi"]
    chunk_len = psi // 8
    total_len = (m1 + m2) * chunk_len

    decrypted_results = []
    # 假设 final_query_result 的顺序与 DB 中记录顺序一致（记录序号从1开始）
    for i, agg in enumerate(final_query_result):
        data = (str(i+1) + str(DB[i].id)).encode('utf-8')
        pad = F(Ke, data, total_len)
        pad_int = int.from_bytes(pad, byteorder='big')
        plain = agg ^ pad_int
        decrypted_results.append(plain)
    return decrypted_results

def main():
    # 2. 构造配置参数 config
    config = {
        "lambda": 16,  # 安全参数，16 字节（128 位安全性）
        "spatial_bloom_filter": {
            "size": 200,      # m1：空间 GBF 的长度（块数）
            "hash_count": 3,  # 空间 GBF 使用的哈希函数个数
            "psi": 32         # ψ 参数（以比特为单位，通常为8的倍数）
        },
        "keyword_bloom_filter": {
            "size": 200,      # m2：关键词 GBF 的长度（块数）
            "hash_count": 4,  # 关键词 GBF 使用的哈希函数个数
            "psi": 32         # ψ 参数
        },
        "s": 64,              # 参数 s，用于前缀长度计算（单位：比特）
        "m_prime_1": 200,     # 分段数目 m'_1（用于处理 R 部分）
        "m_prime_2": 200,     # 分段数目 m'_2（用于处理 W* 部分）
        "U": 3                # 参与方数量
    }

    # 1. 读取 CSV 文件，构造 spatio-textual 数据集 DB
    csv_file = "us-colleges-and-universities.csv"  # 请修改为你的 CSV 文件路径
    df = prepare_dataset.load_and_transform(csv_file)
    DB = convert_dataset(df, config)

    # 3. 调用 setup 函数，构造本地认证索引（AUI）和秘密密钥 K
    AUI, K = Setup(DB, config)
    print("本地索引（AUI）和秘密密钥（K）构建成功。")

    # 4. 提示用户输入查询内容
    query = input("请输入查询内容：")
  
    # 5. 调用 search_process 执行本地查询（暂不考虑认证验证部分）
    results = search_process(query, AUI)
    
    # 6. 输出查询结果分享
    print("\n查询结果分享：")
    print(results)

    # 7. 组合各参与方结果，得到最终聚合结果（各结果块按位异或后的大整数列表）
    final_query_result = combine_results(results)
    print("\n最终查询结果（各结果块按位异或后）：")
    print(final_query_result)

    # 8. 解密聚合结果，还原出明文内积值 
    decrypted_results = decrypt_all_results(final_query_result, DB, K[0], config)
    # print("\n解密后的明文内积值：")
    # print(decrypted_results)

    # 9. 根据解密内积值判断匹配
    # 利用 GBF.fingerprint 函数计算每条记录关键词的预期指纹，
    # 将其转换为整数，与解密后的内积值进行比较。
    from GBF import fingerprint  # 确保导入 GBF 模块中的 fingerprint 函数

    matching_triples = []
    psi = config["keyword_bloom_filter"]["psi"]
    for i, dec in enumerate(decrypted_results):
        record = DB[i]
        # 计算预期的指纹值（bytes），并转换为整数
        expected_fp = int.from_bytes(fingerprint(record.keywords, psi), byteorder='big')
        # 如果解密结果与预期指纹相等，则认为匹配
        if dec == expected_fp:
            matching_triples.append((record.id, record.x, record.y, record.keywords))
        
    print("\n还原的匹配记录（三元组）：")
    for triple in matching_triples:
        print(triple)


if __name__ == '__main__':
    main()
