import requests
import os

def test_file_upload():
    # 测试接口地址 (请确保您的 FastAPI 服务已启动，且端口一致)
    url = "http://127.0.0.1:8080/files/upload"

    # 1. 动态创建一个简单的临时“图片”文件用于测试
    test_image_path = "dummy_test_image.jpg"
    with open(test_image_path, "wb") as f:
        # 写入一些假想的文件内容
        f.write(b"this is a dummy image content")

    try:
        # 2. 构造上传文件参数
        # requests 的 files 格式: "对应表单参数名": ("文件名", 文件对象, "Content-Type")
        # 后端校验了 content_type 必须是 image/ 开头
        with open(test_image_path, "rb") as img_file:
            files = {
                "file": ("dummy_test_image.jpg", img_file, "image/jpeg")
            }
            
            print(f"正在发送 POST 请求到: {url}")
            response = requests.post(url, files=files)
            
            # 3. 打印出响应结果
            print("-" * 30)
            print(f"状态码 (Status Code): {response.status_code}")
            try:
                print(f"返回结果 (Response JSON): {response.json()}")
            except ValueError:
                print(f"返回结果 (纯文本): {response.text}")
            print("-" * 30)

    except requests.exceptions.ConnectionError:
        print("错误: 无法连接到服务器。请检查您的 FastAPI 服务 (uvicorn) 是否已在 8080 端口启动。")
    finally:
        # 4. 测试结束后清理临时文件
        if os.path.exists(test_image_path):
            os.remove(test_image_path)
            print("临时测试文件已清理。")

if __name__ == "__main__":
    test_file_upload()
