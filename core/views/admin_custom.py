from django.shortcuts import redirect, get_object_or_404, render
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.models import User, Group
from django.contrib.admin.models import LogEntry
from django.db.models import Count
from django.contrib import messages

from ..models import Client, Opportunite, Quote, OrdreFabrication, ProductionEntry, Material, Machine

@login_required
@staff_member_required
def admin_view(request):
    users = User.objects.all().order_by('-date_joined')
    total_users = users.count()
    active_users = users.filter(is_active=True).count()
    staff_users = users.filter(is_staff=True).count()
    groups = Group.objects.annotate(user_count=Count('user')).all()

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