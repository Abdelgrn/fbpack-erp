from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from ..models import ERPNotification, ERPNotificationState
from ..models.permissions import user_has_module_access
from ..services.notifications import sync_notifications


MODULE_PERMISSION_MAP = {
    'stock': 'stock',
    'planning': 'planning',
    'planification': 'planification',
    'production': 'production',
    'prepress': 'prepress',
    'maintenance': 'maintenance',
    'crm': 'crm',
    'dashboard': 'dashboard',
}


def _allowed_modules(user):
    if user.is_superuser:
        return list(MODULE_PERMISSION_MAP.keys())
    return [module for module, permission in MODULE_PERMISSION_MAP.items()
            if user_has_module_access(user, permission)]


def _visible_queryset(user, include_processed=False):
    allowed = _allowed_modules(user)
    query = ERPNotification.objects.filter(is_active=True, module__in=allowed)
    if not include_processed:
        query = query.exclude(user_states__user=user, user_states__is_processed=True)
    return query.distinct()


def _serialize(notification, state=None):
    return {
        'id': notification.pk,
        'module': notification.module,
        'module_label': notification.get_module_display(),
        'level': notification.level,
        'title': notification.title,
        'message': notification.message,
        'url': notification.url,
        'icon': notification.icon,
        'is_read': bool(state and state.is_read),
        'is_processed': bool(state and state.is_processed),
        'date': timezone.localtime(notification.last_seen_at).strftime('%d/%m/%Y %H:%M'),
    }


@login_required
def notification_center(request):
    sync_notifications()
    selected_module = request.GET.get('module', 'ALL')
    selected_level = request.GET.get('level', 'ALL')
    show_processed = request.GET.get('processed') == '1'

    notifications = _visible_queryset(request.user, include_processed=show_processed)
    if selected_module != 'ALL':
        notifications = notifications.filter(module=selected_module)
    if selected_level != 'ALL':
        notifications = notifications.filter(level=selected_level)
    notifications = notifications.order_by('-last_seen_at')[:300]

    states = {state.notification_id: state for state in ERPNotificationState.objects.filter(
        user=request.user, notification_id__in=[item.pk for item in notifications]
    )}
    rows = []
    for item in notifications:
        item.current_state = states.get(item.pk)
        rows.append(item)

    return render(request, 'notifications/notification_center.html', {
        'notifications': rows,
        'selected_module': selected_module,
        'selected_level': selected_level,
        'show_processed': show_processed,
        'module_choices': ERPNotification.MODULE_CHOICES,
        'level_choices': ERPNotification.LEVEL_CHOICES,
    })


@login_required
@require_GET
def notification_api_list(request):
    sync_notifications()
    notifications = list(_visible_queryset(request.user).order_by('-last_seen_at')[:20])
    states = {state.notification_id: state for state in ERPNotificationState.objects.filter(
        user=request.user, notification_id__in=[item.pk for item in notifications]
    )}
    data = [_serialize(item, states.get(item.pk)) for item in notifications]
    visible = _visible_queryset(request.user)
    unread = visible.exclude(
        user_states__user=request.user,
        user_states__is_read=True,
    ).count()
    critical = visible.filter(level='CRITICAL').count()
    return JsonResponse({'ok': True, 'notifications': data, 'unread_count': unread, 'critical_count': critical})


@login_required
@require_POST
def notification_mark_read(request, notification_id):
    notification = get_object_or_404(_visible_queryset(request.user, include_processed=True), pk=notification_id)
    state, _ = ERPNotificationState.objects.get_or_create(user=request.user, notification=notification)
    if not state.is_read:
        state.is_read = True
        state.read_at = timezone.now()
        state.save(update_fields=['is_read', 'read_at'])
    return JsonResponse({'ok': True})


@login_required
@require_POST
def notification_mark_all_read(request):
    notifications = list(_visible_queryset(request.user).only('id'))
    existing = {state.notification_id: state for state in ERPNotificationState.objects.filter(
        user=request.user, notification_id__in=[item.pk for item in notifications]
    )}
    now = timezone.now()
    create_rows = []
    update_rows = []
    for notification in notifications:
        state = existing.get(notification.pk)
        if state:
            if not state.is_read:
                state.is_read = True
                state.read_at = now
                update_rows.append(state)
        else:
            create_rows.append(ERPNotificationState(
                user=request.user, notification=notification, is_read=True, read_at=now
            ))
    if create_rows:
        ERPNotificationState.objects.bulk_create(create_rows, ignore_conflicts=True)
    if update_rows:
        ERPNotificationState.objects.bulk_update(update_rows, ['is_read', 'read_at'])
    return JsonResponse({'ok': True})


@login_required
@require_POST
def notification_toggle_processed(request, notification_id):
    notification = get_object_or_404(_visible_queryset(request.user, include_processed=True), pk=notification_id)
    state, _ = ERPNotificationState.objects.get_or_create(user=request.user, notification=notification)
    state.is_processed = not state.is_processed
    state.processed_at = timezone.now() if state.is_processed else None
    state.is_read = True
    state.read_at = state.read_at or timezone.now()
    state.save(update_fields=['is_processed', 'processed_at', 'is_read', 'read_at'])
    return JsonResponse({'ok': True, 'is_processed': state.is_processed})
