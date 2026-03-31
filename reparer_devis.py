import os

print("🔧 Ajout du modèle Devis (Quote) manquant...")

models_path = "core/models.py"

with open(models_path, "r", encoding="utf-8") as f:
    content = f.read()

# Le code du modèle Devis
quote_model = """
class Quote(models.Model):
    client = models.ForeignKey(Client, on_delete=models.CASCADE)
    reference = models.CharField("Référence", max_length=50)
    date = models.DateField(default=timezone.now)
    total_amount = models.DecimalField("Montant Total", max_digits=12, decimal_places=2, default=0)
    status = models.CharField(max_length=20, default='DRAFT', choices=[('DRAFT', 'Brouillon'), ('SENT', 'Envoyé'), ('SIGNED', 'Signé')])
    pdf_file = models.FileField("PDF Signé", upload_to='quotes/', blank=True, null=True)

    def __str__(self): return self.reference
"""

# On l'ajoute à la fin du fichier si il n'existe pas
if "class Quote" not in content:
    with open(models_path, "a", encoding="utf-8") as f: # "a" pour append (ajouter à la fin)
        f.write("\n" + quote_model)
    print("✅ Modèle Quote ajouté dans models.py")
else:
    print("ℹ️ Le modèle Quote existe déjà.")

# On ajoute aussi l'admin pour le voir
admin_path = "core/admin.py"
with open(admin_path, "r", encoding="utf-8") as f:
    admin_content = f.read()

if "admin.site.register(Quote)" not in admin_content:
    with open(admin_path, "a", encoding="utf-8") as f:
        f.write("\nadmin.site.register(Quote)")
    print("✅ Quote ajouté à l'interface Admin.")

print("\n⚠️ ACTION REQUISE :")
print("1. python manage.py makemigrations")
print("2. python manage.py migrate")
print("3. Relancez le script des rôles (creer_roles.py)")