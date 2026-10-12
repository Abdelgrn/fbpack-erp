from django.shortcuts import redirect, get_object_or_404, render
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.models import User, Group
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.views.decorators.http import require_POST
from django.contrib.admin.models import LogEntry
from django.db.models import Count, Q
from django.contrib import messages
from django.http import HttpResponse, JsonResponse, FileResponse
from django.core.management import call_command
from django.utils import timezone
from django.conf import settings
from django.templatetags.static import static
import traceback
import io
import os
import shutil
import secrets

from ..models import Client, Opportunite, Quote, OrdreFabrication, ProductionEntry, Material, Machine
from ..models.permissions import UserModulePermission, ModuleAdministrator, AdministrationAuditLog
from ..models import robust_import_local_data
from ..services.full_backup import create_full_backup, validate_and_extract, restore_media


MODULES_LIST = [
    ('dashboard', '📊 Dashboard'),
    ('planning', '📅 Planning Gantt'),
    ('reporting', '📈 Reporting'),
    ('kpi', '📊 KPI & Data Analyse'),
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


def _managed_modules(user):
    if user.is_superuser:
        return [code for code, _ in MODULES_LIST]
    return list(ModuleAdministrator.objects.filter(user=user, is_active=True).values_list('module', flat=True))


def _audit(request, action, target=None, module='', details=''):
    AdministrationAuditLog.objects.create(actor=request.user, target_user=target, action=action,
        module=module, details=details, ip_address=request.META.get('REMOTE_ADDR'))


def erp_admin_required(view_func):
    from functools import wraps
    from django.core.exceptions import PermissionDenied
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        if request.user.is_superuser or _managed_modules(request.user):
            return view_func(request, *args, **kwargs)
        raise PermissionDenied("Accès Administration ERP refusé.")
    return wrapped


def _can_manage_user(actor, target):
    if actor.is_superuser:
        return True
    if target.is_superuser or target == actor:
        return False
    managed = _managed_modules(actor)
    try:
        return bool(set(managed) & set(target.module_permissions.get_allowed_modules()))
    except UserModulePermission.DoesNotExist:
        return False


@login_required
@erp_admin_required
def admin_view(request):
    managed_modules = _managed_modules(request.user)
    users = User.objects.all().order_by('-date_joined')
    if not request.user.is_superuser:
        access_filter = Q()
        for code in managed_modules:
            access_filter |= Q(**{f'module_permissions__can_access_{code}': True})
        users = users.filter(access_filter).exclude(is_superuser=True).distinct()
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
        'managed_modules': managed_modules, 'is_global_admin': request.user.is_superuser,
        'module_delegations': ModuleAdministrator.objects.filter(is_active=True).select_related('user','granted_by'),
        'audit_logs': AdministrationAuditLog.objects.select_related('actor','target_user')[:30],
    }
    return render(request, 'admin_custom.html', context)


@login_required
@erp_admin_required
@require_POST
def admin_add_user(request):
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '').strip()
        is_staff = request.POST.get('is_staff') == 'on' if request.user.is_superuser else False
        is_active = request.POST.get('is_active') == 'on'
        create_superuser = request.POST.get('create_superuser') == 'on'
        if create_superuser:
            if not request.user.is_superuser:
                from django.core.exceptions import PermissionDenied
                raise PermissionDenied("Seul un superadministrateur peut créer un autre superadministrateur.")
            if not request.user.check_password(request.POST.get('admin_current_password', '')):
                messages.error(request, "Mot de passe du superadministrateur connecté incorrect.")
                return redirect('admin_view')
            if request.POST.get('admin_confirmation', '').strip().upper() != 'CONFIRMER':
                messages.error(request, "Saisissez exactement CONFIRMER pour créer le superadministrateur.")
                return redirect('admin_view')
            is_staff = True
            is_active = True

        # Création : mot de passe OBLIGATOIRE et validé par la politique Django.
        if username and password:
            try:
                validate_password(password)
            except ValidationError as exc:
                messages.error(request, "❌ Mot de passe refusé : " + " ".join(exc.messages))
                return redirect('admin_view')
            if not User.objects.filter(username=username).exists():
                u = User.objects.create_user(username=username, email=email, password=password)
                u.is_staff = is_staff
                u.is_superuser = create_superuser
                u.is_active = is_active
                u.save()

                perms = UserModulePermission.objects.create(user=u)
                for module_code, _ in MODULES_LIST:
                    field_name = f'can_access_{module_code}'
                    value = create_superuser or (request.POST.get(f'module_{module_code}') == 'on' and module_code in _managed_modules(request.user))
                    setattr(perms, field_name, value)
                perms.save()

                _audit(request, 'SUPERUSER_CREATED' if create_superuser else 'USER_CREATED', u, 'admin' if create_superuser else '', request.POST.get('admin_reason', '').strip())
                if create_superuser:
                    messages.success(request, f"👑 Superadministrateur '{username}' créé avec succès.")
                else:
                    messages.success(request, f"✅ Utilisateur '{username}' créé avec succès !")
            else:
                messages.error(request, f"❌ Le nom d'utilisateur '{username}' existe déjà.")
        else:
            messages.error(request, "❌ Nom d'utilisateur et mot de passe obligatoires pour la création.")
    return redirect('admin_view')


@login_required
@erp_admin_required
@require_POST
def admin_edit_user(request, user_id):
    """
    Modification d'un utilisateur :
    - modules / email / staff / actif : toujours modifiables
    - mot de passe : OPTIONNEL
      → si vide  = on GARDE l'ancien mot de passe (le manager n'a pas besoin de le connaître)
      → si rempli = on change uniquement le mot de passe
    """
    u = get_object_or_404(User, id=user_id)
    if not _can_manage_user(request.user, u):
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied('Vous ne pouvez pas administrer cet utilisateur.')

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '').strip()  # peut être vide
        is_staff = request.POST.get('is_staff') == 'on' if request.user.is_superuser else u.is_staff
        is_active = request.POST.get('is_active') == 'on'

        # Sécurité : ne pas retomber sur un username déjà pris par un autre compte
        if username and username != u.username and User.objects.filter(username=username).exclude(id=u.id).exists():
            messages.error(request, f"❌ Le nom d'utilisateur '{username}' est déjà utilisé.")
            return redirect('admin_view')

        # Infos de base (sans toucher au mot de passe)
        if username:
            u.username = username
        u.email = email

        # Ne pas retirer is_staff / is_active d'un superuser par erreur de case
        if not u.is_superuser:
            u.is_staff = is_staff
            u.is_active = is_active

        password_changed = False
        # >>> CLÉ MÉTIER : mot de passe optionnel à l'édition <<<
        if password:
            try:
                validate_password(password, user=u)
            except ValidationError as exc:
                messages.error(request, "❌ Mot de passe refusé : " + " ".join(exc.messages))
                return redirect('admin_view')
            u.set_password(password)
            password_changed = True

        u.save()

        # Modules ERP (indépendants du mot de passe)
        perms, created = UserModulePermission.objects.get_or_create(user=u)
        for module_code, _ in MODULES_LIST:
            field_name = f'can_access_{module_code}'
            # Les superusers gardent tout ; on enregistre quand même les cases pour cohérence
            if request.user.is_superuser or module_code in _managed_modules(request.user):
                value = request.POST.get(f'module_{module_code}') == 'on'
                setattr(perms, field_name, value)
        perms.save()

        if password_changed:
            messages.success(
                request,
                f"✅ Utilisateur '{u.username}' mis à jour (modules + nouveau mot de passe)."
            )
        else:
            messages.success(
                request,
                f"✅ Utilisateur '{u.username}' mis à jour. "
                f"Le mot de passe existant a été conservé (aucune saisie requise)."
            )

    return redirect('admin_view')


@login_required
@erp_admin_required
@require_POST
def admin_toggle_user(request, user_id):
    u = get_object_or_404(User, id=user_id)
    if not _can_manage_user(request.user, u):
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied('Vous ne pouvez pas administrer cet utilisateur.')
    if not u.is_superuser:
        u.is_active = not u.is_active
        u.save()
        etat = "activé" if u.is_active else "désactivé"
        messages.success(request, f"✅ Utilisateur '{u.username}' {etat}.")
    return redirect('admin_view')


@login_required
@require_POST
def admin_promote_superuser(request, user_id):
    if not request.user.is_superuser:
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied("Action réservée au superadministrateur.")
    target = get_object_or_404(User, pk=user_id)
    password = request.POST.get('current_password', '')
    confirmation = request.POST.get('confirmation', '').strip().upper()
    reason = request.POST.get('reason', '').strip()
    if not request.user.check_password(password):
        messages.error(request, "Mot de passe du superadministrateur incorrect.")
    elif confirmation != 'CONFIRMER':
        messages.error(request, "Saisissez exactement CONFIRMER pour valider.")
    elif target.is_superuser:
        messages.info(request, f"{target.username} est déjà superadministrateur.")
    else:
        target.is_active = True; target.is_staff = True; target.is_superuser = True
        target.save(update_fields=['is_active', 'is_staff', 'is_superuser'])
        _audit(request, 'SUPERUSER_GRANTED', target, 'admin', reason or 'Promotion depuis Administration ERP')
        messages.success(request, f"{target.username} est maintenant superadministrateur ERP.")
    return redirect('admin_view')


@login_required
@require_POST
def admin_demote_superuser(request, user_id):
    if not request.user.is_superuser:
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied("Action réservée au superadministrateur.")
    target = get_object_or_404(User, pk=user_id)
    password = request.POST.get('current_password', '')
    confirmation = request.POST.get('confirmation', '').strip().upper()
    reason = request.POST.get('reason', '').strip()
    if target == request.user:
        messages.error(request, "Vous ne pouvez pas retirer vos propres droits superadministrateur.")
    elif not request.user.check_password(password):
        messages.error(request, "Mot de passe du superadministrateur incorrect.")
    elif confirmation != 'CONFIRMER':
        messages.error(request, "Saisissez exactement CONFIRMER pour valider.")
    elif User.objects.filter(is_superuser=True, is_active=True).count() <= 1:
        messages.error(request, "Impossible de retirer le dernier superadministrateur actif.")
    elif not target.is_superuser:
        messages.info(request, f"{target.username} n'est pas superadministrateur.")
    else:
        target.is_superuser = False; target.is_staff = False
        target.save(update_fields=['is_superuser', 'is_staff'])
        _audit(request, 'SUPERUSER_REVOKED', target, 'admin', reason or 'Rétrogradation depuis Administration ERP')
        messages.success(request, f"Les droits superadministrateur de {target.username} ont été retirés.")
    return redirect('admin_view')


@login_required
@require_POST
def admin_assign_module_manager(request):
    if not request.user.is_superuser:
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied
    user = get_object_or_404(User, pk=request.POST.get('user_id'))
    module = request.POST.get('module')
    if module not in dict(MODULES_LIST) or module == 'admin' or user.is_superuser:
        messages.error(request, 'Délégation invalide.')
    else:
        ModuleAdministrator.objects.update_or_create(user=user, module=module,
            defaults={'granted_by': request.user, 'is_active': True})
        perms, _ = UserModulePermission.objects.get_or_create(user=user)
        setattr(perms, f'can_access_{module}', True); perms.can_access_admin = True; perms.save()
        _audit(request, 'MODULE_ADMIN_GRANTED', user, module)
        messages.success(request, f'{user.username} est maintenant administrateur du module {module}.')
    return redirect('admin_view')

@login_required
@require_POST
def admin_revoke_module_manager(request, delegation_id):
    if not request.user.is_superuser:
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied
    delegation = get_object_or_404(ModuleAdministrator, pk=delegation_id)
    delegation.is_active = False; delegation.save(update_fields=['is_active'])
    _audit(request, 'MODULE_ADMIN_REVOKED', delegation.user, delegation.module)
    messages.success(request, 'Délégation retirée.')
    return redirect('admin_view')


@login_required
@staff_member_required
@require_POST
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
@require_POST
def admin_restore_backup_view(request):
    if not request.user.is_superuser:
        return JsonResponse({'error':'Accès refusé'},status=403)
    uploaded=request.FILES.get('backup_file')
    if not uploaded or not uploaded.name.lower().endswith('.zip'):
        messages.error(request,'Sélectionnez une sauvegarde complète .zip.'); return redirect('admin_view')
    if not request.user.check_password(request.POST.get('current_password','')) or request.POST.get('confirmation','').strip().upper()!='RESTAURER':
        messages.error(request,'Mot de passe incorrect ou confirmation RESTAURER absente.'); return redirect('admin_view')
    root=work=None
    try:
        # Sauvegarde de sécurité avant toute modification.
        emergency, emergency_work=create_full_backup()
        root,work=validate_and_extract(uploaded)
        success,message=robust_import_local_data(specific_file=str(root/'database.json'))
        if not success: raise RuntimeError(message)
        restore_media(root)
        _audit(request,'FULL_RESTORE',request.user,'admin',f'Archive {uploaded.name}')
        messages.success(request,'Restauration complète réussie. Une sauvegarde de sécurité préalable a été créée côté serveur.')
    except Exception as exc:
        messages.error(request,f'Restauration annulée : {exc}')
    finally:
        if work: shutil.rmtree(work,ignore_errors=True)
    return redirect('admin_view')


def export_database_backup(request):
    expected=getattr(settings,'BACKUP_AGENT_TOKEN','')
    auth=request.headers.get('Authorization','')
    token=auth[7:] if auth.startswith('Bearer ') else ''
    authorized=(request.user.is_authenticated and request.user.is_superuser) or (expected and secrets.compare_digest(token,expected))
    if not authorized: return JsonResponse({'error':'Accès non autorisé'},status=403)
    archive=work=None
    try:
        archive,work=create_full_backup()
        response=FileResponse(open(archive,'rb'),content_type='application/zip',as_attachment=True,filename=archive.name)
        response._resource_closers.append(lambda: shutil.rmtree(work,ignore_errors=True))
        return response
    except Exception:
        if work: shutil.rmtree(work,ignore_errors=True)
        return JsonResponse({'error':'Échec de création de la sauvegarde'},status=500)


def manifest_view(request):
    """Génère un fichier manifest.json dynamique avec l'URL absolue exacte de logo1.png pour Chrome et Windows."""
    logo_url = request.build_absolute_uri(static('logo1.png'))
    data = {
        "name": "FB PACK ERP Ultimate",
        "short_name": "FB PACK",
        "description": "ERP FB PACK - Production, Stock, CRM, Maintenance, DRH",
        "start_url": "/",
        "scope": "/",
        "display": "standalone",
        "orientation": "any",
        "background_color": "#0f172a",
        "theme_color": "#0f172a",
        "lang": "fr",
        "icons": [
            {
                "src": logo_url,
                "sizes": "192x192",
                "type": "image/png",
                "purpose": "any"
            },
            {
                "src": logo_url,
                "sizes": "512x512",
                "type": "image/png",
                "purpose": "any"
            }
        ]
    }
    return JsonResponse(data, content_type="application/manifest+json")