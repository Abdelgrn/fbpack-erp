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
    for r in default_rooms:
        ChatRoom.objects.get_or_create(slug=r['slug'], defaults=r)
        
    return render(request, 'chat/chat_home.html', {
        'rooms': ChatRoom.objects.filter(est_actif=True).order_by('type', 'name'),
        'online_users': UserPresence.objects.filter(is_online=True).select_related('user')
    })

@login_required
def chat_room(request, room_slug):
    room = get_object_or_404(ChatRoom, slug=room_slug, est_actif=True)
    room.membres.add(request.user)
    chat_messages = list(room.messages.select_related('auteur').order_by('-date_envoi')[:50])[::-1]
    
    return render(request, 'chat/chat_room.html', {
        'room': room, 'rooms': ChatRoom.objects.filter(est_actif=True).order_by('type', 'name'),
        'messages': chat_messages, 'online_users': UserPresence.objects.filter(is_online=True, current_room=room).select_related('user'),
    })

@login_required
def chat_send_message(request):
    if request.method == 'POST':
        room_slug, content = request.POST.get('room_slug'), request.POST.get('message', '').strip()
        if room_slug and content:
            msg = ChatMessage.objects.create(room=get_object_or_404(ChatRoom, slug=room_slug), auteur=request.user, contenu=content, type_message='TEXT')
            return JsonResponse({'success': True, 'message_id': msg.id, 'timestamp': msg.get_time_display()})
    return JsonResponse({'success': False}, status=400)

@login_required
def chat_get_messages(request, room_slug):
    room = get_object_or_404(ChatRoom, slug=room_slug)
    last_id = request.GET.get('last_id', 0)
    messages = room.messages.filter(id__gt=last_id).select_related('auteur').order_by('date_envoi')
    return JsonResponse({
        'messages': [{
            'id': m.id, 'auteur': m.auteur.username, 'auteur_id': m.auteur.id,
            'contenu': m.contenu, 'timestamp': m.get_time_display(), 'type': m.type_message
        } for m in messages]
    })

@login_required
def send_system_notification(request):
    if request.method == 'POST' and request.user.is_staff:
        msg, room_slug = request.POST.get('message', '').strip(), request.POST.get('room_slug', 'general')
        if msg:
            room = ChatRoom.objects.filter(slug=room_slug).first()
            if room:
                ChatMessage.objects.create(room=room, auteur=request.user, contenu=msg, type_message='SYSTEM')
                messages.success(request, "Notification envoyée !")
    return redirect('chat_home')