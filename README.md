# eps-commons

Llibreria compartida entre els projectes Django de l'EPS (parcials, vertical, ...).

Conté la maquinària comuna: autenticació OAuth2, impersonació d'usuaris,
middleware, context processors, template base, utilitats LDAP i templatetags.

## Ús

Cada projecte la declara com a dependència editable al seu `pyproject.toml`:

```toml
[tool.uv.sources]
eps-commons = { path = "../commons", editable = true }
```

## Problema conegut: uv + Python 3.13 + macOS

### Símptoma

`ModuleNotFoundError: No module named 'eps_commons'` en executar `uv run`
o qualsevol Python del venv, malgrat que `uv sync` reporti èxit.

### Causa

`uv` crea els fitxers `.pth` de les instal·lacions editables amb el flag
macOS `UF_HIDDEN` activat (ocult per al Finder). Python 3.13 va afegir
una comprovació nova a `site.addpackage()` que **salta explícitament** els
fitxers `.pth` marcats com a ocults:

```python
# cpython/Lib/site.py (Python 3.13)
if (getattr(st, 'st_flags', 0) & stat.UF_HIDDEN):
    _trace(f"Skipping hidden .pth file: {fullname!r}")
    return
```

El `.pth` és al directori, `os.path.exists()` el troba, però Python no
l'afegeix a `sys.path`. No es mostra cap avís.

Es pot confirmar amb:

```bash
python3 -c "
import os, stat
pth = '.venv/lib/python3.13/site-packages/_editable_impl_eps_commons.pth'
st = os.lstat(pth)
print('UF_HIDDEN:', bool(getattr(st, 'st_flags', 0) & stat.UF_HIDDEN))
"
# UF_HIDDEN: True
```

### Solució

Afegir `commons/` a `PYTHONPATH` al `.envrc` de cada projecte dependent:

```bash
export PYTHONPATH="$PWD/../commons${PYTHONPATH:+:$PYTHONPATH}"
```

Això fa que `eps_commons` sigui importable directament, sense dependre
del mecanisme de `.pth`. La instal·lació editable es manté al `pyproject.toml`
per mantenir la resolució de dependències transitives.

### Estat

Bug reportat a uv: els `.pth` files no haurien de tenir `UF_HIDDEN` ja que
és un flag que indica "ocult per a l'usuari", no "fitxer de sistema privat".
Mentre no es corregeixi, el `PYTHONPATH` al `.envrc` és la solució estable.

---

## Estat del workspace epsapps

### Projectes

| Projecte | Descripció |
|---|---|
| `commons/` | Biblioteca compartida (aquest repo) |
| `vertical/` | Coordinació vertical de continguts entre assignatures |
| `parcials/` | Gestió de proves d'avaluació i calendaris de parcials |

### Feina feta (sessió d'homogeneïtzació)

#### Moviments cap a commons
- **`ROL` class** (`PROFESSORAT`, `DIRECCIO`): era duplicada a `vertical/models.py`
  i `parcials/utils.py`. Ara viu a `eps_commons/utils.py`.
- **`get_full_name`**: era duplicada a `parcials/utils.py`. `parcials` ara la
  importa des d'`eps_commons.utils`.
- **`impersonation_context`**: era reimplementada a `parcials/context_processors.py`
  (versió incompleta, sense `can_impersonate`). S'ha eliminat; `parcials` usa ara
  `eps_commons.context_processors.impersonation_context`. La versió de commons
  s'ha actualitzat per retornar també `can_impersonate` (necessari a la template
  `gestio/gestio_index.html`).
- **`_lookup_ldap_user`**: còpia local a `vertical/services.py` amb path TLS
  hardcoded. Substituïda per `eps_commons.ldap.lookup_ldap_user`.
- **`make_version_view`**: factoria afegida a `eps_commons/views.py` per
  eliminar la vista `/version/` duplicada en ambdós projectes.

#### Homogeneïtzació de configuració
| # | Canvi | Projecte |
|---|---|---|
| 1 | `LANGUAGE_CODE='ca'`, `TIME_ZONE='Europe/Madrid'` | parcials |
| 2 | `WhiteNoiseMiddleware` just després de `SecurityMiddleware` | parcials |
| 3 | `SECRET_KEY = os.environ['SECRET_KEY']` (sense fallback insegur) | vertical |
| 4 | `IMPERSONATION_ENABLED/GROUP/SUCCESS_URL` a `epsapps_prod` | parcials |
| 5 | `AUTH_PASSWORD_VALIDATORS` complets a prod, buits a `local` | parcials |
| 6 | `make_version_view` eliminant duplicació de vista `/version/` | ambdós |

#### Infraestructura
- `git init` a `commons/`
- Build backend canviat de `uv_build` a `hatchling`
- `PYTHONPATH=../commons` afegit als `.envrc` de `vertical` i `parcials`

---

### Feina pending

#### Petites inconsistències de configuració

- **`STATIC_URL`**: `vertical` usa `'/static/'` (amb `/` inicial), `parcials` usa
  `'static/'`. Django 4+ recomana sense `/` inicial. Caldria alinear `vertical`.

- **`STORAGES`**: `parcials/base.py` configura explícitament
  `CompressedManifestStaticFilesStorage` de whitenoise. `vertical` no la
  configura; usa el comportament per defecte. Cal decidir si alinear.

- **`LOGIN_URL` a `base.py`**: `vertical` la defineix com `'login'` a `base.py`
  (sobreescrita a prod per `'oauth_login'`). `parcials` no la defineix a `base.py`
  i la posa directament a cada entorn (`local` i `epsapps_prod`). Inconsistència
  menor, cap pràctica és clarament millor.

- **`IMPERSONATION_GROUP` a `vertical/epsapps_prod`**: `vertical` activa
  `IMPERSONATION_ENABLED = True` a prod però no defineix `IMPERSONATION_GROUP`.
  Això significa que qualsevol superusuari pot impersonar (sense necessitat de
  ser del grup Direccio). Verificar si és intencional o si cal afegir
  `IMPERSONATION_GROUP = 'Direccio'`.

#### Estructura de templates

`parcials` divideix les templates entre dos llocs:
- `parcials/templates/` (arrel del projecte, en `DIRS`) — base, home, errors, registration
- `parcials/parcials/templates/` (dins l'app, via `APP_DIRS`) — templates de l'app

`vertical` les té totes a `vertical/templates/` (dins l'app, via `APP_DIRS`).

L'enfocament de `vertical` és més consistent. Migrar `parcials` seria un
refactor no trivial però clarificaria l'estructura.

#### Configs d'entorn exclusius de `parcials`

`parcials` té dos entorns que `vertical` no té:
- `epsapps_test/settings.py` — entorn de test al servidor amb OAuth2
  (`DEBUG=True`, `LOGIN_URL='oauth_login'`)
- `local_compose/settings.py` — entorn local amb Docker Compose
  (`DEBUG=True`, `LOGIN_URL='oauth_login'`)

Verificar si `vertical` necessita configuracions equivalents.

#### Potencials candidats futurs per a commons

- **`MaintenanceModeMiddleware`** (ara a `parcials/middleware.py`): prou genèric
  per ser útil a qualsevol projecte. Requereix `django-solo` com a dependència.
- **`ensure_user_exists` / `ensure_professor_exists`**: lògiques similars de
  vinculació User↔Professor al login, però prou diferenciades pel model de dades
  de cada app per no fusionar ara.
