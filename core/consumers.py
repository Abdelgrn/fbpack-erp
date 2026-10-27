import json
import logging
import re
import time
from collections import deque
from urllib.parse import urlparse

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.conf import settings
from django.http.request import validate_host
from django.utils import timezone

logger = logging.getLogger('security')

# Les noms de groupes Channels n'acceptent que ASCII alphanumérique, - _ et .
SLUG_RE = re.compile(r'^[-a-zA-Z0-9_]{1,80}$')
CONTROL_CHARS_RE = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]')

MAX_FRAME_CHARS = 5000        # taille maximale d'une trame WebSocket reçue
MAX_MESSAGE_CHARS = 2000      # taille maximale d'un message de chat
RATE_WINDOW_SECONDS = 10      # fenêtre de limitation de débit
RATE_MAX_EVENTS = 20          # événements max par fenêtre et par connexion
REVALIDATE_SECONDS = 60       # revérification compte actif + session


class ChatConsumer(AsyncWebsocketConsumer):
    """Chat ERP : tous les utilisateurs connectés peuvent rejoindre tous les salons."""

    # ------------------------------------------------------------------ #
    # Sécurité
    # ------------------------------------------------------------------ #
    def _origin_allowed(self):
        """Empêche le détournement de WebSocket depuis un site tiers (CSWSH)."""
        if settings.DEBUG:
            # Développement local : accès possible par IP du réseau ou nom du PC.
            return True
        origin = None
        for name, value in self.scope.get('headers', []):
            if name == b'origin':
                origin = value.decode('latin-1')
                break
        if not origin:
            # Client non-navigateur : pas de cookie de session détournable.
            return True
        host = urlparse(origin).hostname
        if not host:
            return False
        allowed = list(settings.ALLOWED_HOSTS)
        if not allowed and settings.DEBUG:
            allowed = ['localhost', '127.0.0.1', '[::1]']
        return validate_host(host, allowed)

    def _rate_limited(self):
        now = time.monotonic()
        while self.recent_events and now - self.recent_events[0] > RATE_WINDOW_SECONDS:
            self.recent_events.popleft()
        if len(self.recent_events) >= RATE_MAX_EVENTS:
            return True
        self.recent_events.append(now)
        return False

    async def _still_authorized(self):
        """Revérifie périodiquement que le compte et la session sont toujours valides."""
        now = time.monotonic()
        if now - self.last_validation < REVALIDATE_SECONDS:
            return True
        self.last_validation = now
        return await self.check_user_and_session()

    # ------------------------------------------------------------------ #
    # Cycle de vie
    # ------------------------------------------------------------------ #
    async def connect(self):
        self.joined = False
        self.recent_events = deque()
        self.last_validation = time.monotonic()
        self.user = self.scope.get('user')
        self.room_slug = ''
        self.room_group_name = ''

        if not self._origin_allowed():
            logger.warning('ws_origin_refused')
            await self.close(code=4403)
            return

        if not (self.user and self.user.is_authenticated and self.user.is_active):
            await self.close(code=4401)
            return

        slug = (self.scope.get('url_route', {}).get('kwargs', {}) or {}).get('room_slug', '')
        if not isinstance(slug, str) or not SLUG_RE.match(slug):
            await self.close(code=4400)
            return

        self.room_slug = slug
        self.room_group_name = f'chat_{slug}'

        if not await self.room_accessible():
            await self.close(code=4404)
            return

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        self.joined = True
        await self.accept()

        await self.update_user_presence(True)
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'user_join',
                'username': self.user.username,
                'user_id': self.user.id,
            },
        )

    async def disconnect(self, close_code):
        # Une connexion refusée dans connect() ne doit rien déclencher ici.
        if not getattr(self, 'joined', False):
            return
        self.joined = False
        try:
            await self.update_user_presence(False)
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'user_leave',
                    'username': self.user.username,
                    'user_id': self.user.id,
                },
            )
        except Exception as exc:
            logger.error('ws_disconnect_failed error=%s', type(exc).__name__)
        finally:
            await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        if not text_data:
            return
        if len(text_data) > MAX_FRAME_CHARS:
            await self.close(code=4413)
            return

        if not await self._still_authorized():
            await self.close(code=4401)
            return

        try:
            data = json.loads(text_data)
        except (TypeError, ValueError):
            return
        if not isinstance(data, dict):
            return

        if self._rate_limited():
            await self.send(text_data=json.dumps({
                'type': 'system',
                'message': 'Trop de messages envoyés. Ralentissez.',
            }))
            return

        message_type = data.get('type', 'message')

        if message_type == 'message':
            raw = data.get('message', '')
            if not isinstance(raw, str):
                return
            message = CONTROL_CHARS_RE.sub('', raw).strip()
            if not message or len(message) > MAX_MESSAGE_CHARS:
                return

            saved_message = await self.save_message(message)
            if not saved_message:
                await self.close(code=4404)
                return

            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'chat_message',
                    'message': message,
                    'username': self.user.username,
                    'user_id': self.user.id,
                    'timestamp': saved_message['timestamp'],
                    'message_id': saved_message['id'],
                },
            )

        elif message_type == 'typing':
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'user_typing',
                    'username': self.user.username,
                    'user_id': self.user.id,
                    'is_typing': data.get('is_typing') is True,
                },
            )

    # ------------------------------------------------------------------ #
    # Événements envoyés au client
    # ------------------------------------------------------------------ #
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

    # ------------------------------------------------------------------ #
    # Accès base de données
    # ------------------------------------------------------------------ #
    @database_sync_to_async
    def room_accessible(self):
        """Salon actif et existant. Les chats privés (DIRECT) restent réservés à leurs 2 membres."""
        from .models import ChatRoom
        room = ChatRoom.objects.filter(slug=self.room_slug, est_actif=True).first()
        if room is None:
            return False
        if room.type == 'DIRECT':
            return room.membres.filter(pk=self.user.pk).exists()
        return True

    @database_sync_to_async
    def check_user_and_session(self):
        from django.contrib.auth import get_user_model
        from django.contrib.sessions.models import Session

        User = get_user_model()
        if not User.objects.filter(pk=self.user.pk, is_active=True).exists():
            return False

        session = self.scope.get('session')
        session_key = getattr(session, 'session_key', None)
        if session_key:
            return Session.objects.filter(
                session_key=session_key,
                expire_date__gt=timezone.now(),
            ).exists()
        return True

    @database_sync_to_async
    def save_message(self, content):
        from .models import ChatRoom, ChatMessage
        try:
            room = ChatRoom.objects.get(slug=self.room_slug, est_actif=True)
        except ChatRoom.DoesNotExist:
            return None
        message = ChatMessage.objects.create(
            room=room,
            auteur=self.user,
            contenu=content,
            type_message='TEXT',
        )
        sent_at = message.date_envoi
        try:
            sent_at = timezone.localtime(sent_at)
        except ValueError:
            pass
        return {
            'id': message.id,
            'timestamp': sent_at.strftime('%H:%M'),
        }

    @database_sync_to_async
    def update_user_presence(self, is_online):
        from .models import ChatRoom, UserPresence
        presence, _created = UserPresence.objects.get_or_create(user=self.user)
        presence.is_online = is_online
        if is_online:
            try:
                presence.current_room = ChatRoom.objects.get(slug=self.room_slug)
            except ChatRoom.DoesNotExist:
                pass
        else:
            presence.current_room = None
        presence.save()
