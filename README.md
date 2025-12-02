# repairkawapp

![CI](https://github.com/Repair-Cafe-Orsay/repairkawapp/actions/workflows/ci.yml/badge.svg)
![Coverage](https://codecov.io/gh/Repair-Cafe-Orsay/repairkawapp/branch/refactor/graph/badge.svg)
Application for Repair Café - initially developped for/by the Repair Café Orsay

# Installation

* create database
* copy `config-template.json` to `config.json` and adapt configuration
* create python virtual env and install requirements
* launch `init_db.py` to initialize the database - this can be done only once, for model upgrade, use `flask-alembic` (https://flask-alembic.readthedocs.io/en/latest/)

## Database migrations (Alembic)

After the first initialization (`init_db.py`), structural changes are managed with Alembic.

Setup performed in this repo:

* `alembic.ini` at project root
* `alembic/` directory with `env.py`, `versions/` and script template
* First revision: enlarge `user.password` to length 255.

Typical workflow:

1. Adjust models in `repairkawapp/models.py`.
2. Autogenerate a revision (example):
  ```
  alembic revision --autogenerate -m "your message"
  ```
3. Review the generated file under `alembic/versions/` and edit if needed.
4. Apply migrations:
  ```
  alembic upgrade head
  ```
5. (If needed) downgrade:
  ```
  alembic downgrade -1
  ```

Configuration: Alembic reads the Flask app database URL from `create_app()` inside `alembic/env.py`; ensure `config.json` is present with a valid `SQLALCHEMY_DATABASE_URI` before running commands.

Production hint: keep `init_db.py` only for first empty database creation. Afterwards use Alembic exclusively.

# Development

* launch flask server

```
flask --debug --app repairkawapp run
```

## Code Structure

The structure of the code is the following:

* `repairkawapp/models.py` defines the data model using SQLAlchemy ORM. Prefered database is mysql/mariadb, but
it should also be working well with postgres.
* The three following modules define the available routes organized by `blueprint` (http://exploreflask.com/en/latest/blueprints.html)
  * `repairkawap/api.py` defines the routes for the application apis. Several webpages are using ajax call to retrieve or
post values. Ideally this should be prefered to static page generation.
  * `repairkawap/auth.py` - code for handling authentication - code is fully generic and should not really be modified. Function requiring
authentication should take the decorator `@login_required`
  * `repairkawap/main.py` - main pages routes

Flask application initialization is defined in `repairkawapp/__init__.py` and is dynamically called when `flask` or `wsgi` load the module
through the `create_app` function.

## Continuous Integration

A workflow GitHub Actions (`.github/workflows/ci.yml`) exécute à chaque push ou PR sur `main` et `refactor` :

* Linting avec `ruff` (style + erreurs courantes)
* Vérification de format avec `black` (mode --check)
* (Optionnel) Typage basique avec `mypy` (non bloquant pour l'instant)
* Tests `pytest` avec rapport de couverture (artefact `coverage.xml`)
* Audit de dépendances (job séparé) via `pip-audit` et `safety`
* Smoke test d'import rapide (job speed-run) pour valider l'initialisation minimale

Pour corriger localement:
```
pip install -r requirements.txt ruff black mypy
ruff check .
black .
mypy repairkawapp
pytest -q
```

Prochaines améliorations possibles CI: publication badge de couverture (Codecov), workflow release taggé, build image Docker, matrice multi versions Python (3.10/3.11/3.12).


## RepairMonitor synchro (beta)

Une pré-synchronisation avec https://www.repairmonitor.org est en cours d'intégration. Pour permettre à l'application de se connecter automatiquement, ajoutez les clés suivantes dans `config.json` (et renseignez les valeurs réelles côté prod/dev) :

```
"REPAIR_MONITOR_USERNAME": "user@example.org",
"REPAIR_MONITOR_PASSWORD": "mot-de-passe",
"REPAIR_MONITOR_LANGUAGE": "fr"
```

Une fois les identifiants configurés, allez dans *Admin → Paramètres site* et utilisez le bloc « Synchronisation RepairMonitor » pour lancer une simulation (`/api/sync_repairmonitor`). L'endpoint se connecte à RepairMonitor avec les identifiants ci-dessus, vérifie l'accès au tableau de bord, puis liste les fiches clôturées prêtes à être exportées (limite paramétrable). La synchronisation complète (upload des fiches) arrivera dans une étape ultérieure.


## Templates
Pages templates are build by routes (essentially in `main.py`) and use jinja templating engine: see https://jinja.palletsprojects.com/en/3.1.x/templates/
for a full documentation. Templates are in `repairkawap/templates/` and are defining in cascade and blocks. All pages inherits from `base.html`- and some templates like
`log.html` are used for log tabs - and use themselves `log_template.html` defining jinja macros.

## Static Files and libraries

`repairkawapp/static` directory contains all css, javascript libraries and static images. The global html structure relies on bootstrap 5, and 3 main javascript libraries are used:

* `datatables`: display dynamic tables (https://datatables.net)
* `jquery`: https://jquery.com
* `daterangepicker`: selection of date range for statistics (https://www.daterangepicker.com)
* `d3`: data displaying (https://d3js.org)

# Production

Typical deployment on apache with a configuration like:

```
WSGIPythonPath /home/rco/repairkawapp/venv/lib/python3.7/site-packages/

<VirtualHost *:80>
    ServerName app.repaircafe-orsay.org

    WSGIDaemonProcess repairkawapp user=rco group=rco threads=5
    WSGIScriptAlias / /home/rco/repairkawapp/repairkawapp.wsgi

    <Directory /home/rco/repairkawapp>
        Require all granted
        WSGIProcessGroup therepairkawapp
        WSGIApplicationGroup %{GLOBAL}
    </Directory>
RewriteEngine on
RewriteCond %{SERVER_NAME} =app.repaircafe-orsay.org
RewriteRule ^ https://%{SERVER_NAME}%{REQUEST_URI} [END,NE,R=permanent]
</VirtualHost>
```

see online documentation:

* `WSGI` with nginx: https://www.digitalocean.com/community/tutorials/how-to-serve-flask-applications-with-uswgi-and-nginx-on-ubuntu-18-04
* `WSGI` with apache: https://www.bogotobogo.com/python/Flask/Python_Flask_HelloWorld_App_with_Apache_WSGI_Ubuntu14.php
