import base64
import hashlib
import hmac
import secrets


ALGORITHM = "pbkdf2_sha256"
ITERATIONS = 260000
SALT_BYTES = 16

# 将输入的密码进行哈希处理，返回一个包含算法、迭代次数、盐和哈希值的字符串。{算法}${迭代次数}${盐}${哈希值}
def hash_password(password: str) -> str:
    salt = secrets.token_bytes(SALT_BYTES)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, ITERATIONS)
    # 将二进制的 salt 和 digest 分别进行 Base64 编码，并解码为 ASCII 字符串。这样它们就可以安全地存储在文本数据库字段中。
    salt_b64 = base64.b64encode(salt).decode("ascii")
    digest_b64 = base64.b64encode(digest).decode("ascii")
    return f"{ALGORITHM}${ITERATIONS}${salt_b64}${digest_b64}"

# 定义函数，用于判断数据库中存储的字符串是否是按照上述格式生成的哈希值。为了向后兼容。如果数据库里还有旧的明文密码，这个函数会返回 False，表示它不是一个哈希值。
def is_hashed_password(stored_password: str) -> bool:
    return isinstance(stored_password, str) and stored_password.startswith(f"{ALGORITHM}$")


def verify_password(password: str, stored_password: str) -> bool:
    # 后向兼容，如果 stored_password 不是一个哈希值（即不符合上述格式），则直接使用 hmac.compare_digest 来比较输入的密码和存储的密码。这允许系统在过渡期间继续支持旧的明文密码，同时新注册或更新的用户将使用更安全的哈希存储方式。
    if not is_hashed_password(stored_password):
        return hmac.compare_digest(password, stored_password)

    parts = stored_password.split("$", 3)
    if len(parts) != 4:
        return False

    _, iterations_raw, salt_b64, digest_b64 = parts
    try:
        iterations = int(iterations_raw)
        salt = base64.b64decode(salt_b64.encode("ascii"))
        # 正确的哈希值（从数据库中已有的存储来）
        expected_digest = base64.b64decode(digest_b64.encode("ascii"))
    except (ValueError, TypeError):
        return False
    # 传入的密码得到的哈希值
    actual_digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(actual_digest, expected_digest)
