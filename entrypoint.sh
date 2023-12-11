#!/bin/bash

export GUNICORN_APP=${GUNICORN_APP:-"connect.wsgi"}
export GUNICORN_CONF=${GUNICORN_CONF:-"${PROJECT_PATH}/gunicorn.conf.py"}

do_gosu(){
    user="$1"
    shift 1

    is_exec="false"
    if [ "$1" = "exec" ]; then
        is_exec="true"
        shift 1
    fi

    if [ "$(id -u)" = "0" ]; then
        if [ "${is_exec}" = "true" ]; then
            exec gosu "${user}" "$@"
        else
            gosu "${user}" "$@"
            return "$?"
        fi
    else
        if [ "${is_exec}" = "true" ]; then
            exec "$@"
        else
            eval '"$@"'
            return "$?"
        fi
    fi
}


if [[ "start" == "$1" ]]; then
    echo "Running collectstatic"
    do_gosu "${APP_USER}:${APP_GROUP}" python manage.py collectstatic --noinput
    echo "Starting server"
    do_gosu "${APP_USER}:${APP_GROUP}" exec gunicorn "${GUNICORN_APP}" --timeout 999999 -c "${GUNICORN_CONF}"   
fi
exec "$@"