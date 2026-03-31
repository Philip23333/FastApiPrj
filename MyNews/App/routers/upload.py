import os
import shutil
from fastapi import APIRouter, File, UploadFile
from utils.response import ApiResponse, success_response, error_response
import uuid

router = APIRouter(prefix="/files", tags=["files"])

# 上传目录 (确保相对 App 根目录)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UPLOAD_DIR = os.path.join(BASE_DIR, "static", "uploads")

@router.post("/upload")
async def upload_image(file: UploadFile = File(...)):
    """处理图片上传"""
    # 确保上传目录存在
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    
    # 验证文件类型 (可选，仅允许图片)
    if not file.content_type.startswith("image/"):
        return error_response(400, "仅支持上传图片文件")

    # 生成唯一文件名，防止重名覆盖
    file_ext = file.filename.split('.')[-1] if '.' in file.filename else ''
    new_filename = f"{uuid.uuid4().hex}.{file_ext}" if file_ext else uuid.uuid4().hex
    file_path = os.path.join(UPLOAD_DIR, new_filename)

    # 保存图片文件
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # 返回给前端的图片 URL 路径
    # 注意，这里的 /static 是需要在 main.py 挂载静态文件的
    image_url = f"/static/uploads/{new_filename}"
    
    return success_response(data={"url": image_url}, message="图片上传成功")
