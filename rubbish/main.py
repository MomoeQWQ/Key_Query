# main.py

import pandas as pd
import prepare_dataset
import configparser
from SetupProcess import Setup   # 使用已实现的 setup 函数，其输入为 DB 列表和配置字典
from SearchProcess import search_process  # 已实现的本地查询功能
from convert_dataset import convert_dataset

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
        "m_prime_1": 200,      # 分段数目 m'_1（用于处理 R 部分）
        "m_prime_2": 200,      # 分段数目 m'_2（用于处理 W* 部分）
        "U": 3                # 参与方数量
    }


    # 1. 读取 CSV 文件，构造 spatio-textual 数据集 DB
    csv_file = "us-colleges-and-universities.csv"  # 请修改为你的 CSV 文件路径
    df = prepare_dataset.load_and_transform(csv_file)
    DB = convert_dataset(df,config)

    # 3. 调用 setup 函数，构造本地认证索引（AUI）和秘密密钥 K
    AUI, K = Setup(DB, config)
    print("本地索引（AUI）和秘密密钥（K）构建成功。")

    # 4. 提示用户输入查询内容
    query = input("请输入查询内容：")
  
    # 5. 调用 search_process 执行本地查询（暂不考虑认证验证部分）
    results = search_process(query, AUI)
    
    # 6. 输出查询结果
    print("\n查询结果：")
    print(results)

    # 组合各方结果，假设每个参与方的结果分享是一个列表，每个列表中各元素对应一个查询块的结果
    def combine_results(result_shares):
        # 获取参与方数量以及结果块个数（假设每个参与方结果列表长度相同）
        parties = sorted(result_shares.keys())
        num_blocks = len(result_shares[parties[0]])
        
        final_results = []
        for i in range(num_blocks):
            # 初始值设为0
            xor_sum = 0
            for party in parties:
                xor_sum ^= result_shares[party][i]
            final_results.append(xor_sum)
        return final_results

    final_query_result = combine_results(results)
    print("\n最终查询结果（各结果块按位异或后）：")
    print(final_query_result)

if __name__ == '__main__':
    main()
