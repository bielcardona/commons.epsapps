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
