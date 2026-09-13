with open("core/views.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

result = []
found = False
for i, line in enumerate(lines):
    if "def parse_time_safe(val):" in line and not found:
        found = True
        result.append(line)
        continue
    if found and "if hasattr(val," in line and "hour" in line and "pd.isna" not in lines[i-3]:
        result.append("        try:\n")
        result.append("            if pd.isna(val):\n")
        result.append("                return None\n")
        result.append("        except (TypeError, ValueError):\n")
        result.append("            pass\n")
        result.append("        try:\n")
        result.append(line)
        found = False
        continue
    result.append(line)

with open("core/views.py", "w", encoding="utf-8") as f:
    f.writelines(result)
print("OK! parse_time_safe corrigee!")
