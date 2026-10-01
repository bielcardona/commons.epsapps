from unittest.mock import MagicMock, patch

from django.contrib.auth.models import Group, User
from django.test import TestCase, override_settings


def _login_oauth(client, groups, username='usr001'):
    """Simula el retorn del hub a oauth_callback amb els `groups` donats."""
    session = client.session
    session['oauth_code_verifier'] = 'v'
    session['oauth_state'] = 's'
    session.save()
    userinfo = MagicMock(status_code=200)
    userinfo.json.return_value = {
        'username': username, 'email': f'{username}@uib.es',
        'first_name': 'Nom', 'last_name': 'Cognom', 'groups': groups,
    }
    with patch('eps_commons.views.OAuth2Session') as session_cls:
        oauth = session_cls.return_value
        oauth.fetch_token.return_value = {'access_token': 't'}
        oauth.get.return_value = userinfo
        client.get('/oauth/callback/?code=c&state=s')
    return User.objects.get(username=username)


def _grups(user):
    return set(user.groups.values_list('name', flat=True))


class OAuthCallbackGrupsTests(TestCase):
    def test_afegeix_els_grups_rebuts(self):
        user = _login_oauth(self.client, ['Professorat', 'Direccio'])
        self.assertEqual(_grups(user), {'Professorat', 'Direccio'})

    def test_treu_els_rols_que_el_hub_ja_no_envia(self):
        _login_oauth(self.client, ['Professorat', 'Direccio'])
        user = _login_oauth(self.client, ['Professorat'])
        self.assertEqual(_grups(user), {'Professorat'})

    def test_no_toca_els_grups_propis_de_l_app(self):
        user = User.objects.create(username='usr001')
        user.groups.add(Group.objects.create(name='GrupLocal'))
        user = _login_oauth(self.client, ['Professorat'])
        self.assertEqual(_grups(user), {'Professorat', 'GrupLocal'})

    @override_settings(OAUTH2_MANAGED_GROUPS=['Direccio'])
    def test_respecta_oauth2_managed_groups(self):
        user = User.objects.create(username='usr001')
        user.groups.add(Group.objects.create(name='Direccio'), Group.objects.create(name='Professorat'))
        user = _login_oauth(self.client, [])
        self.assertEqual(_grups(user), {'Professorat'})


class CurrentRolMiddlewareTests(TestCase):
    def setUp(self):
        self.user = User.objects.create(username='usr001')
        self.user.groups.add(Group.objects.create(name='Professorat'))
        self.client.force_login(self.user)

    def _set_rol(self, rol):
        session = self.client.session
        session['current_rol'] = rol
        session.save()

    def test_mante_un_rol_valid(self):
        self._set_rol('Professorat')
        self.client.get('/ping/')
        self.assertEqual(self.client.session['current_rol'], 'Professorat')

    def test_reinicia_un_rol_que_ja_no_te(self):
        self._set_rol('Direccio')
        self.client.get('/ping/')
        self.assertEqual(self.client.session['current_rol'], 'Professorat')

    def test_rol_a_none_si_no_te_cap_grup(self):
        self.user.groups.clear()
        self._set_rol('Direccio')
        self.client.get('/ping/')
        self.assertIsNone(self.client.session['current_rol'])
