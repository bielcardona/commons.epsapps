from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, override_settings

from eps_commons.ldap import lookup_ldap_user_by_email, search_ldap_candidates

LDAP_SETTINGS = dict(
    LDAP_URL='ldaps://ldap.example', LDAP_BASE_DN='dc=uib,dc=es',
    LDAP_BIND_DN='uid=bind', LDAP_BIND_PASSWORD='pw',
)


def _entry(uid, cn, email, groups=(), given='', sn=''):
    return (f'uid={uid},ou=persones,dc=uib,dc=es', {
        'uid': [uid.encode()],
        'cn': [cn.encode()],
        'givenName': [given.encode()],
        'sn': [sn.encode()],
        'mailAutoReplyMode': [email.encode()],
        'isMemberOf': [f'cn={g},ou=grups,dc=uib,dc=es'.encode() for g in groups],
    })


def _fake_ldap(results):
    """Patch de `ldap.initialize`: la connexió retorna `results` a
    `search_s` (amb una referència de cerca sense dn, com fa LDAP real)."""
    conn = MagicMock()
    conn.search_s.return_value = list(results) + [(None, ['ldaps://ref'])]
    return patch('ldap.initialize', return_value=conn), conn


def _filter(conn):
    return conn.search_s.call_args.args[2]


@override_settings(**LDAP_SETTINGS)
class LookupLdapUserByEmailTests(SimpleTestCase):
    def test_troba_per_correu_exacte(self):
        patcher, conn = _fake_ldap([_entry(
            'abc123', 'Joan Pons Ferrer', 'joan.pons@estudiant.uib.cat',
            groups=['ALU', 'CENALU_EPSU'], given='Joan', sn='Pons Ferrer',
        )])
        with patcher:
            result = lookup_ldap_user_by_email('joan.pons@estudiant.uib.cat')
        self.assertEqual(_filter(conn), '(mailAutoReplyMode=joan.pons@estudiant.uib.cat)')
        self.assertEqual(result, {
            'username': 'abc123',
            'common_name': 'Joan Pons Ferrer',
            'first_name': 'Joan',
            'last_name': 'Pons Ferrer',
            'email': 'joan.pons@estudiant.uib.cat',
            'groups': ['ALU', 'CENALU_EPSU'],
        })

    def test_sense_resultats_retorna_none(self):
        patcher, _ = _fake_ldap([])
        with patcher:
            self.assertIsNone(lookup_ldap_user_by_email('ningu@uib.cat'))

    def test_mes_d_un_resultat_retorna_none(self):
        patcher, _ = _fake_ldap([
            _entry('abc123', 'A', 'x@uib.cat'), _entry('def456', 'B', 'x@uib.cat'),
        ])
        with patcher:
            self.assertIsNone(lookup_ldap_user_by_email('x@uib.cat'))

    def test_escapa_el_filtre(self):
        patcher, conn = _fake_ldap([])
        with patcher:
            lookup_ldap_user_by_email('a*)(uid=*@uib.cat')
        self.assertEqual(_filter(conn), r'(mailAutoReplyMode=a\2a\29\28uid=\2a@uib.cat)')

    def test_correu_buit_no_consulta_ldap(self):
        patcher, conn = _fake_ldap([])
        with patcher:
            self.assertIsNone(lookup_ldap_user_by_email(''))
        conn.search_s.assert_not_called()

    @override_settings(LDAP_URL=None)
    def test_sense_configuracio_retorna_none(self):
        self.assertIsNone(lookup_ldap_user_by_email('x@uib.cat'))

    def test_error_ldap_retorna_none(self):
        patcher, conn = _fake_ldap([])
        conn.search_s.side_effect = Exception('caigut')
        with patcher:
            self.assertIsNone(lookup_ldap_user_by_email('x@uib.cat'))


@override_settings(**LDAP_SETTINGS)
class SearchLdapCandidatesTests(SimpleTestCase):
    def test_retorna_candidats_amb_grups(self):
        patcher, conn = _fake_ldap([
            _entry('abc123', 'Joan Pons Ferrer', 'j@uib.cat', groups=['ALU', 'CENALU_EPSU']),
            _entry('def456', 'Joan Pons Mas', 'k@uib.cat', groups=['ALU']),
        ])
        with patcher:
            result = search_ldap_candidates('Joan Pons')
        self.assertEqual(_filter(conn), '(cn=*Joan Pons*)')
        self.assertEqual([c['username'] for c in result], ['abc123', 'def456'])
        self.assertEqual(result[0]['groups'], ['ALU', 'CENALU_EPSU'])
        self.assertEqual(result[0]['common_name'], 'Joan Pons Ferrer')

    def test_filtra_per_grup(self):
        patcher, conn = _fake_ldap([])
        with patcher:
            search_ldap_candidates('Joan Pons', group='CENALU_EPSU')
        self.assertEqual(
            _filter(conn),
            '(&(isMemberOf=cn=CENALU_EPSU,ou=grups,dc=uib,dc=es)(cn=*Joan Pons*))',
        )

    def test_escapa_el_filtre(self):
        patcher, conn = _fake_ldap([])
        with patcher:
            search_ldap_candidates('Joan*)(uid=*')
        self.assertEqual(_filter(conn), r'(cn=*Joan\2a\29\28uid=\2a*)')

    def test_consulta_buida_no_consulta_ldap(self):
        patcher, conn = _fake_ldap([])
        with patcher:
            self.assertEqual(search_ldap_candidates('  '), [])
        conn.search_s.assert_not_called()

    def test_error_ldap_retorna_llista_buida(self):
        patcher, conn = _fake_ldap([])
        conn.search_s.side_effect = Exception('caigut')
        with patcher:
            self.assertEqual(search_ldap_candidates('Joan'), [])
