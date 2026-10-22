# eps-commons

Llibreria compartida entre els projectes Django de l'EPS (parcials, vertical, ...).

Conté la maquinària comuna: autenticació OAuth2, impersonació d'usuaris,
middleware, context processors, template base, utilitats LDAP i templatetags.

## Rols

El hub és l'única font dels rols. En cada login, `oauth_callback` afegeix
els grups que envia el hub i **treu** els de `OAUTH2_MANAGED_GROUPS` que ja
no envia (per defecte, els valors de `ROL`: Professorat, Direccio, Alumnat,
PTGAS). Els grups que no són en aquesta llista són propis de l'app i no es
toquen.

`CurrentRolMiddleware` reinicia el `current_rol` de la sessió si l'usuari ja
no té aquell grup. S'ha de posar després de `CurrentUserMiddleware`:

```python
MIDDLEWARE = [
    ...
    'eps_commons.middleware.CurrentUserMiddleware',
    'eps_commons.middleware.CurrentRolMiddleware',
]
```

## Impersonació

Cal `IMPERSONATION_ENABLED = True`. Per defecte només hi poden fer
impersonate els superusuaris (i, si es defineix `IMPERSONATION_GROUP`, només
els superusuaris d'aquest grup). `IMPERSONATION_ALLOWED_GROUPS` hi afegeix
els membres dels grups indicats:

```python
IMPERSONATION_ALLOWED_GROUPS = ['Direccio']
```

Qui no és superusuari no pot impersonar superusuaris ni usuaris staff.

## Tests

```sh
PYTHONPATH=. DJANGO_SETTINGS_MODULE=tests.settings python -m django test tests
```
