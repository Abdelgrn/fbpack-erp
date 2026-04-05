# fix_all_templates.py
# Placez ce fichier à la racine du projet et exécutez: python fix_all_templates.py

import os
import re

TEMPLATES_DIR = os.path.join('templates', 'drh')

# URLs qui N'EXISTENT PAS et leur remplacement
URL_REPLACEMENTS = {
    # URLs inexistantes → remplacer par POST vers la page liste
    "{% url 'drh:department_create' %}": "{% url 'department_list' %}",
    "{% url 'drh:department_detail' department.id %}": "#",
    "{% url 'drh:department_update' department.id %}": "{% url 'department_list' %}",
    "{% url 'drh:department_list' %}": "{% url 'department_list' %}",
    "{% url 'drh:positions' %}": "{% url 'position_list' %}",
    "{% url 'drh:employes' %}": "{% url 'employee_list' %}",
    
    # Supprimer tous les préfixes drh:
    "{% url 'drh:": "{% url '",
    
    # URLs inventées qui n'existent pas
    "{% url 'department_create' %}": "{% url 'department_list' %}",
    "{% url 'department_detail' department.id %}": "#",
    "{% url 'department_update' department.id %}": "{% url 'department_list' %}",
    "{% url 'department_delete' department.id %}": "{% url 'department_list' %}",
    
    # Position URLs inventées
    "{% url 'position_create' %}": "{% url 'position_list' %}",
    "{% url 'position_update' position.id %}": "{% url 'position_list' %}",
    "{% url 'position_delete' position.id %}": "{% url 'position_list' %}",
    
    # Shift URLs inventées
    "{% url 'shift_create' %}": "{% url 'shift_list' %}",
    "{% url 'shift_update' shift.id %}": "{% url 'shift_list' %}",
    "{% url 'shift_delete' shift.id %}": "{% url 'shift_list' %}",
    "{% url 'shift_assign_employees' shift.id %}": "{% url 'shift_list' %}",
    
    # Skill URLs inventées
    "{% url 'skill_create' %}": "{% url 'skill_list' %}",
    "{% url 'skill_delete' skill.id %}": "{% url 'skill_list' %}",
    "{% url 'category_create' %}": "{% url 'skill_list' %}",
    
    # Absence URLs inventées
    "{% url 'absence_create' %}": "{% url 'attendance_list' %}",
    
    # Contract URLs inventées
    "{% url 'contract_create' %}": "{% url 'employee_list' %}",
    
    # Payroll URLs inventées
    "{% url 'payroll_generate' %}": "{% url 'payslip_bulk_generate' %}",
    
    # EPI URLs inventées
    "{% url 'epi_distribute' %}": "{% url 'epi_list' %}",
    
    # Schedule URLs inventées
    "{% url 'schedule_generate' %}": "{% url 'schedule_list' %}",
}

def fix_templates():
    if not os.path.exists(TEMPLATES_DIR):
        print(f"❌ Dossier {TEMPLATES_DIR} introuvable!")
        return
    
    files_fixed = 0
    
    for filename in os.listdir(TEMPLATES_DIR):
        if not filename.endswith('.html'):
            continue
        
        filepath = os.path.join(TEMPLATES_DIR, filename)
        
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original = content
        
        # Appliquer les remplacements
        for old, new in URL_REPLACEMENTS.items():
            content = content.replace(old, new)
        
        # Regex: supprimer tout préfixe drh: restant
        content = re.sub(r"{%\s*url\s+'drh:(\w+)'", r"{% url '\1'", content)
        content = re.sub(r'{%\s*url\s+"drh:(\w+)"', r'{% url "\1"', content)
        
        if content != original:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            files_fixed += 1
            print(f"  ✅ Corrigé: {filename}")
        else:
            print(f"  ⏭️  Pas de changement: {filename}")
    
    print(f"\n🎉 {files_fixed} fichier(s) corrigé(s)!")

if __name__ == '__main__':
    fix_templates()