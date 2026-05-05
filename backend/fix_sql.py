import re

with open("main.py", "r", encoding="utf-8") as f:
    content = f.read()

# 只替换 SQL 语句中的 %s（在 cursor.execute( 后面的字符串内）
# 简单起见，直接全局替换所有 %s 为 ?，但要避免破坏 f-string 或 printf 格式化
# 更安全的做法：匹配 cursor.execute( 内的字符串
pattern = r"(cursor\.execute\([\s\n]*['\"])(.*?)(['\"])"
def repl(m):
    prefix = m.group(1)
    sql = m.group(2)
    suffix = m.group(3)
    # 替换参数占位符
    new_sql = re.sub(r'%s', '?', sql)
    return prefix + new_sql + suffix

new_content = re.sub(pattern, repl, content, flags=re.DOTALL)

with open("main.py", "w", encoding="utf-8") as f:
    f.write(new_content)

print("已替换 SQL 中的 %s 为 ?")