"""
Utilitats LDAP per als projectes EPS.

Requereix python-ldap: uv add 'eps-commons[ldap]'

Configuració necessària a settings.py:
    LDAP_URL         = 'ldaps://ldap.uib.es'
    LDAP_BASE_DN     = 'dc=uib,dc=es'
    LDAP_BIND_DN     = 'uid=...'
    LDAP_BIND_PASSWORD = '...'
"""

import logging

logger = logging.getLogger(__name__)

ROL_LDAP_GROUP = {
    'Professorat': 'cn=PDI,ou=grups,dc=uib,dc=es',
    'PTGAS':       'cn=PAS,ou=grups,dc=uib,dc=es',
    'Alumnat':     'cn=ALU,ou=grups,dc=uib,dc=es',
    'Direccio':    'cn=CENEQPDIR_EPSU,ou=grups,dc=uib,dc=es',
}


def _setup_ldap_tls(ldap_lib):
    ldap_lib.set_option(ldap_lib.OPT_X_TLS_REQUIRE_CERT, ldap_lib.OPT_X_TLS_DEMAND)
    try:
        import certifi
        ldap_lib.set_option(ldap_lib.OPT_X_TLS_CACERTFILE, certifi.where())
    except (ImportError, ValueError):
        # macOS SecureTransport no suporta OPT_X_TLS_CACERTFILE
        ldap_lib.set_option(ldap_lib.OPT_X_TLS_REQUIRE_CERT, ldap_lib.OPT_X_TLS_ALLOW)


def _get_ldap_settings():
    from django.conf import settings
    ldap_url = getattr(settings, 'LDAP_URL', None)
    base_dn = getattr(settings, 'LDAP_BASE_DN', None)
    bind_dn = getattr(settings, 'LDAP_BIND_DN', None)
    bind_password = getattr(settings, 'LDAP_BIND_PASSWORD', None)
    return ldap_url, base_dn, bind_dn, bind_password


def lookup_ldap_user(username):
    """
    Cerca un usuari per UID al directori LDAP.
    Retorna {'first_name', 'last_name', 'email'} o None si no es troba.
    """
    try:
        import ldap
        from django.utils.encoding import force_str
        ldap_url, base_dn, bind_dn, bind_password = _get_ldap_settings()
        if not all([ldap_url, base_dn, bind_dn, bind_password]):
            return None
        _setup_ldap_tls(ldap)
        conn = ldap.initialize(ldap_url)
        conn.simple_bind_s(bind_dn, bind_password)
        result = conn.search_s(base_dn, ldap.SCOPE_SUBTREE, f'(uid={username})', [])
        if result:
            _, entry = result[0]
            return {
                'first_name': force_str(entry.get('givenName', [b''])[0]),
                'last_name': force_str(entry.get('sn', [b''])[0]),
                'email': force_str(entry.get('mailAutoReplyMode', [b''])[0]),
            }
    except Exception:
        logger.debug('LDAP lookup failed for username=%s', username)
    return None


def search_ldap_records(query_string, rol=None):
    """
    Cerca registres LDAP per cn o uid que continguin query_string.
    Si rol és un valor vàlid de ROL_LDAP_GROUP, filtra per isMemberOf.
    Retorna llista de {'username', 'common_name'}.
    """
    try:
        import ldap
        from django.utils.encoding import force_str
        ldap_url, base_dn, bind_dn, bind_password = _get_ldap_settings()
        if not all([ldap_url, base_dn, bind_dn, bind_password]):
            return []
        _setup_ldap_tls(ldap)
        conn = ldap.initialize(ldap_url)
        conn.simple_bind_s(bind_dn, bind_password)
        text_filter = f'(|(cn=*{query_string}*)(uid=*{query_string}*))'
        ldap_group = ROL_LDAP_GROUP.get(rol)
        ldap_filter = f'(&(isMemberOf={ldap_group}){text_filter})' if ldap_group else text_filter
        result = conn.search_s(
            base_dn,
            ldap.SCOPE_SUBTREE,
            ldap_filter,
            ['uid', 'cn'],
        )
        results = []
        for dn, entry in result:
            if dn is None:
                continue
            uid = force_str(entry.get('uid', [b''])[0])
            cn = force_str(entry.get('cn', [b''])[0])
            results.append({'username': uid, 'common_name': cn})
        return results
    except Exception:
        logger.debug('LDAP search failed for query=%s', query_string)
        return []


def lookup_by_cn(cn_query):
    """
    Cerca al LDAP per nom complet (cn).
    Retorna 'Cognoms, Nom' si es troba de manera única, None altrament.
    """
    try:
        import ldap
        from django.utils.encoding import force_str
        ldap_url, base_dn, bind_dn, bind_password = _get_ldap_settings()
        if not all([ldap_url, base_dn, bind_dn, bind_password]):
            return None
        _setup_ldap_tls(ldap)
        conn = ldap.initialize(ldap_url)
        conn.simple_bind_s(bind_dn, bind_password)
        result = conn.search_s(
            base_dn,
            ldap.SCOPE_SUBTREE,
            f'(cn=*{cn_query}*)',
            ['givenName', 'sn'],
        )
        entries = [(dn, e) for dn, e in result if dn is not None]
        if len(entries) == 1:
            _, entry = entries[0]
            given = force_str(entry.get('givenName', [b''])[0])
            surname = force_str(entry.get('sn', [b''])[0])
            if given and surname:
                return f'{surname}, {given}'
        elif len(entries) > 1:
            logger.warning("Cerca LDAP ambigua per '%s' (%d resultats)", cn_query, len(entries))
        else:
            logger.warning("Sense resultats LDAP per '%s'", cn_query)
    except Exception as e:
        logger.warning("Error LDAP cercant '%s': %s", cn_query, e)
    return None


_PERSON_ATTRS = ['uid', 'cn', 'givenName', 'sn', 'mailAutoReplyMode', 'isMemberOf']


def _connect():
    """Connexió LDAP autenticada, o None si falta configuració."""
    import ldap
    ldap_url, base_dn, bind_dn, bind_password = _get_ldap_settings()
    if not all([ldap_url, base_dn, bind_dn, bind_password]):
        return None, None
    _setup_ldap_tls(ldap)
    conn = ldap.initialize(ldap_url)
    conn.simple_bind_s(bind_dn, bind_password)
    return conn, base_dn


def _person(entry):
    """Entrada LDAP -> dict amb `username`, `common_name`, `first_name`,
    `last_name`, `email` i `groups` (noms curts: 'ALU', 'CENALU_EPSU'...)."""
    from django.utils.encoding import force_str

    def first(attr):
        return force_str(entry.get(attr, [b''])[0])

    groups = []
    for dn in entry.get('isMemberOf', []):
        rdn = force_str(dn).split(',', 1)[0]
        if rdn.lower().startswith('cn='):
            groups.append(rdn[3:])
    return {
        'username': first('uid'),
        'common_name': first('cn'),
        'first_name': first('givenName'),
        'last_name': first('sn'),
        'email': first('mailAutoReplyMode'),
        'groups': groups,
    }


def _search_people(ldap_filter):
    import ldap
    conn, base_dn = _connect()
    if conn is None:
        return []
    result = conn.search_s(base_dn, ldap.SCOPE_SUBTREE, ldap_filter, _PERSON_ATTRS)
    return [_person(entry) for dn, entry in result if dn is not None]


def lookup_ldap_user_by_email(email):
    """
    Cerca una persona pel correu exacte (LDAP no admet comodins en aquest
    atribut). Retorna el dict de `_person`, o None si no n'hi ha cap, n'hi
    ha més d'una o LDAP falla.
    """
    if not email or not email.strip():
        return None
    try:
        import ldap.filter
        people = _search_people(
            f'(mailAutoReplyMode={ldap.filter.escape_filter_chars(email.strip())})'
        )
    except Exception:
        logger.warning('Error LDAP cercant per correu')
        return None
    if len(people) > 1:
        logger.warning('Cerca LDAP per correu ambigua (%d resultats)', len(people))
        return None
    return people[0] if people else None


def search_ldap_candidates(query_string, group=None):
    """
    Cerca persones el cn de les quals conté `query_string`; si es dona
    `group` (nom curt, p.ex. 'CENALU_EPSU'), només els seus membres.
    Retorna llista de dicts de `_person` (amb `groups`), per comparar-hi el
    nom exactament i filtrar per grup a qui crida. Llista buida si LDAP falla.
    """
    if not query_string or not query_string.strip():
        return []
    try:
        import ldap.filter
        text_filter = f'(cn=*{ldap.filter.escape_filter_chars(query_string.strip())}*)'
        if group:
            group_dn = f'cn={ldap.filter.escape_filter_chars(group)},ou=grups,dc=uib,dc=es'
            text_filter = f'(&(isMemberOf={group_dn}){text_filter})'
        return _search_people(text_filter)
    except Exception:
        logger.warning('Error LDAP cercant candidats')
        return []
