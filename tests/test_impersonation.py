from django.contrib.auth.models import Group, User
from django.test import TestCase, override_settings


@override_settings(IMPERSONATION_ENABLED=True)
class ImpersonationPermisosTests(TestCase):
    def setUp(self):
        self.direccio = User.objects.create(username='dir001')
        self.direccio.groups.add(Group.objects.create(name='Direccio'))
        self.professor = User.objects.create(username='prof001')
        self.superuser = User.objects.create(username='admin', is_superuser=True)
        self.staff = User.objects.create(username='staff', is_staff=True)

    def _impersona(self, impersonador, objectiu):
        self.client.force_login(impersonador)
        response = self.client.get(f'/impersonate/{objectiu.username}/')
        return response, self.client.session.get('_impersonated_user_id')

    def test_sense_grups_permesos_direccio_no_pot(self):
        _, impersonat = self._impersona(self.direccio, self.professor)
        self.assertIsNone(impersonat)

    @override_settings(IMPERSONATION_ALLOWED_GROUPS=['Direccio'])
    def test_grup_permes_pot_impersonar(self):
        _, impersonat = self._impersona(self.direccio, self.professor)
        self.assertEqual(impersonat, self.professor.pk)

    @override_settings(IMPERSONATION_ALLOWED_GROUPS=['Direccio'])
    def test_grup_permes_no_pot_impersonar_superusuaris_ni_staff(self):
        for objectiu in (self.superuser, self.staff):
            response, impersonat = self._impersona(self.direccio, objectiu)
            self.assertEqual(response.status_code, 404)
            self.assertIsNone(impersonat)

    @override_settings(IMPERSONATION_ALLOWED_GROUPS=['Direccio'])
    def test_llista_amaga_superusuaris_i_staff(self):
        from eps_commons.views import _impersonable_users
        usernames = set(_impersonable_users(self.direccio).values_list('username', flat=True))
        self.assertEqual(usernames, {'dir001', 'prof001'})

    @override_settings(IMPERSONATION_ALLOWED_GROUPS=['Direccio'])
    def test_professor_sense_grup_no_pot(self):
        _, impersonat = self._impersona(self.professor, self.direccio)
        self.assertIsNone(impersonat)

    def test_superusuari_pot_impersonar_qualsevol(self):
        _, impersonat = self._impersona(self.superuser, self.staff)
        self.assertEqual(impersonat, self.staff.pk)
