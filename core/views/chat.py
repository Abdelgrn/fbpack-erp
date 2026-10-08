from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.contrib import messages
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
from django.db.models import Q, Max, Count, Prefetch

from ..models import ChatRoom, ChatMessage, UserPresence


def update_user_presence(user, current_room=None):
    """Marque l'utilisateur comme en ligne et nettoie les inactifs."""
    limite_activite = timezone.now() - timedelta(minutes=2)
    UserPresence.objects.filter(last_seen__lt=limite_activite, is_online=True).update(is_online=False)

    presence, created = UserPresence.objects.get_or_create(user=user)
    presence.is_online = True
    presence.current_room = current_room
    presence.save()


def get_user_active_modules(user):
    """
    Modules ERP réels de l'utilisateur via UserModulePermission
    (même source que le menu latéral / Administration).
    """
    if user.is_superuser:
        return {
            'dashboard', 'planning', 'reporting', 'crm', 'prepress',
            'planification', 'production', 'stock', 'maintenance',
            'drh', 'chat', 'import', 'admin',
        }

    try:
        from ..models.permissions import UserModulePermission
        perms = user.module_permissions
        modules = set(perms.get_allowed_modules() or [])
    except Exception:
        modules = set()

    # Tout le monde avec le chat peut au minimum être notifié sur Général / Urgences
    modules.add('chat')
    modules.add('dashboard')
    return modules


# MAPPING SALONS <-> MODULES ERP
ROOM_MODULE_MAP = {
    'commercial': ['crm'],
    'production': ['production', 'planification'],
    'technique': ['maintenance'],
    'drh': ['drh'],
    'stock': ['stock'],
}


def get_user_notifiable_rooms(user):
    """
    Retourne la liste des IDs des salons dont cet utilisateur doit RECEVOIR les notifications.
    - Général et Urgences : Tout le monde.
    - Commercial, Production, Technique : Seuls ceux qui ont le module ERP correspondant.
    - Private (DIRECT) : Uniquement si l'utilisateur est membre du chat privé.
    """
    user_modules = get_user_active_modules(user)
    
    # 1. Salons publics généraux (notifient tout le monde)
    public_always = ChatRoom.objects.filter(
        est_actif=True, 
        slug__in=['general', 'urgences']
    ).values_list('id', flat=True)

    # 2. Salons métiers filtrés par module
    allowed_slugs = []
    for room_slug, required_modules in ROOM_MODULE_MAP.items():
        if any(m in user_modules for m in required_modules) or user.is_superuser:
            allowed_slugs.append(room_slug)

    module_room_ids = ChatRoom.objects.filter(
        est_actif=True, 
        slug__in=allowed_slugs
    ).values_list('id', flat=True)

    # 3. Chats Privés (DIRECT) où l'utilisateur est membre
    private_ids = ChatRoom.objects.filter(
        est_actif=True, 
        type='DIRECT', 
        membres=user
    ).values_list('id', flat=True)

    return list(set(list(public_always) + list(module_room_ids) + list(private_ids)))


def ensure_default_rooms():
    """Crée les salons par défaut s'ils n'existent pas."""
    default_rooms = [
        {'name': 'Général', 'slug': 'general', 'type': 'GENERAL', 'icone': '💬', 'description': 'Discussion commune à tous'},
        {'name': 'Production', 'slug': 'production', 'type': 'PRODUCTION', 'icone': '🏭', 'description': 'Atelier & Planification'},
        {'name': 'Commercial', 'slug': 'commercial', 'type': 'COMMERCIAL', 'icone': '💼', 'description': 'Équipe Commerciale & Devis'},
        {'name': 'Technique', 'slug': 'technique', 'type': 'TECHNIQUE', 'icone': '🔧', 'description': 'Maintenance & Parc Machine'},
        {'name': 'Urgences', 'slug': 'urgences', 'type': 'URGENCE', 'icone': '🚨', 'description': 'Signalements & Problèmes bloquants'},
    ]
    for room_data in default_rooms:
        ChatRoom.objects.get_or_create(
            slug=room_data['slug'],
            defaults=room_data
        )


@login_required
def chat_home(request):
    update_user_presence(request.user, None)
    ensure_default_rooms()

    rooms = ChatRoom.objects.filter(est_actif=True).exclude(type='DIRECT').order_by('type', 'name')
    online_users = UserPresence.objects.filter(is_online=True).select_related('user')

    # Discussions privées
    private_rooms = ChatRoom.objects.filter(
        est_actif=True,
        type='DIRECT',
        membres=request.user
    ).prefetch_related('membres', 'messages').order_by('-date_creation')

    tous_utilisateurs = User.objects.filter(is_active=True).exclude(id=request.user.id).order_by('username')

    context = {
        'rooms': rooms,
        'online_users': online_users,
        'private_rooms': private_rooms,
        'tous_utilisateurs': tous_utilisateurs
    }
    return render(request, 'chat/chat_home.html', context)


@login_required
def chat_room(request, room_slug):
    room = get_object_or_404(ChatRoom, slug=room_slug, est_actif=True)

    # Sécurité pour les chats privés
    if room.type == 'DIRECT' and not room.membres.filter(id=request.user.id).exists():
        messages.error(request, "Vous n'avez pas accès à cette discussion privée.")
        return redirect('chat_home')

    room.membres.add(request.user)
    update_user_presence(request.user, room)

    chat_messages = room.messages.select_related('auteur').order_by('-date_envoi')[:50]
    chat_messages = list(chat_messages)[::-1]

    rooms = ChatRoom.objects.filter(est_actif=True).exclude(type='DIRECT').order_by('type', 'name')
    online_users = UserPresence.objects.filter(
        is_online=True, current_room=room
    ).select_related('user')

    private_rooms = ChatRoom.objects.filter(
        est_actif=True,
        type='DIRECT',
        membres=request.user
    ).order_by('-date_creation')

    tous_utilisateurs = User.objects.filter(is_active=True).exclude(id=request.user.id).order_by('username')

    room_display_name = room.name
    if room.type == 'DIRECT':
        autre_membre = room.membres.exclude(id=request.user.id).first()
        room_display_name = f"Discuter avec {autre_membre.username}" if autre_membre else "Chat Privé"

    context = {
        'room': room,
        'room_display_name': room_display_name,
        'rooms': rooms,
        'messages': chat_messages,
        'online_users': online_users,
        'private_rooms': private_rooms,
        'tous_utilisateurs': tous_utilisateurs
    }
    return render(request, 'chat/chat_room.html', context)


@login_required
def chat_send_message(request):
    """Envoi d'un message dans un salon ou chat privé."""
    if request.method == 'POST':
        room_slug = request.POST.get('room_slug')
        content = request.POST.get('message', '').strip()

        if room_slug and content:
            room = get_object_or_404(ChatRoom, slug=room_slug)

            if room.type == 'DIRECT' and not room.membres.filter(id=request.user.id).exists():
                return JsonResponse({'success': False, 'error': 'Non autorisé'}, status=403)

            message = ChatMessage.objects.create(
                room=room, auteur=request.user,
                contenu=content, type_message='TEXT'
            )
            update_user_presence(request.user, room)

            return JsonResponse({
                'success': True,
                'message_id': message.id,
                'timestamp': message.get_time_display(),
                'auteur': request.user.username,
                'auteur_id': request.user.id,
            })

    return JsonResponse({'success': False}, status=400)


@login_required
def chat_get_messages(request, room_slug):
    """Récupère l'historique des messages pour le widget et la page salon."""
    room = get_object_or_404(ChatRoom, slug=room_slug)

    if room.type == 'DIRECT' and not room.membres.filter(id=request.user.id).exists():
        return JsonResponse({'error': 'Non autorisé'}, status=403)

    last_id = request.GET.get('last_id', 0)
    try:
        last_id = int(last_id or 0)
    except (TypeError, ValueError):
        last_id = 0

    update_user_presence(request.user, room)

    if last_id <= 0:
        chat_messages = room.messages.select_related('auteur').order_by('-date_envoi')[:80]
        chat_messages = list(chat_messages)[::-1]
    else:
        chat_messages = room.messages.filter(id__gt=last_id).select_related('auteur').order_by('date_envoi')

    data = [{
        'id': msg.id,
        'auteur': msg.auteur.username,
        'auteur_id': msg.auteur.id,
        'contenu': msg.contenu,
        'timestamp': msg.get_time_display(),
        'type': msg.type_message,
    } for msg in chat_messages]

    return JsonResponse({'messages': data})


@login_required
def chat_notifications_api(request):
    """
    API globale des notifications.
    Cible intelligemment les bons utilisateurs selon leurs modules ERP !
    """
    try:
        last_id = int(request.GET.get('last_id', 0) or 0)
    except (TypeError, ValueError):
        last_id = 0

    update_user_presence(request.user, None)

    # Récupérer UNIQUEMENT les salons auxquels l'utilisateur a droit en terme de notification
    notifiable_room_ids = get_user_notifiable_rooms(request.user)
    
    if not notifiable_room_ids:
        return JsonResponse({
            'messages': [],
            'count': 0,
            'latest_id': last_id,
            'max_id': last_id,
        })

    max_id = ChatMessage.objects.filter(room_id__in=notifiable_room_ids).aggregate(m=Max('id'))['m'] or 0

    init = request.GET.get('init', '') == '1'
    if init or last_id <= 0:
        return JsonResponse({
            'messages': [],
            'count': 0,
            'latest_id': max_id,
            'max_id': max_id,
        })

    nouveaux = (
        ChatMessage.objects
        .filter(room_id__in=notifiable_room_ids, id__gt=last_id)
        .exclude(auteur=request.user)
        .select_related('auteur', 'room')
        .order_by('id')[:30]
    )

    data = []
    for msg in nouveaux:
        room_label = msg.room.name if msg.room else 'Chat'
        room_icone = getattr(msg.room, 'icone', '💬') if msg.room else '💬'
        is_direct = False
        if msg.room and getattr(msg.room, 'type', '') == 'DIRECT':
            is_direct = True
            room_label = msg.auteur.username if msg.auteur else 'Message privé'
            room_icone = '👤'

        data.append({
            'id': msg.id,
            'auteur': msg.auteur.username if msg.auteur else '?',
            'auteur_id': msg.auteur_id,
            'contenu': msg.contenu,
            'timestamp': msg.get_time_display() if hasattr(msg, 'get_time_display') else '',
            'type': msg.type_message,
            'room_slug': msg.room.slug if msg.room else '',
            'room_name': room_label,
            'room_icone': room_icone,
            'is_direct': is_direct,
        })

    latest = data[-1]['id'] if data else last_id
    if max_id < latest:
        max_id = latest

    return JsonResponse({
        'messages': data,
        'count': len(data),
        'latest_id': latest,
        'max_id': max_id,
    })


@login_required
def send_system_notification(request):
    if request.method == 'POST' and request.user.is_staff:
        message = request.POST.get('message', '').strip()
        room_slug = request.POST.get('room_slug', 'general')

        if message:
            room = ChatRoom.objects.filter(slug=room_slug).first()
            if room:
                ChatMessage.objects.create(
                    room=room, auteur=request.user,
                    contenu=message, type_message='SYSTEM'
                )
                messages.success(request, "Notification envoyée !")

    return redirect('chat_home')


@login_required
def chat_private_init(request, user_id):
    """Initialise ou récupère un chat privé entre deux utilisateurs."""
    autre_utilisateur = get_object_or_404(User, id=user_id)
    if autre_utilisateur == request.user:
        return redirect('chat_home')

    id_min, id_max = sorted([request.user.id, autre_utilisateur.id])
    room_slug = f"direct-{id_min}-{id_max}"

    room, created = ChatRoom.objects.get_or_create(
        slug=room_slug,
        defaults={
            'name': f"Discussion : {autre_utilisateur.username}",
            'type': 'DIRECT',
            'description': f"Chat privé entre {request.user.username} et {autre_utilisateur.username}",
            'icone': '👤',
        }
    )

    room.membres.add(request.user, autre_utilisateur)
    return redirect('chat_room', room_slug=room_slug)


@login_required
def chat_widget_data(request):
    """API de démarrage du widget flottant (Salons + Privés)."""
    update_user_presence(request.user, None)
    ensure_default_rooms()

    rooms_qs = (
        ChatRoom.objects
        .filter(est_actif=True)
        .exclude(type='DIRECT')
        .annotate(msg_count=Count('messages'))
        .order_by('type', 'name')
    )
    rooms_data = []
    for r in rooms_qs:
        last_msg = r.messages.select_related('auteur').order_by('-date_envoi').first()
        rooms_data.append({
            'slug': r.slug,
            'name': r.name,
            'icone': r.icone or '💬',
            'type': r.type,
            'description': r.description or '',
            'messages_count': r.msg_count,
            'last_message': (last_msg.contenu[:100] if last_msg else ''),
            'last_author': (last_msg.auteur.username if last_msg and last_msg.auteur else ''),
            'last_time': (last_msg.get_time_display() if last_msg else ''),
        })

    private_qs = (
        ChatRoom.objects
        .filter(est_actif=True, type='DIRECT', membres=request.user)
        .prefetch_related('membres')
        .annotate(msg_count=Count('messages'))
        .order_by('-date_creation')
    )
    private_data = []
    for r in private_qs:
        other = r.membres.exclude(id=request.user.id).first()
        last_msg = r.messages.select_related('auteur').order_by('-date_envoi').first()
        is_online = False
        if other:
            try:
                is_online = bool(other.presence.is_online)
            except Exception:
                is_online = False
        private_data.append({
            'slug': r.slug,
            'name': other.username if other else 'Chat Privé',
            'user_id': other.id if other else None,
            'icone': '👤',
            'messages_count': r.msg_count,
            'last_message': (last_msg.contenu[:100] if last_msg else 'Commencer la discussion'),
            'last_author': (last_msg.auteur.username if last_msg and last_msg.auteur else ''),
            'last_time': (last_msg.get_time_display() if last_msg else ''),
            'is_online': is_online,
        })

    users_qs = User.objects.filter(is_active=True).exclude(id=request.user.id).order_by('username')
    presence_map = {
        p.user_id: p.is_online
        for p in UserPresence.objects.filter(user_id__in=users_qs.values_list('id', flat=True))
    }
    users_data = []
    for u in users_qs:
        users_data.append({
            'id': u.id,
            'username': u.username,
            'is_online': bool(presence_map.get(u.id, False)),
            'is_staff': u.is_staff,
        })

    return JsonResponse({
        'rooms': rooms_data,
        'private_rooms': private_data,
        'users': users_data,
        'current_user': request.user.username,
        'current_user_id': request.user.id,
    })


@login_required
def chat_private_api(request, user_id):
    """Initialise un chat privé en JSON pour le widget."""
    autre_utilisateur = get_object_or_404(User, id=user_id, is_active=True)
    if autre_utilisateur.id == request.user.id:
        return JsonResponse({'success': False, 'error': 'Vous ne pouvez pas discuter avec vous-même.'}, status=400)

    id_min, id_max = sorted([request.user.id, autre_utilisateur.id])
    room_slug = f"direct-{id_min}-{id_max}"

    room, created = ChatRoom.objects.get_or_create(
        slug=room_slug,
        defaults={
            'name': f"Discussion : {autre_utilisateur.username}",
            'type': 'DIRECT',
            'description': f"Chat privé entre {request.user.username} et {autre_utilisateur.username}",
            'icone': '👤',
        }
    )
    room.membres.add(request.user, autre_utilisateur)
    update_user_presence(request.user, room)

    return JsonResponse({
        'success': True,
        'created': created,
        'room_slug': room.slug,
        'room_name': autre_utilisateur.username,
        'room_icone': '👤',
        'user_id': autre_utilisateur.id,
    })