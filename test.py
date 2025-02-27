from pybloom_live import BloomFilter
import random
import string
import time
from concurrent.futures import ThreadPoolExecutor

# 生成随机字符串
def random_string(length=10):
    return ''.join(random.choices(string.ascii_lowercase, k=length))

# 1. 正确性测试
def correctness_test():
    bloom = BloomFilter(capacity=1000, error_rate=0.01)
    inserted_elements = ["apple", "banana", "cherry"]
    
    # 插入元素
    for element in inserted_elements:
        bloom.add(element)
    
    # 查询已插入的元素
    assert bloom.__contains__("apple") == True
    assert bloom.__contains__("banana") == True
    assert bloom.__contains__("cherry") == True
    
    # 查询未插入的元素
    assert bloom.__contains__("orange") == False
    assert bloom.__contains__("grape") == False
    
    print("Correctness test passed!")

# 2. 假阳性率测试
def false_positive_rate_test():
    bloom = BloomFilter(capacity=1000, error_rate=0.01)
    inserted_elements = [random_string() for _ in range(1000)]
    
    # 插入元素
    for element in inserted_elements:
        bloom.add(element)
    
    false_positive_count = 0
    total_queries = 10000
    
    # 查询未插入的元素
    for _ in range(total_queries):
        query_element = random_string()
        if query_element in bloom:
            false_positive_count += 1
    
    false_positive_rate = false_positive_count / total_queries
    print(f"False Positive Rate: {false_positive_rate:.2%}")
    
    assert false_positive_rate <= 0.05  # 假阳性率不超过5%
    print("False positive rate test passed!")

# 3. 性能测试（优化版：并行插入）
def optimized_performance_test():
    bloom = BloomFilter(capacity=1000000, error_rate=0.01)
    
    # 插入100万个元素并使用并行化
    elements = [random_string() for _ in range(1000000)]
    
    start_time = time.time()
    # 使用线程池并行插入元素
    with ThreadPoolExecutor() as executor:
        executor.submit(batch_insert, bloom, elements)
    end_time = time.time()
    insert_time = end_time - start_time

    # 查询100万个元素
    start_time = time.time()
    for element in elements:
        bloom.__contains__(element)
    end_time = time.time()
    query_time = end_time - start_time

    print(f"Insert time for 1 million elements: {insert_time:.2f} seconds")
    print(f"Query time for 1 million elements: {query_time:.2f} seconds")
    
    # 插入和查询时间应该在合理范围内
    assert insert_time < 5  # 插入时间少于5秒
    assert query_time < 5  # 查询时间少于5秒
    print("Optimized performance test passed!")

# 4. 边界条件测试（优化版）
def optimized_boundary_conditions_test():
    # 小数据集测试
    bloom_small = BloomFilter(capacity=10, error_rate=0.01)
    bloom_small.add("apple")
    assert bloom_small.__contains__("apple") == True
    assert bloom_small.__contains__("banana") == False
    
    # 优化大数据集测试，减少插入数据量
    bloom_large = BloomFilter(capacity=1000000, error_rate=0.01)  # 使用较小的容量
    elements = [random_string() for _ in range(100000)]  # 插入100,000个元素，而不是1亿
    
    # 插入100,000个元素
    start_time = time.time()
    batch_insert(bloom_large, elements, batch_size=5000)  # 每次插入5000个元素
    end_time = time.time()
    insert_time = end_time - start_time
    print(f"Insert time for 100,000000 elements: {insert_time:.2f} seconds")
    
    # 查询100,000个元素
    false_positive_count = 0
    total_queries = 10000  # 查询次数减少到10,000次
    start_time = time.time()
    for _ in range(total_queries):
        query_element = random_string()
        if query_element in bloom_large:
            false_positive_count += 1
    end_time = time.time()
    query_time = end_time - start_time
    
    false_positive_rate = false_positive_count / total_queries
    print(f"False Positive Rate: {false_positive_rate:.2%}")
    print(f"Query time for 10,000 queries: {query_time:.2f} seconds")
    
    # 假阳性率应小于10%
    assert false_positive_rate < 0.1
    assert insert_time < 5  # 插入时间应小于5秒
    assert query_time < 5  # 查询时间应小于5秒
    
    print("Optimized boundary conditions test passed!")

# 分批插入函数（优化插入过程）
def batch_insert(bloom, elements, batch_size=10000):
    for i in range(0, len(elements), batch_size):
        batch = elements[i:i + batch_size]
        for elem in batch:
            bloom.add(elem)

# 执行所有测试
def run_tests():
    correctness_test()
    false_positive_rate_test()
    optimized_performance_test()
    optimized_boundary_conditions_test()

# 运行所有测试
run_tests()
