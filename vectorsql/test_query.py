import psycopg2
import json

try:
    conn = psycopg2.connect(
        user="postgres",
        password="123456",
        host="localhost",
        port="5433",
        database="doc_smart_db"
    )
    cursor = conn.cursor()

    print("\n" + "="*50)
    print("🔍 正在执行智能检索...")
    
    # 【核心知识点】
    # structured_data->>'total_amount' : 提取 JSON 里的 total_amount 字段并转为文本
    # ::numeric : 把它强转为数字，以便进行数学比较 (> 1000)
    sql = """
    SELECT asset_id, doc_type, structured_data 
    FROM doc_assets 
    WHERE (structured_data->>'total_amount')::numeric > 1000
    AND structured_data->>'risk_level' = 'low';
    """

    cursor.execute(sql)
    results = cursor.fetchall()

    if results:
        for row in results:
            asset_id, doc_type, data = row
            print(f"\n📄 找到文档 [{doc_type}]")
            print(f"ID: {asset_id}")
            print(f"销售方: {data.get('seller')}")
            print(f"金额: {data.get('total_amount')}")
            print(f"明细: {json.dumps(data.get('items'), ensure_ascii=False)}")
    else:
        print("❌ 未找到符合条件的文档。")

    print("="*50 + "\n")

except (Exception, psycopg2.Error) as error:
    print("❌ 查询出错:", error)

finally:
    if 'conn' in locals() and conn:
        cursor.close()
        conn.close()