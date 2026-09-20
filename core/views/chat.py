from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.contrib import messages
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta

from ..models import ChatRoom, ChatMessage, UserPresence

def update_user_presence(user, current_room=None):
    # Marquer comme hors ligne les utilisateurs inactifs depuis plus de 2 minutes
    limite_activite = timezone.now() - timedelta(minutes=2)
    UserPresence.objects.filter(last_seen__lt=limite_activite, is_online=True).update(is_online=False)
    
    # Mettre à jour l'utilisateur actuel
    presence, created = UserPresence.objects.get_or_create(user=user)
    presence.is_online = True
    presence.current_room = current_room
    presence.save()

@login_required
def chat_home(request):
    update_user_presence(request.user, None)
    
    # Récupérer les salons publics uniquement
    rooms = ChatRoom.objects.filter(est_actif=True).exclude(type='DIRECT').order_by('type', 'name')

    default_rooms = [
        {'name': 'Général', 'slug': 'general', 'type': 'GENERAL', 'icone': '💬'},
        {'name': 'Production', 'slug': 'production', 'type': 'PRODUCTION', 'icone': '🏭'},
        {'name': 'Commercial', 'slug': 'commercial', 'type': 'COMMERCIAL', 'icone': '💼'},
        {'name': 'Technique', 'slug': 'technique', 'type': 'TECHNIQUE', 'icone': '🔧'},
        {'name': 'Urgences', 'slug': 'urgences', 'type': 'URGENCE', 'icone': '🚨'},
    ]

    for room_data in default_rooms:
        ChatRoom.objects.get_or_create(
            slug=room_data['slug'],
            defaults=room_data
        )

    rooms = ChatRoom.objects.filter(est_actif=True).exclude(type='DIRECT').order_by('type', 'name')
    online_users = UserPresence.objects.filter(is_online=True).select_related('user')
    
    # Récupérer toutes les discussions privées actives de l'utilisateur
    private_rooms = ChatRoom.objects.filter(
        est_actif=True, 
        type='DIRECT', 
        membres=request.user
    ).order_by('-date_creation')
    
    # Liste de tous les autres utilisateurs pour initier un chat privé
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
    
    # Discussions privées de l'utilisateur
    private_rooms = ChatRoom.objects.filter(
        est_actif=True, 
        type='DIRECT', 
        membres=request.user
    ).order_by('-date_creation')
    
    tous_utilisateurs = User.objects.filter(is_active=True).exclude(id=request.user.id).order_by('username')

    # Déterminer le titre du chat privé
    if room.type == 'DIRECT':
        autre_membre = room.membres.exclude(id=request.user.id).first()
        room.name = f"Discuter avec {autre_membre.username}" if autre_membre else "Chat Privé"

    context = {
        'room': room, 
        'rooms': rooms,
        'messages': chat_messages,
        'online_users': online_users,
        'private_rooms': private_rooms,
        'tous_utilisateurs': tous_utilisateurs
    }
    return render(request, 'chat/chat_room.html', context)


@login_required
def chat_send_message(request):
    if request.method == 'POST':
        room_slug = request.POST.get('room_slug')
        content = request.POST.get('message', '').strip()

        if room_slug and content:
            room = get_object_or_404(ChatRoom, slug=room_slug)
            
            # Vérification de sécurité pour les chats privés
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
            })

    return JsonResponse({'success': False}, status=400)


@login_required
def chat_get_messages(request, room_slug):
    room = get_object_or_404(ChatRoom, slug=room_slug)
    
    # Sécurité pour les chats privés
    if room.type == 'DIRECT' and not room.membres.filter(id=request.user.id).exists():
        return JsonResponse({'error': 'Non autorisé'}, status=403)

    last_id = request.GET.get('last_id', 0)
    update_user_presence(request.user, room)

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
    """Initialise ou récupère un chat privé entre l'utilisateur connecté et un autre utilisateur"""
    autre_utilisateur = get_object_or_404(User, id=user_id)
    if autre_utilisateur == request.user:
        return redirect('chat_home')

    # Générer un slug unique et prévisible basé sur les IDs triés des deux utilisateurs
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