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
