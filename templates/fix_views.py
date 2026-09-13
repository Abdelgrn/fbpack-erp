@"
with open('core/views.py', 'r', encoding='utf-8') as f:
    content = f.read()

old_text = '''    if hasattr(val, 'hour'):
            return val
        if hasattr(val, 'time'):
            return val.time()'''

new_text = '''    try:
            if pd.isna(val):
                return None
        except (TypeError, ValueError):
            pass
        if hasattr(val, 'hour'):
            return val
        if hasattr(val, 'time'):
            return val.time()'''

if old_text in content:
    content = content.replace(old_text, new_text, 1)
    with open('core/views.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print('OK! Correction appliquee!')
else:
    print('ERREUR: texte non trouve')
"@ | Out-File -FilePath fix_views.py -Encoding utf8
