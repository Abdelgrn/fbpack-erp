from django.conf import settings
from django.db import models


class ERPNotification(models.Model):
    LEVEL_CHOICES = [
        ('INFO', 'Information'),
        ('WARNING', 'Attention'),
        ('CRITICAL', 'Critique'),
        ('SUCCESS', 'Succès'),
    ]
    MODULE_CHOICES = [
        ('stock', 'Stocks & Achats'),
        ('planning', 'Planning'),
        ('planification', 'Planification'),
        ('production', 'Production'),
        ('prepress', 'Prépresse'),
        ('maintenance', 'Maintenance'),
        ('crm', 'CRM'),
        ('dashboard', 'Général'),
    ]

    dedup_key = models.CharField('Clé anti-doublon', max_length=190, unique=True, db_index=True)
    module = models.CharField(max_length=20, choices=MODULE_CHOICES, db_index=True)
    level = models.CharField(max_length=10, choices=LEVEL_CHOICES, default='INFO', db_index=True)
    title = models.CharField(max_length=200)
    message = models.TextField(blank=True)
    url = models.CharField(max_length=500, blank=True)
    icon = models.CharField(max_length=10, default='🔔')
    source_model = models.CharField(max_length=100, blank=True)
    source_id = models.PositiveBigIntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    first_seen_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'core'
        ordering = ['-level', '-last_seen_at']
        indexes = [
            models.Index(fields=['is_active', 'module', 'level'], name='notif_active_module_idx'),
        ]

    def __str__(self):
        return f'{self.icon} {self.title}'


class ERPNotificationState(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='erp_notification_states')
    notification = models.ForeignKey(ERPNotification, on_delete=models.CASCADE, related_name='user_states')
    is_read = models.BooleanField(default=False, db_index=True)
    read_at = models.DateTimeField(null=True, blank=True)
    is_processed = models.BooleanField(default=False, db_index=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = 'core'
        constraints = [
            models.UniqueConstraint(fields=['user', 'notification'], name='unique_notification_state_user'),
        ]
        indexes = [
            models.Index(fields=['user', 'is_read', 'is_processed'], name='notif_state_user_idx'),
        ]

    def __str__(self):
        return f'{self.user} — {self.notification}'
