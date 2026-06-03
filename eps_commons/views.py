import base64
import hashlib
import os
import tomllib

import requests as http_requests
from django.conf import settings
from django.contrib.auth import get_user_model, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import Group
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from requests.auth import HTTPBasicAuth
from requests_oauthlib import OAuth2Session


def swap_rol(request, group_name):
    if request.user.is_authenticated and request.user.groups.filter(name=group_name).exists():
        request.session['current_rol'] = group_name
    next_url = request.GET.get('next') or request.META.get('HTTP_REFERER', '/')
    return redirect(next_url)


def _can_impersonate(user):
    if not user.is_superuser:
        return False
    impersonation_group = getattr(settings, 'IMPERSONATION_GROUP', None)
    if impersonation_group:
        return user.groups.filter(name=impersonation_group).exists()
    return True


@user_passes_test(_can_impersonate)
def impersonate_list(request):
    if not getattr(settings, 'IMPERSONATION_ENABLED', False):
        raise Http404
    User = get_user_model()
    users = User.objects.order_by('last_name', 'first_name', 'username')
    return render(request, 'eps_commons/impersonate_list.html', {'users': users})


@user_passes_test(_can_impersonate)
def impersonate_user(request, username):
    if not getattr(settings, 'IMPERSONATION_ENABLED', False):
        raise Http404
    from eps_commons.signals import user_impersonated
    User = get_user_model()
    target_user = get_object_or_404(User, username=username)
    request.session['_impersonator_id'] = request.user.pk
    request.session['_impersonated_user_id'] = target_user.pk
    grups = target_user.groups.all()
    request.session['current_rol'] = grups.first().name if grups.exists() else None
    user_impersonated.send(sender=request.user.__class__, request=request, user=target_user)
    success_url = getattr(settings, 'IMPERSONATION_SUCCESS_URL', settings.LOGIN_REDIRECT_URL)
    return redirect(success_url)


@login_required
def stop_impersonation(request):
    if '_impersonator_id' in request.session:
        impersonator_id = request.session['_impersonator_id']
        del request.session['_impersonated_user_id']
        del request.session['_impersonator_id']
        User = get_user_model()
        try:
            impersonator = User.objects.get(pk=impersonator_id)
            grups = impersonator.groups.all()
            request.session['current_rol'] = grups.first().name if grups.exists() else None
        except User.DoesNotExist:
            request.session.pop('current_rol', None)
    success_url = getattr(settings, 'IMPERSONATION_SUCCESS_URL', settings.LOGIN_REDIRECT_URL)
    return redirect(success_url)


# --- OAuth2 ---

def _oauth_userinfo_url():
    return getattr(settings, 'OAUTH2_USERINFO_URL', 'https://hub.epsapps.uib.es/api/userinfo/')


def _generate_code_verifier():
    return base64.urlsafe_b64encode(os.urandom(40)).rstrip(b'=').decode('utf-8')


def _generate_code_challenge(verifier):
    digest = hashlib.sha256(verifier.encode('utf-8')).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b'=').decode('utf-8')


def oauth_login(request):
    next_url = request.GET.get('next') or request.META.get('HTTP_REFERER', '/')
    request.session['oauth_next_url'] = next_url

    verifier = _generate_code_verifier()
    challenge = _generate_code_challenge(verifier)
    request.session['oauth_code_verifier'] = verifier

    oauth = OAuth2Session(
        settings.OAUTH2_CLIENT_ID,
        redirect_uri=settings.OAUTH2_REDIRECT_URI,
    )
    authorization_url, state = oauth.authorization_url(
        settings.OAUTH2_AUTHORIZATION_URL,
        code_challenge=challenge,
        code_challenge_method='S256',
    )
    request.session['oauth_state'] = state
    return redirect(authorization_url)


def oauth_callback(request):
    verifier = request.session.get('oauth_code_verifier')
    state = request.session.get('oauth_state')

    oauth = OAuth2Session(
        settings.OAUTH2_CLIENT_ID,
        redirect_uri=settings.OAUTH2_REDIRECT_URI,
        state=state,
    )
    token = oauth.fetch_token(
        settings.OAUTH2_TOKEN_URL,
        authorization_response=request.build_absolute_uri(),
        code_verifier=verifier,
        auth=HTTPBasicAuth(settings.OAUTH2_CLIENT_ID, settings.OAUTH2_CLIENT_SECRET),
    )

    userinfo_response = oauth.get(_oauth_userinfo_url())
    if userinfo_response.status_code == 200:
        userinfo = userinfo_response.json()
        group_names = userinfo.get('groups', [])
        allowed_groups = getattr(settings, 'OAUTH2_ALLOWED_GROUPS', None)
        if allowed_groups and not any(g in allowed_groups for g in group_names):
            from django.http import HttpResponse
            return HttpResponse("No tens permisos per accedir a aquesta aplicació.", status=403)
        User = get_user_model()
        username = userinfo.get('username')
        user, _ = User.objects.get_or_create(username=username)
        user.first_name = userinfo.get('first_name', '')
        user.last_name = userinfo.get('last_name', '')
        user.email = userinfo.get('email', '')
        user.save()
        for group_name in group_names:
            group, _ = Group.objects.get_or_create(name=group_name)
            user.groups.add(group)
        login(request, user)

    request.session['access_token'] = token['access_token']
    next_url = request.session.pop('oauth_next_url', None)
    return redirect(next_url or settings.LOGIN_REDIRECT_URL)


def user_info(request):
    token = request.session.get('access_token')
    if not token:
        return JsonResponse({"error": "No s'ha trobat el token d'accés."}, status=401)
    response = http_requests.get(
        _oauth_userinfo_url(),
        headers={"Authorization": f"Bearer {token}"},
    )
    if response.status_code == 200:
        return JsonResponse(response.json())
    return JsonResponse({"error": "No s'ha pogut recuperar la informació de l'usuari"}, status=502)


def logout_view(request):
    request.session.pop('access_token', None)
    request.session.pop('refresh_token', None)
    logout(request)
    next_url = request.GET.get('next') or request.META.get('HTTP_REFERER', '/')
    return redirect(next_url)


def make_version_view(pyproject_path):
    def version_view(request):
        try:
            with open(pyproject_path, 'rb') as f:
                ver = tomllib.load(f).get('project', {}).get('version', 'unknown')
        except Exception:
            ver = 'unknown'
        return JsonResponse({'version': ver})
    return version_view
