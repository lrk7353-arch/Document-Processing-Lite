import psycopg2

try:
    # 这里填我们刚才反复确认过的配置
    connection = psycopg2.connect(
        user="postgres",
        password="123456",  # 你的密码
        host="localhost",
        port="5433",        # 关键！我们查到的端口
        database="doc_smart_db"
    )

    cursor = connection.cursor()
    
    # 执行一条简单的查询
    cursor.execute("SELECT version();")
    record = cursor.fetchone()
    
    print("\n" + "="*50)
    print("✅ 成功连接到数据库！")
    print(f"数据库版本: {record[0]}")
    print("既然 Python 能连上，那个 VS Code 插件报什么错都不用管了！")
    print("="*50 + "\n")

except (Exception, psycopg2.Error) as error:
    print("\n❌ 连接失败:", error)

finally:
    if 'connection' in locals() and connection:
        cursor.close()
        connection.close()