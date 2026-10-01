import threading

from django.conf import settings

_user = threading.local()


def get_current_user():
    return getattr(_user, 'value', None)


class CurrentUserMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        impersonated_user_id = request.session.get('_impersonated_user_id')
        if impersonated_user_id and request.user.is_authenticated:
            if not getattr(settings, 'IMPERSONATION_ENABLED', False):
                del request.session['_impersonated_user_id']
                del request.session['_impersonator_id']
            elif request.session.get('_impersonator_id'):
                from django.contrib.auth import get_user_model
                User = get_user_model()
                try:
                    impersonated_user = User.objects.get(pk=impersonated_user_id)
                    request._original_user = request.user
                    request.user = impersonated_user
                except User.DoesNotExist:
                    del request.session['_impersonated_user_id']
                    del request.session['_impersonator_id']

        _user.value = request.user if request.user.is_authenticated else None
        response = self.get_response(request)
        _user.value = None
        return response


class CurrentRolMiddleware:
    """Reinicia el rol de la sessió si l'usuari ja no té aquell grup (p.ex.
    perquè el hub l'hi ha tret). Ha d'anar després de CurrentUserMiddleware
    perquè, durant una impersonació, es comprovi l'usuari impersonat."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        current_rol = request.session.get('current_rol')
        if current_rol and request.user.is_authenticated:
            groups = request.user.groups
            if not groups.filter(name=current_rol).exists():
                first = groups.first()
                request.session['current_rol'] = first.name if first else None
        return self.get_response(request)
