#!/bin/bash

export GUNICORN_APP=${GUNICORN_APP:-"connect.wsgi"}
export GUNICORN_CONF=${GUNICORN_CONF:-"${PROJECT_PATH}/gunicorn.conf.py"}
export LOG_LEVEL=${LOG_LEVEL:-"INFO"}
export CELERY_APP=${CELERY_APP:-"connect"}
export CELERY_MAX_WORKERS=${CELERY_MAX_WORKERS:-'6'}
export CELERY_BEAT_DATABASE_FILE=${CELERY_BEAT_DATABASE_FILE:-'/tmp/celery_beat_database'}
export HEALTHCHECK_TIMEOUT=${HEALTHCHECK_TIMEOUT:-"10"}

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
    do_gosu "${APP_USER}:${APP_GROUP}" exec gunicorn "${GUNICORN_APP}" -c "${GUNICORN_CONF}"   
elif [[ "celery-worker" == "$1" ]]; then
    celery_queue="celery"
    if [ "${2}" ] ; then
        celery_queue="${2}"
    fi
    do_gosu "${APP_USER}:${APP_GROUP}" exec celery \
        -A "${CELERY_APP}" --workdir="${PROJECT_PATH}" worker \
        -Q "${celery_queue}" \
        -O fair \
        -l "${LOG_LEVEL}" \
        --autoscale=${CELERY_MAX_WORKERS},1
elif [[ "celery-beat" == "$1" ]]; then
    do_gosu "${APP_USER}:${APP_GROUP}" exec celery \
        -A "${CELERY_APP}" --workdir="${PROJECT_PATH}" beat \
        --loglevel="${LOG_LEVEL}" \
        -s "${CELERY_BEAT_DATABASE_FILE}"
elif [[ "healthcheck-celery-worker" == "$1" ]]; then
    celery_queue="celery"
    if [ "${2}" ] ; then
        celery_queue="${2}"
    fi
    HEALTHCHECK_OUT=$(
        do_gosu "${APP_USER}:${APP_GROUP}" celery -A "${CELERY_APP}" \
            inspect ping \
            -d "${celery_queue}@${HOSTNAME}" \
            --timeout "${HEALTHCHECK_TIMEOUT}" 2>&1
    )
    echo "${HEALTHCHECK_OUT}"
    grep -F -qs "${celery_queue}@${HOSTNAME}: OK" <<< "${HEALTHCHECK_OUT}" || exit 1
    exit 0
fi
exec "$@"