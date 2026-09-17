from django.db import models
from django.contrib.auth.models import User

class ChatRoom(models.Model):
    TYPE_CHOICES = [
        ('GENERAL', 'Général'), ('PRODUCTION', 'Production'),
        ('COMMERCIAL', 'Commercial'), ('TECHNIQUE', 'Technique'),
        ('URGENCE', 'Urgences'),
    ]

    name = models.CharField("Nom du salon", max_length=100)
    slug = models.SlugField("Slug", unique=True)
    type = models.CharField("Type", max_length=20, choices=TYPE_CHOICES, default='GENERAL')
    description = models.TextField("Description", blank=True)
    icone = models.CharField("Icône", max_length=10, default='💬')
    est_actif = models.BooleanField("Actif", default=True)
    date_creation = models.DateTimeField("Créé le", auto_now_add=True)
    membres = models.ManyToManyField(User, related_name='chat_rooms', blank=True, verbose_name="Membres")

    class Meta:
        app_label = 'core'
        verbose_name = "Salon de chat"
        verbose_name_plural = "Salons de chat"


class ChatMessage(models.Model):
    TYPE_CHOICES = [
        ('TEXT', 'Texte'), ('SYSTEM', 'Système'),
        ('ALERT', 'Alerte'), ('FILE', 'Fichier'),
    ]

    room = models.ForeignKey(ChatRoom, on_delete=models.CASCADE, related_name='messages', verbose_name="Salon")
    auteur = models.ForeignKey(User, on_delete=models.CASCADE, related_name='chat_messages', verbose_name="Auteur")
    contenu = models.TextField("Message")
    type_message = models.CharField("Type", max_length=10, choices=TYPE_CHOICES, default='TEXT')
    date_envoi = models.DateTimeField("Envoyé le", auto_now_add=True)
    lu_par = models.ManyToManyField(User, related_name='messages_lus', blank=True, verbose_name="Lu par")
    fichier = models.FileField("Fichier joint", upload_to='chat_files/', blank=True, null=True)
    of_lie = models.ForeignKey('core.OrdreFabrication', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="OF lié")

    class Meta:
        app_label = 'core'
        verbose_name = "Message"
        verbose_name_plural = "Messages"


class UserPresence(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='presence', verbose_name="Utilisateur")
    is_online = models.BooleanField("En ligne", default=False)
    last_seen = models.DateTimeField("Dernière activité", auto_now=True)
    current_room = models.ForeignKey(ChatRoom, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Salon actuel")

    class Meta:
        app_label = 'core'
        verbose_name = "Présence utilisateur"
        verbose_name_plural = "Présences utilisateurs"