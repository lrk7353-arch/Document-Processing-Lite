import shutil
import os
from fastapi import FastAPI, UploadFile, File, HTTPException
from ai_engine.ocr_processor import ocr_pdf_with_tesseract, clean_with_deepseek, save_to_db

app = FastAPI(title="DocSmart AI API", description="外贸单证智能处理中台接口")

# 确保有个临时文件夹存上传的文件
UPLOAD_DIR = "temp_uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@app.get("/")
def read_root():
    return {"message": "DocSmart AI Service is Running! 🚀"}

@app.post("/analyze/invoice")
async def analyze_invoice(file: UploadFile = File(...)):
    """
    上传 PDF 发票 -> OCR 识别 -> DeepSeek 提取 -> 存入数据库
    """
    # 1. 验证文件类型
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="目前仅支持 PDF 文件")

    # 2. 保存上传的文件到本地临时目录
    temp_file_path = os.path.join(UPLOAD_DIR, file.filename)
    try:
        with open(temp_file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        print(f"📥 接收到文件: {file.filename}")

        # 3. 调用你的 AI 引擎 (复用 ocr_processor.py 的逻辑)
        # 3.1 OCR 识别
        raw_text = ocr_pdf_with_tesseract(temp_file_path)
        if not raw_text:
            raise HTTPException(status_code=500, detail="OCR 识别失败，未能提取到文字")

        # 3.2 DeepSeek 提取
        structured_data = clean_with_deepseek(raw_text)
        if not structured_data:
            raise HTTPException(status_code=500, detail="AI 分析失败")

        # 3.3 存入数据库
        asset_id = save_to_db("invoice", raw_text, structured_data)

        # 4. 返回结果给前端
        return {
            "status": "success",
            "message": "处理完成",
            "data": {
                "asset_id": asset_id,
                "file_name": file.filename,
                "extracted_content": structured_data
            }
        }

    except Exception as e:
        print(f"❌ API 出错: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    
    finally:
        # (可选) 处理完后删除临时文件，节省空间
        # if os.path.exists(temp_file_path):
        #     os.remove(temp_file_path)
        pass

if __name__ == "__main__":
    import uvicorn
    # 启动服务，端口 8000
    uvicorn.run(app, host="0.0.0.0", port=8000)