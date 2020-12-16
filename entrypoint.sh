#!/bin/sh
cd $WORKDIR
python manage.py collectstatic --noinput

gunicorn connect.wsgi --timeout 999999 -c gunicorn.conf.py
