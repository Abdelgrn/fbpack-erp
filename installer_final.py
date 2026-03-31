import os
import sys

# Configuration du projet
PROJECT_NAME = "fbpack"
APP_NAME = "core"

# Structure des fichiers
files = {
    "requirements.txt": """
django
pandas
openpyxl
pillow
""",
    f"{PROJECT_NAME}/__init__.py": "",
    f"{PROJECT_NAME}/settings.py": f"""
from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = 'django-ultimate-erp-secret-key'
DEBUG = True
ALLOWED_HOSTS = ['*']

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    '{APP_NAME}',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = '{PROJECT_NAME}.urls'

TEMPLATES = [
    {{
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {{
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        }},
    }},
]

WSGI_APPLICATION = '{PROJECT_NAME}.wsgi.application'

DATABASES = {{
    'default': {{
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }}
}}

LANGUAGE_CODE = 'fr-fr'
TIME_ZONE = 'Europe/Paris'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'
""",
    f"{PROJECT_NAME}/urls.py": f"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('{APP_NAME}.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
""",
    f"{PROJECT_NAME}/wsgi.py": f"""
import os
from django.core.wsgi import get_wsgi_application
os.environ.setdefault('DJANGO_SETTINGS_MODULE', '{PROJECT_NAME}.settings')
application = get_wsgi_application()
""",
    f"{APP_NAME}/__init__.py": "",
    
    # ---------------------------------------------------------
    # MODÈLES DE DONNÉES (Le Cœur du Système)
    # ---------------------------------------------------------
    f"{APP_NAME}/models.py": """
from django.db import models
from django.utils import timezone
from django.utils.html import format_html
import datetime

# --- A. CRM ---
class Client(models.Model):
    STATUS_CHOICES = [('PROSPECT', 'Prospect'), ('ACTIVE', 'Actif'), ('VIP', 'VIP'), ('LOST', 'Perdu')]
    name = models.CharField("Raison Sociale", max_length=200)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PROSPECT')
    sector = models.CharField("Secteur", max_length=100, blank=True)
    city = models.CharField("Ville", max_length=100)
    phone = models.CharField("Téléphone", max_length=50)
    email = models.EmailField(blank=True)
    
    def __str__(self): return self.name

class ClientContact(models.Model):
    client = models.ForeignKey(Client, on_delete=models.CASCADE)
    name = models.CharField("Nom", max_length=100)
    role = models.CharField("Fonction", max_length=100)
    is_primary = models.BooleanField("Principal", default=False)

class InteractionLog(models.Model):
    client = models.ForeignKey(Client, on_delete=models.CASCADE)
    date = models.DateTimeField(default=timezone.now)
    type = models.CharField(max_length=50, choices=[('CALL', 'Appel'), ('EMAIL', 'Email'), ('MEET', 'Rdv')])
    summary = models.CharField("Résumé", max_length=200)
    details = models.TextField("Détails")

# --- B. PREPRESSE (Fiches Techniques & Outillage) ---
class TechnicalProduct(models.Model):
    client = models.ForeignKey(Client, on_delete=models.CASCADE)
    ref_internal = models.CharField("Ref Interne", max_length=50, unique=True)
    name = models.CharField("Désignation", max_length=200)
    
    # Structure
    structure_type = models.CharField(max_length=20, choices=[('MONO', 'Mono'), ('DUPLEX', 'Duplex'), ('TRIPLEX', 'Triplex')])
    width_mm = models.FloatField("Laize (mm)")
    cut_length_mm = models.FloatField("Pas de coupe (mm)", default=0)
    
    # Fichiers
    artwork_file = models.FileField("Fichier Graphique (AI/PDF)", upload_to='artwork/', blank=True)
    artwork_version = models.IntegerField(default=1)
    
    def __str__(self): return f"{self.ref_internal} - {self.name}"

class Tooling(models.Model):
    TYPE_CHOICES = [('CYL', 'Cylindre Hélio'), ('CLICHE', 'Cliché Flexo')]
    product = models.ForeignKey(TechnicalProduct, on_delete=models.CASCADE)
    tool_type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    serial_number = models.CharField("N° Série", max_length=100)
    
    # Usure
    max_impressions = models.IntegerField("Durée de vie (tours)", default=1000000)
    current_impressions = models.IntegerField("Tours actuels", default=0)
    
    def wear_percent(self):
        if self.max_impressions == 0: return 0
        return round((self.current_impressions / self.max_impressions) * 100, 1)

# --- E. STOCK (Matières Premières) ---
class Supplier(models.Model):
    name = models.CharField("Fournisseur", max_length=200)
    email = models.EmailField()
    def __str__(self): return self.name

class Material(models.Model):
    CAT_CHOICES = [('FILM', 'Film/Papier'), ('INK', 'Encre'), ('GLUE', 'Colle'), ('SOLV', 'Solvant')]
    name = models.CharField("Désignation", max_length=200)
    category = models.CharField(max_length=10, choices=CAT_CHOICES)
    quantity = models.FloatField("Stock Réel")
    unit = models.CharField("Unité", max_length=10, default='kg')
    min_threshold = models.FloatField("Stock Alerte (Min)")
    supplier = models.ForeignKey(Supplier, on_delete=models.SET_NULL, null=True)
    price_per_unit = models.DecimalField("Prix Unitaire", max_digits=10, decimal_places=2, default=0)

    def is_low_stock(self):
        return self.quantity <= self.min_threshold

    def __str__(self): return self.name

# --- D. MACHINES & MAINTENANCE ---
class Machine(models.Model):
    STATUS_CHOICES = [('RUN', 'En Production'), ('STOP', 'Arrêt'), ('MAINT', 'Maintenance'), ('PANNE', 'En Panne')]
    name = models.CharField("Nom Machine", max_length=100)
    type = models.CharField(max_length=50, choices=[('EXT', 'Extrudeuse'), ('IMP', 'Imprimeuse'), ('DEC', 'Découpeuse')])
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='STOP')

    def __str__(self): return self.name

class MaintenanceSchedule(models.Model):
    machine = models.ForeignKey(Machine, on_delete=models.CASCADE)
    task = models.CharField("Tâche", max_length=200)
    frequency_days = models.IntegerField("Fréquence (jours)")
    last_done = models.DateField("Dernière fois")
    
    @property
    def next_due(self):
        return self.last_done + datetime.timedelta(days=self.frequency_days)

class IncidentLog(models.Model):
    machine = models.ForeignKey(Machine, on_delete=models.CASCADE)
    date = models.DateTimeField(auto_now_add=True)
    issue = models.CharField("Panne", max_length=200)
    action_taken = models.TextField("Action Corrective")
    downtime_minutes = models.IntegerField("Temps d'arrêt (min)", default=0)

# --- C. PRODUCTION (Planning & OF) ---
class ProductionOrder(models.Model):
    of_number = models.CharField("N° OF", max_length=50, unique=True)
    client = models.ForeignKey(Client, on_delete=models.CASCADE)
    product = models.ForeignKey(TechnicalProduct, on_delete=models.CASCADE)
    machine = models.ForeignKey(Machine, on_delete=models.SET_NULL, null=True)
    
    quantity_planned = models.FloatField("Qté Prévue (kg/m)")
    start_time = models.DateTimeField("Début Prévu")
    end_time = models.DateTimeField("Fin Prévue")
    
    status = models.CharField(max_length=20, default='PLANNED', choices=[('PLANNED', 'Planifié'), ('IN_PROGRESS', 'En cours'), ('DONE', 'Terminé'), ('LATE', 'En Retard')])
    
    # BAT Link
    bat_file = models.FileField("BAT Validé", upload_to='bat/', blank=True, null=True)
    
    # Real Time Data (Saisi par l'opérateur)
    produced_qty = models.FloatField("Qté Produite", default=0)
    waste_qty = models.FloatField("Déchets (kg)", default=0)
    
    def __str__(self): return f"OF {self.of_number} - {self.product.name}"

class ConsumptionLog(models.Model):
    of = models.ForeignKey(ProductionOrder, on_delete=models.CASCADE, related_name='consumptions')
    material = models.ForeignKey(Material, on_delete=models.CASCADE)
    quantity_used = models.FloatField("Qté Consommée")
    
    def save(self, *args, **kwargs):
        # Décrémente le stock automatiquement
        self.material.quantity -= self.quantity_used
        self.material.save()
        super().save(*args, **kwargs)

class PurchaseOrder(models.Model):
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE)
    date = models.DateField(auto_now_add=True)
    status = models.CharField(max_length=20, default='DRAFT', choices=[('DRAFT', 'Brouillon'), ('SENT', 'Envoyée'), ('RECEIVED', 'Reçue')])
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
""",

    # ---------------------------------------------------------
    # ADMIN (Configuration Back-Office Puissante)
    # ---------------------------------------------------------
    f"{APP_NAME}/admin.py": """
from django.contrib import admin
from django.utils.html import format_html
from .models import *

# --- CRM ---
class ContactInline(admin.TabularInline):
    model = ClientContact
    extra = 1

class ClientAdmin(admin.ModelAdmin):
    list_display = ('name', 'status_badge', 'city', 'sector')
    list_filter = ('status', 'sector')
    search_fields = ('name', 'city')
    inlines = [ContactInline]
    
    def status_badge(self, obj):
        colors = {'PROSPECT': 'blue', 'ACTIVE': 'green', 'VIP': 'purple', 'LOST': 'red'}
        return format_html(f'<span style="color: {colors.get(obj.status, "black")}; font-weight:bold;">{obj.get_status_display()}</span>')

# --- STOCK ---
class MaterialAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'quantity', 'unit', 'stock_alert')
    list_filter = ('category', 'supplier')
    
    def stock_alert(self, obj):
        if obj.is_low_stock():
            return format_html('<span style="color:red; font-weight:bold;">⚠️ BAS ({})</span>', obj.min_threshold)
        return "OK"

# --- PRODUCTION ---
class ConsumptionInline(admin.TabularInline):
    model = ConsumptionLog
    extra = 1
    autocomplete_fields = ['material']

class OFAdmin(admin.ModelAdmin):
    list_display = ('of_number', 'client', 'product', 'machine', 'start_time', 'status')
    list_filter = ('status', 'machine')
    search_fields = ('of_number', 'client__name')
    inlines = [ConsumptionInline]

# --- PREPRESSE ---
class ToolingAdmin(admin.ModelAdmin):
    list_display = ('serial_number', 'product', 'tool_type', 'wear_progress')
    
    def wear_progress(self, obj):
        percent = obj.wear_percent()
        color = 'green'
        if percent > 80: color = 'red'
        elif percent > 50: color = 'orange'
        return format_html(f'<div style="width:100px; background:#ddd; border-radius:4px;"><div style="width:{percent}%; background:{color}; height:10px; border-radius:4px;"></div></div> {percent}%')

# --- MACHINE ---
class MaintenanceInline(admin.TabularInline):
    model = MaintenanceSchedule
    extra = 1

class IncidentInline(admin.TabularInline):
    model = IncidentLog
    extra = 0

class MachineAdmin(admin.ModelAdmin):
    list_display = ('name', 'type', 'status')
    inlines = [MaintenanceInline, IncidentInline]

admin.site.register(Client, ClientAdmin)
admin.site.register(TechnicalProduct)
admin.site.register(Tooling, ToolingAdmin)
admin.site.register(Material, MaterialAdmin)
admin.site.register(Supplier)
admin.site.register(Machine, MachineAdmin)
admin.site.register(ProductionOrder, OFAdmin)
admin.site.register(InteractionLog)
admin.site.register(PurchaseOrder)
""",

    # ---------------------------------------------------------
    # VUES & LOGIQUE MÉTIER
    # ---------------------------------------------------------
    f"{APP_NAME}/views.py": """
from django.shortcuts import render
from .models import *
from django.db.models import Sum, Count, Q
from django.utils import timezone

def dashboard(request):
    # KPIs globaux
    context = {
        'count_clients': Client.objects.count(),
        'count_of_running': ProductionOrder.objects.filter(status='IN_PROGRESS').count(),
        'low_stock_count': len([m for m in Material.objects.all() if m.is_low_stock()]),
        'machines': Machine.objects.all(),
        # Pour le graphique "Charge"
        'orders_per_machine': ProductionOrder.objects.values('machine__name').annotate(count=Count('id')),
    }
    return render(request, 'dashboard.html', context)

def production_gantt(request):
    # Vue Gantt simple
    orders = ProductionOrder.objects.exclude(status='DONE').order_by('machine', 'start_time')
    return render(request, 'production/gantt.html', {'orders': orders})

def reporting(request):
    # 1. Analyse Prod : Retards
    delayed_ofs = ProductionOrder.objects.filter(status='LATE')
    
    # 2. Analyse Commerciale : Top Clients
    top_clients = ProductionOrder.objects.values('client__name').annotate(
        total_kg=Sum('produced_qty')
    ).order_by('-total_kg')[:5]
    
    # 3. Analyse Stock : Top Consommation
    top_consumptions = ConsumptionLog.objects.values('material__name').annotate(
        total_used=Sum('quantity_used')
    ).order_by('-total_used')[:5]

    context = {
        'delayed_ofs': delayed_ofs,
        'top_clients_labels': [c['client__name'] for c in top_clients],
        'top_clients_data': [c['total_kg'] for c in top_clients],
        'top_consumptions_labels': [c['material__name'] for c in top_consumptions],
        'top_consumptions_data': [c['total_used'] for c in top_consumptions],
    }
    return render(request, 'reporting.html', context)
""",
    f"{APP_NAME}/urls.py": """
from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('production/planning/', views.production_gantt, name='planning'),
    path('reporting/', views.reporting, name='reporting'),
]
""",

    # ---------------------------------------------------------
    # TEMPLATES (Interface UI/UX Dark & Neon)
    # ---------------------------------------------------------
    "templates/base.html": """
<!DOCTYPE html>
<html lang="fr" class="dark">
<head>
    <meta charset="UTF-8">
    <title>Fb pack ERP Ultimate</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script>
        tailwind.config = {
            darkMode: 'class',
            theme: { extend: { colors: { neon: '#06b6d4', darkbg: '#0f172a', panel: '#1e293b' } } }
        }
    </script>
    <style>
        .glass { background: rgba(30, 41, 59, 0.7); backdrop-filter: blur(10px); border: 1px solid rgba(255,255,255,0.05); }
        .nav-link:hover { color: #06b6d4; background: rgba(255,255,255,0.05); }
    </style>
</head>
<body class="bg-darkbg text-gray-200 font-sans h-screen flex">
    <!-- SIDEBAR -->
    <aside class="w-64 bg-slate-900 border-r border-slate-700 flex flex-col">
        <div class="h-16 flex items-center justify-center border-b border-slate-700">
            <h1 class="text-xl font-bold tracking-wider">POLY<span class="text-neon">PACK</span></h1>
        </div>
        <nav class="flex-1 py-4 space-y-1">
            <a href="{% url 'dashboard' %}" class="nav-link flex items-center px-6 py-3 transition">📊 Dashboard</a>
            <a href="{% url 'planning' %}" class="nav-link flex items-center px-6 py-3 transition">🏭 Production (Gantt)</a>
            <a href="{% url 'reporting' %}" class="nav-link flex items-center px-6 py-3 transition">📈 Reporting</a>
            
            <div class="pt-4 pb-1 px-6 text-xs font-bold text-gray-500 uppercase">Modules Admin</div>
            <a href="/admin/core/client/" class="nav-link flex items-center px-6 py-2 transition text-sm">🤝 CRM & Devis</a>
            <a href="/admin/core/technicalproduct/" class="nav-link flex items-center px-6 py-2 transition text-sm">🎨 Prépresse & Outils</a>
            <a href="/admin/core/productionorder/" class="nav-link flex items-center px-6 py-2 transition text-sm">📝 Ordres Fabrication</a>
            <a href="/admin/core/material/" class="nav-link flex items-center px-6 py-2 transition text-sm">📦 Stocks & Achats</a>
            <a href="/admin/core/machine/" class="nav-link flex items-center px-6 py-2 transition text-sm">⚙️ Parc Machine</a>
        </nav>
        <div class="p-4 border-t border-slate-700 text-center">
            <a href="/admin/" class="text-xs text-neon hover:underline">Accès Back-Office Complet</a>
        </div>
    </aside>

    <!-- MAIN -->
    <main class="flex-1 overflow-auto p-8 relative">
        {% block content %}{% endblock %}
    </main>
</body>
</html>
""",

    "templates/dashboard.html": """
{% extends 'base.html' %}
{% block content %}
<h2 class="text-3xl font-bold text-white mb-6">Vue d'ensemble</h2>

<!-- KPIS -->
<div class="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
    <div class="glass p-4 rounded-xl border-t-4 border-neon">
        <p class="text-gray-400 text-xs uppercase">Clients Total</p>
        <p class="text-3xl font-bold text-white">{{ count_clients }}</p>
    </div>
    <div class="glass p-4 rounded-xl border-t-4 border-green-500">
        <p class="text-gray-400 text-xs uppercase">OF en cours</p>
        <p class="text-3xl font-bold text-white">{{ count_of_running }}</p>
    </div>
    <div class="glass p-4 rounded-xl border-t-4 border-red-500">
        <p class="text-gray-400 text-xs uppercase">Alertes Stock</p>
        <p class="text-3xl font-bold text-red-400">{{ low_stock_count }}</p>
    </div>
    <div class="glass p-4 rounded-xl border-t-4 border-yellow-500">
        <p class="text-gray-400 text-xs uppercase">Machines Actives</p>
        <p class="text-3xl font-bold text-white">{{ machines.count }}</p>
    </div>
</div>

<!-- MACHINES STATUS -->
<h3 class="text-xl font-bold text-white mb-4">État du Parc Machine (Temps Réel)</h3>
<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 mb-8">
    {% for m in machines %}
    <div class="glass p-4 rounded-lg flex items-center justify-between">
        <div>
            <h4 class="font-bold text-white">{{ m.name }}</h4>
            <span class="text-xs text-gray-400">{{ m.get_type_display }}</span>
        </div>
        <span class="px-3 py-1 rounded text-xs font-bold
            {% if m.status == 'RUN' %}bg-green-900 text-green-300 shadow-[0_0_10px_rgba(34,197,94,0.5)]
            {% elif m.status == 'PANNE' %}bg-red-900 text-red-300 animate-pulse
            {% elif m.status == 'MAINT' %}bg-yellow-900 text-yellow-300
            {% else %}bg-slate-700 text-gray-400{% endif %}">
            {{ m.get_status_display }}
        </span>
    </div>
    {% endfor %}
</div>
{% endblock %}
""",

    "templates/production/gantt.html": """
{% extends 'base.html' %}
{% block content %}
<div class="flex justify-between items-center mb-6">
    <h2 class="text-2xl font-bold text-white">Planning de Production (Gantt Visuel)</h2>
    <a href="/admin/core/productionorder/add/" class="bg-neon text-black px-4 py-2 rounded text-sm font-bold hover:bg-cyan-400">Créer un OF +</a>
</div>

<div class="glass p-6 rounded-xl overflow-x-auto">
    <div class="min-w-[800px]">
        {% regroup orders by machine as machine_list %}
        {% for machine in machine_list %}
        <div class="mb-8">
            <h3 class="text-lg font-bold text-white mb-2 flex items-center">
                <span class="w-3 h-3 bg-gray-500 rounded-full mr-2"></span> {{ machine.grouper.name }}
            </h3>
            <div class="relative h-16 bg-slate-800 rounded-lg flex items-center px-2 space-x-1 overflow-hidden">
                <!-- Timeline simplifiée pour l'affichage -->
                {% for of in machine.list %}
                <div class="h-12 rounded flex flex-col justify-center px-3 min-w-[120px] cursor-pointer hover:brightness-110 transition
                    {% if of.status == 'IN_PROGRESS' %}bg-green-600 border border-green-400
                    {% elif of.status == 'LATE' %}bg-red-600 border border-red-400
                    {% else %}bg-blue-600 border border-blue-400{% endif %}"
                    title="{{ of.start_time }} -> {{ of.end_time }}">
                    
                    <span class="text-xs font-bold text-white">OF #{{ of.of_number }}</span>
                    <span class="text-[10px] text-gray-200 truncate">{{ of.client.name }}</span>
                    <span class="text-[10px] text-gray-300">{{ of.quantity_planned }}kg</span>
                </div>
                <div class="w-px h-full bg-slate-700 mx-1"></div> <!-- Séparateur -->
                {% endfor %}
            </div>
        </div>
        {% empty %}
        <p class="text-gray-500">Aucun ordre de fabrication planifié.</p>
        {% endfor %}
    </div>
</div>
{% endblock %}
""",

    "templates/reporting.html": """
{% extends 'base.html' %}
{% block content %}
<h2 class="text-2xl font-bold text-white mb-6">Reporting & Analyses</h2>

<div class="grid grid-cols-1 lg:grid-cols-2 gap-8">
    <!-- CHART 1: Top Clients -->
    <div class="glass p-6 rounded-xl">
        <h3 class="text-lg font-bold text-white mb-4">Top 5 Clients (Volume Kg)</h3>
        <canvas id="clientChart"></canvas>
    </div>

    <!-- CHART 2: Consommation Matière -->
    <div class="glass p-6 rounded-xl">
        <h3 class="text-lg font-bold text-white mb-4">Top Consommation Matières</h3>
        <canvas id="matChart"></canvas>
    </div>
</div>

<div class="mt-8 glass p-6 rounded-xl border-l-4 border-red-500">
    <h3 class="text-lg font-bold text-white mb-4">🚨 Alertes Retards Production</h3>
    <table class="w-full text-left text-sm text-gray-400">
        <thead class="bg-slate-800 text-gray-200 uppercase">
            <tr>
                <th class="p-3">OF N°</th>
                <th class="p-3">Client</th>
                <th class="p-3">Date Prévue</th>
                <th class="p-3">Statut</th>
            </tr>
        </thead>
        <tbody class="divide-y divide-slate-700">
            {% for of in delayed_ofs %}
            <tr>
                <td class="p-3 font-mono text-neon">{{ of.of_number }}</td>
                <td class="p-3">{{ of.client.name }}</td>
                <td class="p-3">{{ of.end_time|date:"d M Y" }}</td>
                <td class="p-3"><span class="text-red-400 font-bold">EN RETARD</span></td>
            </tr>
            {% empty %}
            <tr><td colspan="4" class="p-3 text-center text-green-400">Aucun retard ! Tout est sous contrôle.</td></tr>
            {% endfor %}
        </tbody>
    </table>
</div>

<script>
    // Chart Clients
    new Chart(document.getElementById('clientChart'), {
        type: 'bar',
        data: {
            labels: {{ top_clients_labels|safe }},
            datasets: [{
                label: 'Kg Produits',
                data: {{ top_clients_data|safe }},
                backgroundColor: '#06b6d4',
                borderRadius: 4
            }]
        },
        options: { plugins: { legend: { display: false } }, scales: { y: { grid: { color: '#334155' } }, x: { grid: { display: false } } } }
    });

    // Chart Matières
    new Chart(document.getElementById('matChart'), {
        type: 'doughnut',
        data: {
            labels: {{ top_consumptions_labels|safe }},
            datasets: [{
                data: {{ top_consumptions_data|safe }},
                backgroundColor: ['#f59e0b', '#ef4444', '#10b981', '#3b82f6', '#8b5cf6'],
                borderWidth: 0
            }]
        }
    });
</script>
{% endblock %}
""",

    "manage.py": f"""#!/usr/bin/env python
import os
import sys

def main():
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', '{PROJECT_NAME}.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError("Couldn't import Django.") from exc
    execute_from_command_line(sys.argv)

if __name__ == '__main__':
    main()
"""
}

# Fonction de création
def create_project():
    print(f"🚀 Initialisation de fbpack Ultimate ERP...")
    
    # Création dossiers
    dirs = [
        PROJECT_NAME, APP_NAME, f"{APP_NAME}/migrations",
        "templates", "templates/production",
        "media", "media/artwork", "media/bat", "media/bat/signed"
    ]
    for d in dirs:
        os.makedirs(d, exist_ok=True)
        if "migrations" in d: open(os.path.join(d, "__init__.py"), "w").close()

    # Création fichiers
    for filepath, content in files.items():
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content.strip())
            print(f"✅ {filepath}")

    print("\n🏁 INSTALLATION TERMINÉE.")
    print("-------------------------------------------------------")
    print("1. Créez l'environnement : python -m venv venv")
    print("2. Activez-le (Windows: venv\\Scripts\\activate | Mac: source venv/bin/activate)")
    print("3. Installez les libs :    pip install -r requirements.txt")
    print("4. Migrez la base de données :")
    print("   python manage.py makemigrations")
    print("   python manage.py migrate")
    print("5. Créez un admin :        python manage.py createsuperuser")
    print("6. Lancez le serveur :     python manage.py runserver")
    print("-------------------------------------------------------")
    print("👉 Accès Dashboard : http://127.0.0.1:8000/")
    print("👉 Accès Admin/Saisie : http://127.0.0.1:8000/admin/")

if __name__ == "__main__":
    create_project()