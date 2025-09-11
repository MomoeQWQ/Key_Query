import configparser


def load_config(path: str) -> dict:
    """
    Load configuration from an INI file, providing sane defaults.
    Expects sections: general, spatial_bloom_filter, keyword_bloom_filter, suppression (optional).
    """
    parser = configparser.ConfigParser()
    parser.read(path, encoding="utf-8")

    # Defaults
    general = {
        "lambda": 16,
        "s": 64,
        "m_prime_1": 200,
        "m_prime_2": 200,
        "U": 3,
    }
    if parser.has_section("general"):
        sec = parser["general"]
        general.update({
            "lambda": sec.getint("lambda", general["lambda"]),
            "s": sec.getint("s", general["s"]),
            "m_prime_1": sec.getint("m_prime_1", general["m_prime_1"]),
            "m_prime_2": sec.getint("m_prime_2", general["m_prime_2"]),
            "U": sec.getint("U", general["U"]),
        })

    spatial = {
        "size": 200,
        "hash_count": 3,
        "psi": 32,
    }
    if parser.has_section("spatial_bloom_filter"):
        sec = parser["spatial_bloom_filter"]
        spatial.update({
            "size": sec.getint("size", spatial["size"]),
            "hash_count": sec.getint("hash_count", spatial["hash_count"]),
            "psi": sec.getint("psi", spatial["psi"]),
        })

    keyword = {
        "size": 200,
        "hash_count": 4,
        "psi": 32,
    }
    if parser.has_section("keyword_bloom_filter"):
        sec = parser["keyword_bloom_filter"]
        keyword.update({
            "size": sec.getint("size", keyword["size"]),
            "hash_count": sec.getint("hash_count", keyword["hash_count"]),
            "psi": sec.getint("psi", keyword["psi"]),
        })

    suppression = {
        "enable_padding": True,
        "max_r_blocks": 4,
        "enable_blinding": True,
    }
    if parser.has_section("suppression"):
        sec = parser["suppression"]
        suppression.update({
            "enable_padding": sec.getboolean("enable_padding", suppression["enable_padding"]),
            "max_r_blocks": sec.getint("max_r_blocks", suppression["max_r_blocks"]),
            "enable_blinding": sec.getboolean("enable_blinding", suppression["enable_blinding"]),
        })

    return {
        **general,
        "spatial_bloom_filter": spatial,
        "keyword_bloom_filter": keyword,
        "suppression": suppression,
    }

