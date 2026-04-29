from fastapi import APIRouter, UploadFile, File, HTTPException
import shutil
import os
import sys
from pathlib import Path

# 1. 尝试引入你的 AI 引擎
# 只要 ai_engine 文件夹在 Backend 根目录下，这里就能引用到
try:
    from ai_engine.ocr_processor import ocr_pdf_with_tesseract, clean_with_deepseek, save_to_db
except ImportError:
    # 如果路径有问题，尝试动态添加路径（保险起见）
    sys.path.append(str(Path(__file__).parent.parent.parent))
    from ai_engine.ocr_processor import ocr_pdf_with_tesseract, clean_with_deepseek, save_to_db

router = APIRouter()

# 定义临时文件存放目录
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.post("/api/smart/invoice", summary="智能单证识别 (DeepSeek)")
async def smart_analyze_invoice(file: UploadFile = File(...)):
    """
    上传 PDF -> Tesseract OCR -> DeepSeek 提取 -> 存入 PostgreSQL
    """
    print(f"🚀 [智能体] 收到单证文件: {file.filename}")

    # 1. 验证文件
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="目前仅支持 PDF 文件")

    temp_file_path = os.path.join(UPLOAD_DIR, f"smart_{file.filename}")
    
    try:
        # 2. 保存文件到本地
        with open(temp_file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # 3. OCR 识别
        print("   - 正在进行 OCR 视觉识别...")
        raw_text = ocr_pdf_with_tesseract(temp_file_path)
        if not raw_text:
            raise HTTPException(status_code=500, detail="OCR 未能提取到任何文字")

        # 4. DeepSeek 思考
        print("   - 正在调用 DeepSeek 进行语义提取...")
        structured_data = clean_with_deepseek(raw_text)
        if not structured_data:
            raise HTTPException(status_code=500, detail="AI 分析返回为空")

        # 5. 存入数据库
        print("   - 正在存入数据库...")
        asset_id = save_to_db("invoice", raw_text, structured_data)

        # 6. 返回结果
        # 注意：你的 main.py 里有 create_response_handler 中间件
        # 这里直接返回数据对象即可，中间件会自动把它包装成标准的 {code:0, data:...} 格式
        return {
            "asset_id": asset_id,
            "file_name": file.filename,
            "ai_result": structured_data
        }

    except Exception as e:
        print(f"❌ 处理失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
        
    finally:
        # 可选：清理临时文件
        # if os.path.exists(temp_file_path):
        #     os.remove(temp_file_path)
        pass