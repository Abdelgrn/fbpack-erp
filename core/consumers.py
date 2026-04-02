import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone


class ChatConsumer(AsyncWebsocketConsumer):
    
    async def connect(self):
        self.room_slug = self.scope['url_route']['kwargs']['room_slug']
        self.room_group_name = f'chat_{self.room_slug}'
        self.user = self.scope['user']
        
        if not self.user.is_authenticated:
            await self.close()
            return
        
        # Rejoindre le groupe du salon
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        await self.accept()
        
        # Mettre à jour la présence
        await self.update_user_presence(True)
        
        # Notifier les autres utilisateurs
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'user_join',
                'username': self.user.username,
                'user_id': self.user.id,
            }
        )
    
    async def disconnect(self, close_code):
        # Mettre à jour la présence
        await self.update_user_presence(False)
        
        # Notifier les autres utilisateurs
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'user_leave',
                'username': self.user.username,
                'user_id': self.user.id,
            }
        )
        
        # Quitter le groupe
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
    
    async def receive(self, text_data):
        data = json.loads(text_data)
        message_type = data.get('type', 'message')
        
        if message_type == 'message':
            message = data['message']
            
            # Sauvegarder le message en base
            saved_message = await self.save_message(message)
            
            # Envoyer à tous les utilisateurs du groupe
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'chat_message',
                    'message': message,
                    'username': self.user.username,
                    'user_id': self.user.id,
                    'timestamp': saved_message['timestamp'],
                    'message_id': saved_message['id'],
                }
            )
        
        elif message_type == 'typing':
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'user_typing',
                    'username': self.user.username,
                    'user_id': self.user.id,
                    'is_typing': data.get('is_typing', False),
                }
            )
    
    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            'type': 'message',
            'message': event['message'],
            'username': event['username'],
            'user_id': event['user_id'],
            'timestamp': event['timestamp'],
            'message_id': event['message_id'],
        }))
    
    async def user_join(self, event):
        await self.send(text_data=json.dumps({
            'type': 'user_join',
            'username': event['username'],
            'user_id': event['user_id'],
        }))
    
    async def user_leave(self, event):
        await self.send(text_data=json.dumps({
            'type': 'user_leave',
            'username': event['username'],
            'user_id': event['user_id'],
        }))
    
    async def user_typing(self, event):
        if event['user_id'] != self.user.id:
            await self.send(text_data=json.dumps({
                'type': 'typing',
                'username': event['username'],
                'is_typing': event['is_typing'],
            }))
    
    async def system_message(self, event):
        await self.send(text_data=json.dumps({
            'type': 'system',
            'message': event['message'],
        }))
    
    @database_sync_to_async
    def save_message(self, content):
        from .models import ChatRoom, ChatMessage
        room = ChatRoom.objects.get(slug=self.room_slug)
        message = ChatMessage.objects.create(
            room=room,
            auteur=self.user,
            contenu=content,
            type_message='TEXT'
        )
        return {
            'id': message.id,
            'timestamp': message.date_envoi.strftime('%H:%M'),
        }
    
    @database_sync_to_async
    def update_user_presence(self, is_online):
        from .models import ChatRoom, UserPresence
        presence, created = UserPresence.objects.get_or_create(user=self.user)
        presence.is_online = is_online
        if is_online:
            try:
                room = ChatRoom.objects.get(slug=self.room_slug)
                presence.current_room = room
            except ChatRoom.DoesNotExist:
                pass
        else:
            presence.current_room = None
        presence.save()