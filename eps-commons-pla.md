# Pla: Extreure codi comú dels tres projectes en un paquet compartit `eps-commons`

## Context

ParcialsApp, tfg.epsapps i vertical.epsapps comparteixen nombrosos patrons idèntics o quasi-idèntics: integració LDAP, gestió de rols per sessió, la templatetag `check_groups`, processadors de context, la vista `swap_rol`, i la creació automàtica de Professor en el login. Ara mateix, qualsevol millora s'ha d'aplicar tres vegades manualment.

L'objectiu és crear un paquet `eps-commons` que centralitzi aquest codi, i actualitzar els tres projectes per usar-lo.

---

## Mòduls comuns identificats

### 1. Templatetag `check_groups` → filtre `has_group`
- **Fitxers actuals**: `parcials/templatetags/check_groups.py`, `tfg/templatetags/check_groups.py`, `coordination/templatetags/check_groups.py`
- **Contingut**: filtre Django que comprova si un usuari pertany a un grup
- **Acció**: extreure a `eps_commons/templatetags/check_groups.py`

### 2. Context processors: `current_rol` + `basic_urls`
- **Fitxers actuals**: `parcials/context_processors.py`, `tfg/context_processors.py`, `coordination/context_processors.py`
- **Contingut**: injecta `current_rol` (des de sessió/grups Django) i `LOGIN_URL`/`LOGOUT_URL` a tots els templates
- **Variacions que queden als projectes**: `any_academic_context` (ParcialsApp), `impersonation_context` (tfg, vertical), `site_settings`
- **Acció**: extreure `current_rol` + `basic_urls` a `eps_commons/context_processors.py`

### 3. Vista `swap_rol` + URL
- **Fitxers actuals**: vista a `ParcialsApp/views.py`, `tfg_site/urls.py`, `vertical_coordination/urls.py`
- **Contingut**: canvia `request.session['current_rol']` al grup indicat i redirigeix
- **Acció**: extreure a `eps_commons/views.py` + `eps_commons/urls.py`

### 4. Utilitats LDAP (cerca i normalització)
- **Fitxers actuals**: `parcials/search_directory.py`, `tfg/utils.py`, `coordination/services.py`
- **Funcions comunes**: `strip_title()`, `normalize_text()`, `lookup_in_ldap()`, `search_ldap_records()`
- **Acció**: extreure funcions pures a `eps_commons/ldap.py`

### 5. Creació automàtica de Professor en login
- **Fitxers actuals**: `parcials/services.py`+`signals.py`, `tfg/services.py`, `coordination/signals.py`
- **Contingut**: senyal `user_logged_in` que crida `ensure_professor_exists(user)` amb normalització de nom
- **Nota**: el model `Professor` és diferent a cada projecte → el model no es mou; sí el patró de senyal i la normalització
- **Acció**: extreure `normalize_text()` i el patró com a utilitat configurable (callback injectable)

### 6. Middleware d'impersonació + usuari actual per thread
- **Fitxers actuals**: `tfg/middleware/current_user.py`, `coordination/middleware/current_user.py`
- **Contingut**: swapeja `request.user` per un usuari impersonat (sessió); emmagatzema usuari actual en thread-local
- **ParcialsApp**: no té impersonació → podria adoptar-la
- **Acció**: extreure a `eps_commons/middleware.py`

### 7. Utilitats genèriques
- **`remove_empty_values(dict)`** (`ParcialsApp/utils.py`): elimina valors buits de dicts niats
- **`get_full_name(user)`**: formateja nom com `"Cognom, Nom"`
- **Acció**: extreure a `eps_commons/utils.py`

---

## Estructura del paquet nou

```
eps-commons/                         # Nou repositori/directori al workspace (carpeta actual)
├── eps_commons/
│   ├── __init__.py
│   ├── apps.py
│   ├── context_processors.py        # current_rol, basic_urls
│   ├── views.py                     # swap_rol view
│   ├── urls.py                      # urlpatterns per incloure a cada projecte
│   ├── ldap.py                      # strip_title, normalize_text, lookup_in_ldap
│   ├── middleware.py                # CurrentUserMiddleware + impersonació
│   ├── utils.py                     # remove_empty_values, get_full_name
│   └── templatetags/
│       ├── __init__.py
│       └── check_groups.py          # has_group filter
├── pyproject.toml
└── README.md
```

---

## Estratègia d'implementació

### Fase 1: Crear el paquet `eps-commons`
1. Crear `eps-commons/` al workspace (germà dels tres projectes)
2. Inicialitzar estructura Python (`pyproject.toml` amb nom `eps-commons`)
3. Copiar i adaptar els mòduls per ordre de complexitat creixent:
   - Primer: `templatetags/check_groups.py` (sense dependències)
   - Segon: `utils.py` (funcions pures)
   - Tercer: `context_processors.py` + `views.py` + `urls.py` (depenen de Django)
   - Quart: `ldap.py` (depèn de python-ldap)
   - Cinquè: `middleware.py` (depèn de Django + sessió)

### Fase 2: Migrar ParcialsApp (pilot)
0. Fer una còpia de ParcialsApp (per exemple ParcialsAppPilotProgram) on fer tots els canvis. No tocar ParcialsApp
1. `uv add ../eps-commons` (dependència local en mode editable)
2. Afegir `eps_commons` a `INSTALLED_APPS`
3. Substituir imports i eliminar fitxers duplicats
4. Actualitzar `settings.py`: canviar `context_processors` i `MIDDLEWARE`
5. Actualitzar `urls.py`: `include('eps_commons.urls')` per a `swap_rol`
6. Verificar amb `manage.py check` + prova manual

### Fase 3: Migrar tfg.epsapps i vertical.epsapps (no fer-ho ara!)
- Repetir Fase 2 per a cada projecte
- Documentar les variacions legítimes que resten a cada projecte

---

## Fitxers a modificar per projecte

| Projecte | Fitxer | Canvi |
|---|---|---|
| ParcialsApp | `parcials/templatetags/check_groups.py` | Eliminar → usar `eps_commons` |
| ParcialsApp | `parcials/context_processors.py` | Eliminar `current_rol`+`basic_urls` → mantenir `any_academic_context` |
| ParcialsApp | `ParcialsApp/utils.py` | Eliminar `remove_empty_values` → usar `eps_commons` |
| ParcialsApp | `ParcialsApp/urls.py` | `swap_rol` → `include('eps_commons.urls')` |
| tfg.epsapps | `tfg/templatetags/check_groups.py` | Eliminar → usar `eps_commons` |
| tfg.epsapps | `tfg/context_processors.py` | Eliminar parts comunes |
| tfg.epsapps | `tfg/utils.py` | Eliminar funcions LDAP comunes |
| tfg.epsapps | `tfg/middleware/current_user.py` | Eliminar → usar `eps_commons` |
| vertical | `coordination/templatetags/check_groups.py` | Eliminar → usar `eps_commons` |
| vertical | `coordination/context_processors.py` | Eliminar parts comunes |
| vertical | `coordination/middleware/current_user.py` | Eliminar → usar `eps_commons` |

---

## Verificació (per a cada projecte)

1. `uv run manage.py check` — sense errors de configuració
2. Arrancar servidor (`uv run manage.py runserver`) i fer login
3. Verificar canvi de rol (`/swap_rol/Professorat/`) → `current_rol` canvia al template
4. Verificar que `{% if user|has_group:"Direccio" %}` funciona als templates
5. Verificar que `current_rol` i `LOGIN_URL` apareixen al context

---

## Notes addicionals

- **Dependències del paquet**: Django == 5.2, python-ldap (opcional per a `ldap.py`)
- **Compatibilitat**: els tres projectes usen Django 5.x i `eps_oauth_client` → el paquet ha de ser compatible
- **Publicació**: inicialment com a dependència local (`path = "../eps-commons"`); més endavant es pot publicar a PyPI privat o GitHub Packages
