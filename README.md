# repairkawapp
Application for Repair Café - initially developped for/by the Repair Café Orsay

# Installation

* create database
* copy `config-template.json` to `config.json` and adapt configuration
* create python virtual env and install requirements
* launch `init_db.py` to initialize the database - this can be done only once, for model upgrade, use `flask-alembic` (https://flask-alembic.readthedocs.io/en/latest/)

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
