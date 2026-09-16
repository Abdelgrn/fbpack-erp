from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.contrib import messages

from ..models import ChatRoom, ChatMessage, UserPresence

@login_required
def chat_home(request):
    rooms = ChatRoom.objects.filter(est_actif=True).order_by('type', 'name')

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

    rooms = ChatRoom.objects.filter(est_actif=True).order_by('type', 'name')
    online_users = UserPresence.objects.filter(is_online=True).select_related('user')

    context = {'rooms': rooms, 'online_users': online_users}
    return render(request, 'chat/chat_home.html', context)


@login_required
def chat_room(request, room_slug):
    room = get_object_or_404(ChatRoom, slug=room_slug, est_actif=True)
    room.membres.add(request.user)

    chat_messages = room.messages.select_related('auteur').order_by('-date_envoi')[:50]
    chat_messages = list(chat_messages)[::-1]

    rooms = ChatRoom.objects.filter(est_actif=True).order_by('type', 'name')
    online_users = UserPresence.objects.filter(
        is_online=True, current_room=room
    ).select_related('user')

    context = {
        'room': room, 'rooms': rooms,
        'messages': chat_messages,
        'online_users': online_users,
    }
    return render(request, 'chat/chat_room.html', context)


@login_required
def chat_send_message(request):
    if request.method == 'POST':
        room_slug = request.POST.get('room_slug')
        content = request.POST.get('message', '').strip()

        if room_slug and content:
            room = get_object_or_404(ChatRoom, slug=room_slug)
            message = ChatMessage.objects.create(
                room=room, auteur=request.user,
                contenu=content, type_message='TEXT'
            )
            return JsonResponse({
                'success': True,
                'message_id': message.id,
                'timestamp': message.get_time_display(),
            })

    return JsonResponse({'success': False}, status=400)


@login_required
def chat_get_messages(request, room_slug):
    room = get_object_or_404(ChatRoom, slug=room_slug)
    last_id = request.GET.get('last_id', 0)

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