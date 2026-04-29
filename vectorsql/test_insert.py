import psycopg2
import json

try:
    # 1. 连接数据库 (还是用刚才成功的配置)
    conn = psycopg2.connect(
        user="postgres",
        password="123456",  # 你的密码
        host="localhost",
        port="5433",        # 关键端口
        database="doc_smart_db"
    )
    cursor = conn.cursor()

    # 2. 准备数据：模拟 AI 提取出来的发票数据 (这是 JSON 结构)
    # 以前存这种数据要建十几列，现在直接打包塞进去！
    ai_extracted_data = {
        "invoice_code": "011002200330",
        "invoice_number": "88889999",
        "date": "2023-12-15",
        "total_amount": 1050.00,
        "seller": "阿里云计算有限公司",
        "items": [
            {"name": "云服务器 ECS", "price": 500, "qty": 1},
            {"name": "RDS 数据库", "price": 550, "qty": 1}
        ],
        "risk_level": "low"  # 甚至可以随时加新字段
    }

    # 3. 插入数据
    # 注意：我们将 Python 字典转为 JSON 字符串存入 structured_data 字段
    sql = """
    INSERT INTO doc_assets (doc_type, raw_text, structured_data)
    VALUES (%s, %s, %s)
    RETURNING asset_id;
    """
    
    # 模拟的 OCR 全文文本
    raw_ocr_text = "阿里云发票... 云服务器 ECS ... 合计 1050.00 元 ..."

    cursor.execute(sql, (
        "invoice",                  # doc_type
        raw_ocr_text,               # raw_text
        json.dumps(ai_extracted_data) # structured_data (核心!)
    ))

    # 4. 提交并获取结果
    new_id = cursor.fetchone()[0]
    conn.commit() # 必须要 commit 才会真存进去

    print("\n" + "="*50)
    print("✅ 数据插入成功！")
    print(f"生成的资产 ID (UUID): {new_id}")
    print("这一步证明了你的数据库已经可以支持 Schema-less (无固定模式) 存储了！")
    print("="*50 + "\n")

except (Exception, psycopg2.Error) as error:
    print("\n❌ 发生错误:", error)

finally:
    if 'conn' in locals() and conn:
        cursor.close()
        conn.close()