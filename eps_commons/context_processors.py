from django.conf import settings


def basic_urls(request):
    return {
        'LOGIN_URL': settings.LOGIN_URL,
        'LOGOUT_URL': settings.LOGOUT_URL,
    }


def current_rol(request):
    if request.user.is_authenticated:
        if 'current_rol' not in request.session:
            grups = request.user.groups.all()
            if grups.exists():
                request.session['current_rol'] = grups.first().name
    return {
        'current_rol': request.session.get('current_rol')
    }


def site_settings(request):
    return {
        'SITE_TITLE': getattr(settings, 'SITE_TITLE', ''),
    }


def impersonation_context(request):
    from .views import _can_impersonate
    if not getattr(settings, 'IMPERSONATION_ENABLED', False):
        return {'is_impersonating': False, 'impersonator': None, 'can_impersonate': False}

    can_impersonate = request.user.is_authenticated and _can_impersonate(request.user)

    impersonator_id = request.session.get('_impersonator_id')
    if impersonator_id and request.user.is_authenticated:
        from django.contrib.auth import get_user_model
        User = get_user_model()
        try:
            impersonator = User.objects.get(pk=impersonator_id)
            return {'is_impersonating': True, 'impersonator': impersonator, 'can_impersonate': can_impersonate}
        except User.DoesNotExist:
            pass

    return {'is_impersonating': False, 'impersonator': None, 'can_impersonate': can_impersonate}
