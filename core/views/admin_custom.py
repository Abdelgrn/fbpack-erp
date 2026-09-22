from django.shortcuts import redirect, get_object_or_404, render
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.models import User, Group
from django.contrib.admin.models import LogEntry
from django.db.models import Count
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.core.management import call_command
from django.utils import timezone
from django.conf import settings
import traceback
import io
import os

from ..models import Client, Opportunite, Quote, OrdreFabrication, ProductionEntry, Material, Machine
from ..models.permissions import UserModulePermission
from ..models import robust_import_local_data


MODULES_LIST = [
    ('dashboard', '📊 Dashboard'),
    ('planning', '📅 Planning Gantt'),
    ('reporting', '📈 Reporting'),
    ('crm', '🤝 CRM & Devis'),
    ('prepress', '🎨 Prépresse & Outils'),
    ('planification', '📅 Planification Atelier'),
    ('production', '⚙️ Production Spécial'),
    ('stock', '📦 Stocks & Achats'),
    ('maintenance', '🔧 Maintenance'),
    ('drh', '👥 Ressources Humaines'),
    ('chat', '💬 Chat d\'Équipe'),
    ('import', '📥 Import Excel'),
    ('admin', '⚙️ Administration'),
]


@login_required
@staff_member_required
def admin_view(request):
    users = User.objects.all().order_by('-date_joined')
    total_users = users.count()
    active_users = users.filter(is_active=True).count()
    staff_users = users.filter(is_staff=True).count()
    groups = Group.objects.annotate(user_count=Count('user')).all()

    users_with_perms = []
    for u in users:
        try:
            perms = u.module_permissions
            modules_actifs = perms.get_allowed_modules()
        except UserModulePermission.DoesNotExist:
            modules_actifs = []
        users_with_perms.append({
            'user': u,
            'modules_actifs': modules_actifs,
            'nb_modules': len(modules_actifs),
        })

    stats_modules = [
        {
            'nom': 'CRM & Clients', 'icone': '🤝',
            'items': [
                {'label': 'Clients', 'count': Client.objects.count(), 'url': 'crm_view'},
                {'label': 'Opportunités', 'count': Opportunite.objects.count(), 'url': 'opportunites_view'},
                {'label': 'Devis', 'count': Quote.objects.count(), 'url': 'quotes_view'},
            ]
        },
        {
            'nom': 'Production', 'icone': '🏭',
            'items': [
                {'label': 'OF Multi-Processus', 'count': OrdreFabrication.objects.count(), 'url': 'of_list'},
                {'label': 'Saisies Production', 'count': ProductionEntry.objects.count(), 'url': 'prod_dashboard'},
            ]
        },
        {
            'nom': 'Stock & Machines', 'icone': '📦',
            'items': [
                {'label': 'Matières Premières', 'count': Material.objects.count(), 'url': 'stock_advanced'},
                {'label': 'Machines', 'count': Machine.objects.count(), 'url': 'machine_view'},
            ]
        },
    ]

    recent_actions = LogEntry.objects.select_related('user', 'content_type').order_by('-action_time')[:20]

    context = {
        'users': users, 'total_users': total_users,
        'active_users': active_users, 'staff_users': staff_users,
        'groups': groups, 'stats_modules': stats_modules,
        'recent_actions': recent_actions, 'page_title': 'Administration',
        'users_with_perms': users_with_perms,
        'modules_list': MODULES_LIST,
    }
    return render(request, 'admin_custom.html', context)


@login_required
@staff_member_required
def admin_add_user(request):
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        is_staff = request.POST.get('is_staff') == 'on'
        is_active = request.POST.get('is_active') == 'on'
        if username and password:
            if not User.objects.filter(username=username).exists():
                u = User.objects.create_user(username=username, email=email, password=password)
                u.is_staff = is_staff
                u.is_active = is_active
                u.save()

                perms = UserModulePermission.objects.create(user=u)
                for module_code, _ in MODULES_LIST:
                    field_name = f'can_access_{module_code}'
                    value = request.POST.get(f'module_{module_code}') == 'on'
                    setattr(perms, field_name, value)
                perms.save()

                messages.success(request, f"✅ Utilisateur '{username}' créé avec succès !")
            else:
                messages.error(request, f"❌ Le nom d'utilisateur '{username}' existe déjà.")
        else:
            messages.error(request, "❌ Nom d'utilisateur et mot de passe obligatoires.")
    return redirect('admin_view')


@login_required
@staff_member_required
def admin_edit_user(request, user_id):
    u = get_object_or_404(User, id=user_id)
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        is_staff = request.POST.get('is_staff') == 'on'
        is_active = request.POST.get('is_active') == 'on'
        u.username = username or u.username
        u.email = email
        u.is_staff = is_staff
        u.is_active = is_active
        if password:
            u.set_password(password)
        u.save()

        perms, created = UserModulePermission.objects.get_or_create(user=u)
        for module_code, _ in MODULES_LIST:
            field_name = f'can_access_{module_code}'
            value = request.POST.get(f'module_{module_code}') == 'on'
            setattr(perms, field_name, value)
        perms.save()

        messages.success(request, f"✅ Utilisateur '{u.username}' mis à jour !")
    return redirect('admin_view')


@login_required
@staff_member_required
def admin_toggle_user(request, user_id):
    u = get_object_or_404(User, id=user_id)
    if not u.is_superuser:
        u.is_active = not u.is_active
        u.save()
        etat = "activé" if u.is_active else "désactivé"
        messages.success(request, f"✅ Utilisateur '{u.username}' {etat}.")
    return redirect('admin_view')


@login_required
@staff_member_required
def admin_import_data_view(request):
    """Bouton d'importation manuelle des données du PC en 1 clic"""
    try:
        success, message = robust_import_local_data()
        if success:
            messages.success(request, message)
        else:
            messages.error(request, message)
    except Exception as e:
        print("=== ERREUR IMPORT DATA ===")
        print(traceback.format_exc())
        messages.error(request, f"❌ Erreur critique lors de l'importation: {type(e).__name__} - {str(e)}")
    return redirect('admin_view')


@login_required
@staff_member_required
def admin_restore_backup_view(request):
    """Permet de charger n'importe quel fichier JSON de sauvegarde TOTALE téléchargé par l'utilisateur"""
    if request.method == 'POST' and request.FILES.get('backup_file'):
        backup_file = request.FILES['backup_file']
        if not backup_file.name.endswith('.json'):
            messages.error(request, "❌ Veuillez sélectionner un fichier au format .json")
            return redirect('admin_view')

        try:
            target_path = os.path.join(getattr(settings, 'BASE_DIR', ''), 'FULL_BACKUP_FBPACK.json')
            with open(target_path, 'wb+') as destination:
                for chunk in backup_file.chunks():
                    destination.write(chunk)

            success, message = robust_import_local_data(specific_file=target_path)
            if success:
                messages.success(request, f"🎉 RESTAURATION TOTALE RÉUSSIE ! {message}")
            else:
                messages.error(request, f"❌ Erreur lors de la restauration: {message}")
        except Exception as e:
            messages.error(request, f"❌ Erreur lors de la lecture du fichier: {e}")
    else:
        messages.error(request, "❌ Aucun fichier de sauvegarde sélectionné.")

    return redirect('admin_view')


def export_database_backup(request):
    """Génère un fichier JSON de sauvegarde TOTALE ET ABSOLUE de l'ERP."""
    token = request.GET.get('token', '')
    secret_key = getattr(settings, 'SECRET_KEY', 'django-ultimate-erp-secret-key')
    
    if not (request.user.is_authenticated and request.user.is_superuser or (token and token == secret_key)):
        return JsonResponse({'error': 'Accès non autorisé'}, status=403)

    try:
        buf = io.StringIO()
        call_command(
            'dumpdata', 'core', 'auth.user', 'auth.group', 'core.usermodulepermission', 'admin.logentry',
            exclude=['contenttypes', 'auth.permission'], indent=2, stdout=buf
        )
        buf.seek(0)

        timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
        filename = f"FULL_BACKUP_FBPACK_{timestamp}.json"

        response = HttpResponse(buf.getvalue(), content_type='application/json')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
    except Exception as e:
        return JsonResponse({'error': f"Erreur lors de la sauvegarde: {e}"}, status=500)