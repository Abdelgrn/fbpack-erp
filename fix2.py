with open("core/views.py", "r", encoding="utf-8") as f:
    content = f.read()

bad = """def parse_time_safe(val):
    \"\"\"Parse une heure depuis Excel de mani\u00e8re robuste.\"\"\"
    if val is None or val == 0 or val == '' or str(val).strip() == '':
        return None
    try:
        try:
            if pd.isna(val):
                return None
        except (TypeError, ValueError):
            pass
        try:
        if hasattr(val, 'hour'):
            return val
        if hasattr(val, 'time'):
            return val.time()
        if isinstance(val, float):
            total_seconds = int(val * 24 * 3600)
            return datetime.time(total_seconds // 3600, (total_seconds % 3600) // 60)
        s = str(val).strip()
        parts = s.replace('h', ':').replace('H', ':').split(':')
        if len(parts) >= 2:
            return datetime.time(int(parts[0]), int(parts[1]))
        return None
    except Exception:
        return None"""

good = """def parse_time_safe(val):
    \"\"\"Parse une heure depuis Excel de maniere robuste.\"\"\"
    if val is None or val == 0 or val == '' or str(val).strip() == '':
        return None
    try:
        if pd.isna(val):
            return None
    except (TypeError, ValueError):
        pass
    try:
        s = str(val).strip()
        if s.lower() in ('nat', 'nan', 'none', 'nattype'):
            return None
        if hasattr(val, 'hour'):
            return val
        if hasattr(val, 'time'):
            return val.time()
        if isinstance(val, float):
            total_seconds = int(val * 24 * 3600)
            return datetime.time(total_seconds // 3600, (total_seconds % 3600) // 60)
        parts = s.replace('h', ':').replace('H', ':').split(':')
        if len(parts) >= 2:
            return datetime.time(int(parts[0]), int(parts[1]))
        return None
    except Exception:
        return None"""

if bad in content:
    content = content.replace(bad, good)
    with open("core/views.py", "w", encoding="utf-8") as f:
        f.write(content)
    print("OK! Fonction corrigee!")
else:
    print("Texte non trouve - tentative ligne par ligne")
    lines = content.split("\n")
    new_lines = []
    skip_until_next_def = False
    for i, line in enumerate(lines):
        if "def parse_time_safe(val):" in line:
            skip_until_next_def = True
            new_lines.append("def parse_time_safe(val):")
            new_lines.append('    """Parse une heure depuis Excel de maniere robuste."""')
            new_lines.append("    if val is None or val == 0 or val == '' or str(val).strip() == '':")
            new_lines.append("        return None")
            new_lines.append("    try:")
            new_lines.append("        if pd.isna(val):")
            new_lines.append("            return None")
            new_lines.append("    except (TypeError, ValueError):")
            new_lines.append("        pass")
            new_lines.append("    try:")
            new_lines.append("        s = str(val).strip()")
            new_lines.append("        if s.lower() in ('nat', 'nan', 'none', 'nattype'):")
            new_lines.append("            return None")
            new_lines.append("        if hasattr(val, 'hour'):")
            new_lines.append("            return val")
            new_lines.append("        if hasattr(val, 'time'):")
            new_lines.append("            return val.time()")
            new_lines.append("        if isinstance(val, float):")
            new_lines.append("            total_seconds = int(val * 24 * 3600)")
            new_lines.append("            return datetime.time(total_seconds // 3600, (total_seconds % 3600) // 60)")
            new_lines.append("        parts = s.replace('h', ':').replace('H', ':').split(':')")
            new_lines.append("        if len(parts) >= 2:")
            new_lines.append("            return datetime.time(int(parts[0]), int(parts[1]))")
            new_lines.append("        return None")
            new_lines.append("    except Exception:")
            new_lines.append("        return None")
            continue
        if skip_until_next_def:
            if (line.strip() == "" or line.startswith("    ")):
                continue
            else:
                skip_until_next_def = False
                new_lines.append(line)
        else:
            new_lines.append(line)
    with open("core/views.py", "w", encoding="utf-8") as f:
        f.write("\n".join(new_lines))
    print("OK! Correction ligne par ligne appliquee!")
