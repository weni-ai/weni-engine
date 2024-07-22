def ignore_msgs(event, hint):
    logger_name = event.get("logger")
    if logger_name == "elasticapm.transport":
        return None
    return event
