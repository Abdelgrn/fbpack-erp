from django.core.cache import cache
from django.db import transaction
from django.utils import timezone

from ..models import (
    AlerteMaintenance, BonCommande, CommandeClient, DemandeAchat, ERPNotification,
    Machine, Material, OrdreFabrication, StockLot, Tooling,
)

SYNC_CACHE_KEY = 'erp-notifications-sync-v1'


def _upsert(key, module, level, title, message, url, icon, source_model='', source_id=None):
    ERPNotification.objects.update_or_create(
        dedup_key=key,
        defaults={
            'module': module, 'level': level, 'title': title, 'message': message,
            'url': url, 'icon': icon, 'source_model': source_model,
            'source_id': source_id, 'is_active': True,
        },
    )


def _close_stale(prefix, active_keys):
    query = ERPNotification.objects.filter(dedup_key__startswith=prefix, is_active=True)
    if active_keys:
        query = query.exclude(dedup_key__in=active_keys)
    query.update(is_active=False)


def sync_notifications(force=False):
    """Synchronise les événements métier sans doublons, au maximum une fois par minute."""
    if not force and cache.get(SYNC_CACHE_KEY):
        return
    if not cache.add(SYNC_CACHE_KEY, '1', timeout=60) and not force:
        return

    with transaction.atomic():
        # STOCK BAS / RUPTURE
        keys = []
        for item in Material.objects.filter(is_archived=False).order_by('quantity'):
            if item.quantity > item.min_threshold:
                continue
            key = f'stock:material:{item.pk}'
            keys.append(key)
            rupture = item.quantity <= 0
            _upsert(
                key, 'stock', 'CRITICAL' if rupture else 'WARNING',
                ('Rupture — ' if rupture else 'Stock sous le seuil — ') + item.name,
                f'{item.quantity:g} {item.unit} disponibles · seuil {item.min_threshold:g} {item.unit}',
                '/stock/?tab=matieres&low_stock=on', '⛔' if rupture else '⚠️', 'Material', item.pk,
            )
        _close_stale('stock:material:', keys)

        # LOTS QUALITÉ
        keys = []
        for lot in StockLot.objects.filter(statut__in=['BLOQUE', 'QUARANTAINE', 'EN_ATTENTE']).select_related('material'):
            key = f'stock:lot:{lot.pk}:{lot.statut}'
            keys.append(key)
            level = 'CRITICAL' if lot.statut in ['BLOQUE', 'QUARANTAINE'] else 'INFO'
            _upsert(key, 'stock', level, f'Lot {lot.get_statut_display()}',
                    f'{lot.numero_lot} · {lot.material.name}', f'/stock/lot/{lot.pk}/',
                    '🔒' if level == 'CRITICAL' else '🧪', 'StockLot', lot.pk)
        _close_stale('stock:lot:', keys)

        # DEMANDES D'ACHAT À VALIDER
        keys = []
        for da in DemandeAchat.objects.filter(statut='SOUMISE').select_related('material'):
            key = f'stock:da:{da.pk}'
            keys.append(key)
            _upsert(key, 'stock', 'WARNING' if da.urgence != 'CRITIQUE' else 'CRITICAL',
                    f'DA à valider — {da.reference}',
                    f'{da.material.name} · {da.quantite_demandee:g} kg · {da.get_urgence_display()}',
                    '/stock/?tab=achats', '🛒', 'DemandeAchat', da.pk)
        _close_stale('stock:da:', keys)

        # COMMANDES FOURNISSEURS EN RETARD
        today = timezone.localdate()
        keys = []
        for bc in BonCommande.objects.filter(date_livraison_prevue__lt=today).exclude(statut__in=['RECU_TOTAL', 'ANNULE']).select_related('fournisseur'):
            key = f'stock:bc-late:{bc.pk}'
            keys.append(key)
            _upsert(key, 'stock', 'WARNING', f'Livraison fournisseur en retard — {bc.reference}',
                    f'{bc.fournisseur.name} · prévue le {bc.date_livraison_prevue:%d/%m/%Y}',
                    '/stock/?tab=achats', '🚚', 'BonCommande', bc.pk)
        _close_stale('stock:bc-late:', keys)

        # OF EN RETARD
        keys = []
        for of in OrdreFabrication.objects.filter(date_prevue_fin__lt=today).exclude(statut__in=['TERMINE', 'ANNULE']).select_related('client', 'produit'):
            key = f'planning:of-late:{of.pk}'
            keys.append(key)
            _upsert(key, 'planification', 'CRITICAL' if of.priorite == 'URGENTE' else 'WARNING',
                    f'OF en retard — {of.numero_of}',
                    f'{of.client.name} · {of.produit.name} · prévu le {of.date_prevue_fin:%d/%m/%Y}',
                    f'/of/{of.pk}/', '⏱️', 'OrdreFabrication', of.pk)
        _close_stale('planning:of-late:', keys)

        # COMMANDES CLIENT URGENTES / EN RETARD
        keys = []
        command_qs = CommandeClient.objects.filter(date_livraison_prevue__lt=today).exclude(statut__in=['LIVREE', 'ANNULEE']).select_related('client')
        for cmd in command_qs:
            key = f'crm:order-late:{cmd.pk}'
            keys.append(key)
            _upsert(key, 'crm', 'CRITICAL' if cmd.priorite == 'URGENTE' else 'WARNING',
                    f'Commande en retard — {cmd.reference}',
                    f'{cmd.client.name} · prévue le {cmd.date_livraison_prevue:%d/%m/%Y}',
                    f'/crm/commande/{cmd.pk}/', '📦', 'CommandeClient', cmd.pk)
        _close_stale('crm:order-late:', keys)

        # MACHINES EN PANNE
        keys = []
        for machine in Machine.objects.filter(est_active=True, status='PANNE'):
            key = f'maintenance:machine:{machine.pk}'
            keys.append(key)
            _upsert(key, 'maintenance', 'CRITICAL', f'Machine en panne — {machine.name}',
                    f'{machine.code_machine} · intervention requise',
                    f'/maintenance/machine/{machine.pk}/', '🛑', 'Machine', machine.pk)
        _close_stale('maintenance:machine:', keys)

        # ALERTES MAINTENANCE EXISTANTES
        keys = []
        for alert in AlerteMaintenance.objects.filter(est_traitee=False).select_related('machine'):
            key = f'maintenance:alert:{alert.pk}'
            keys.append(key)
            _upsert(key, 'maintenance', alert.niveau, alert.titre, alert.message,
                    '/maintenance/alertes/', '🔧', 'AlerteMaintenance', alert.pk)
        _close_stale('maintenance:alert:', keys)

        # OUTILLAGES USÉS
        keys = []
        for tool in Tooling.objects.select_related('product__client').all():
            wear = tool.wear_percent
            if wear < 75:
                continue
            key = f'prepress:tool:{tool.pk}'
            keys.append(key)
            _upsert(key, 'prepress', 'CRITICAL' if wear >= 90 else 'WARNING',
                    f'Outillage usé à {wear}% — {tool.serial_number}',
                    f'{tool.product.client.name} · {tool.get_tool_type_display()}',
                    '/prepress/outillages/', '🎨', 'Tooling', tool.pk)
        _close_stale('prepress:tool:', keys)
