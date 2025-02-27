import os
import struct
import hashlib
from Cryptodome.Cipher import AES

# -----------------------------
# 1. 格雷码编码函数
# -----------------------------
def int_to_gray(n: int) -> int:
    """将整数 n 转换为对应的格雷码整数。"""
    return n ^ (n >> 1)

def gray_to_binary_str(n: int, bit_length: int) -> str:
    """将格雷码整数 n 转换为固定长度的二进制字符串。"""
    gray = int_to_gray(n)
    return format(gray, f'0{bit_length}b')

def coordinate_to_gray(coord: float, min_val: float, max_val: float, bit_length: int) -> str:
    """将连续的坐标映射为格雷码字符串。"""
    # 归一化并量化到 [0, 2^bit_length - 1]
    n = int((coord - min_val) / (max_val - min_val) * (2 ** bit_length - 1))
    return gray_to_binary_str(n, bit_length)

# -----------------------------
# 2. 布隆过滤器类
# -----------------------------
class BloomFilter:
    def __init__(self, size: int, hash_count: int):
        self.size = size
        self.hash_count = hash_count
        self.bit_array = [0] * size

    def _hashes(self, item: str):
        """生成 hash_count 个哈希值，采用双哈希技巧。"""
        hash1 = int(hashlib.sha256(item.encode('utf-8')).hexdigest(), 16)
        hash2 = int(hashlib.md5(item.encode('utf-8')).hexdigest(), 16)
        for i in range(self.hash_count):
            yield (hash1 + i * hash2) % self.size

    def add(self, item: str):
        for index in self._hashes(item):
            self.bit_array[index] = 1

    def query(self, item: str) -> bool:
        return all(self.bit_array[index] for index in self._hashes(item))

# -----------------------------
# 3. PRP 实现（基于 AES-ECB）
# -----------------------------
class PRP:
    def __init__(self, key: bytes):
        self.key = key
        self.cipher = AES.new(key, AES.MODE_ECB)

    def permute(self, value: int) -> int:
        # 限制在32位范围内
        value_32 = value % (2**32)
        # 构造16字节数据：4字节的value_32加上12个0字节
        data = struct.pack(">I", value_32) + b'\x00' * 12
        encrypted = self.cipher.encrypt(data)
        # 取加密结果的前4字节，转换为整数返回
        return struct.unpack(">I", encrypted[:4])[0]



# -----------------------------
# 4. 布谷鸟哈希插入算法（支持PRP扰动）
# -----------------------------
def cuckoo_insert(hash_table: list, item: any, prp: PRP, k: int, max_kicks: int = 500) -> bool:
    """
    将 item 插入到 hash_table 中。
    - hash_table: 长度为 M 的列表，空槽用 None 表示。
    - item: 待插入的数据对象（例如，我们可以使用其 gray_code 作为哈希键）。
    - prp: PRP 对象，用于扰动哈希值。
    - k: 候选位置数。
    - max_kicks: 最大踢出次数。
    """
    M = len(hash_table)
    base_hash = abs(hash(item))  # 这里直接使用 Python 内置 hash 值，也可替换为自定义哈希函数
    positions = [prp.permute(base_hash + i) % M for i in range(k)]
    
    current_item = item
    for _ in range(max_kicks):
        for pos in positions:
            if hash_table[pos] is None:
                hash_table[pos] = current_item
                return True
        # 如果所有候选位置都已占用，踢出第一个位置的元素
        pos = positions[0]
        current_item, hash_table[pos] = hash_table[pos], current_item
        base_hash = abs(hash(current_item))
        positions = [prp.permute(base_hash + i) % M for i in range(k)]
    return False  # 达到最大踢出次数仍未插入成功

# -----------------------------
# 5. 数据对象定义及数据类型初始化
# -----------------------------
class DataObject:
    def __init__(self, id: str, x: float, y: float, keywords: list):
        self.id = id            # 唯一标识符
        self.x = x              # 经度或横坐标
        self.y = y              # 纬度或纵坐标
        self.keywords = keywords
        self.gray_code = None   # 通过格雷码编码得到的字符串（例如 x 和 y 拼接而成）
        self.bloom_filter = None  # 对关键词集合构造的布隆过滤器

# 配置参数（实际应用中可通过配置文件加载）
config = {
    "coordinate": {
        "x_min": 0.0,
        "x_max": 100.0,
        "y_min": 0.0,
        "y_max": 100.0,
        "bit_length": 16   # 每个坐标使用16位
    },
    "bloom_filter": {
        "size": 1024,      # 位数组大小
        "hash_count": 4    # 使用的哈希函数个数
    },
    "cuckoo_hashing": {
        "table_size": 2048,  # 布谷鸟哈希表大小
        "num_hash_functions": 3,
        "max_kicks": 500
    },
    "prp": {
        "key": os.urandom(16)  # 128位随机密钥
    }
}

def initialize_data_objects(raw_data: list) -> list:
    """
    raw_data: 每个元素是一个字典，包含 'id', 'x', 'y', 'keywords'
    """
    objects = []
    for data in raw_data:
        obj = DataObject(data['id'], data['x'], data['y'], data['keywords'])
        # 计算 x 和 y 的格雷码，分别转换为固定长度的二进制字符串后拼接
        gray_x = coordinate_to_gray(obj.x, config["coordinate"]["x_min"], config["coordinate"]["x_max"], config["coordinate"]["bit_length"])
        gray_y = coordinate_to_gray(obj.y, config["coordinate"]["y_min"], config["coordinate"]["y_max"], config["coordinate"]["bit_length"])
        obj.gray_code = gray_x + gray_y  # 简单拼接，实际可根据需求进一步设计
        # 初始化布隆过滤器并插入所有关键词
        bf = BloomFilter(config["bloom_filter"]["size"], config["bloom_filter"]["hash_count"])
        for keyword in obj.keywords:
            bf.add(keyword)
        obj.bloom_filter = bf
        objects.append(obj)
    return objects

# 示例数据
raw_data = [
    {"id": "1", "x": 12.3, "y": 45.6, "keywords": ["park", "restaurant"]},
    {"id": "2", "x": 78.9, "y": 12.3, "keywords": ["hospital", "school"]}
]

# 初始化数据对象
data_objects = initialize_data_objects(raw_data)
for obj in data_objects:
    print(f"DataObject ID: {obj.id}, GrayCode: {obj.gray_code}")
    # 仅打印布隆过滤器前20位
    print(f"BloomFilter (first 20 bits): {obj.bloom_filter.bit_array[:20]}")

# -----------------------------
# 6. 构建布谷鸟哈希索引
# -----------------------------
# 初始化哈希表和 PRP 实例
cuckoo_table = [None] * config["cuckoo_hashing"]["table_size"]
prp = PRP(config["prp"]["key"])

# 将每个数据对象（这里使用其 gray_code 作为插入依据）插入布谷鸟哈希表
for obj in data_objects:
    success = cuckoo_insert(cuckoo_table, obj, prp, config["cuckoo_hashing"]["num_hash_functions"], config["cuckoo_hashing"]["max_kicks"])
    if not success:
        print(f"Failed to insert data object ID: {obj.id}")

print("Cuckoo Hash Table Sample (前20个槽位):")
print(cuckoo_table[:20])
