import json


def add_classifier_to_flow(
    sample_flow: str, classifier_uuid: str, template_type: str,
    ticketer: dict = None, queue: dict = None,
):
    from connect.common.models import Project

    with open(sample_flow) as f:
        sample = f.read()

    sample_flow = json.loads(sample)

    if template_type == Project.TYPE_SUPPORT:
        ticketer_uuid = ticketer.get("uuid")
        ticketer_name = ticketer.get("name")

        queue_uuid = queue.get("uuid")
        queue_name = queue.get("name")

        classifier = sample_flow["flows"][1]["nodes"][2]["actions"][0]["classifier"]

        commercial_sector = sample_flow["flows"][2]
        administrative_sector = sample_flow["flows"][3]
        financial_sector = sample_flow["flows"][7]

        sectors = [commercial_sector, administrative_sector, financial_sector]

        for sector in sectors:
            ticketer_json = sector["nodes"][0]["actions"][0]["ticketer"]
            queue_json = sector["nodes"][0]["actions"][0]["topic"]

            # add ticketer to json
            ticketer_json["uuid"] = ticketer_uuid
            ticketer_json["name"] = ticketer_name

            # add queue to json
            queue_json["uuid"] = queue_uuid
            queue_json["name"] = queue_name

        classifier["uuid"] = classifier_uuid

    elif template_type == Project.TYPE_OMIE:
        classifiers = [
            sample_flow["flows"][5]["nodes"][6]["actions"][0]["classifier"],
            sample_flow["flows"][5]["nodes"][13]["actions"][0]["classifier"],
            sample_flow["flows"][10]["nodes"][3]["actions"][0]["classifier"]
        ]

        for classifier in classifiers:
            classifier["uuid"] = classifier_uuid

    elif template_type == Project.TYPE_LEAD_CAPTURE:
        classifier = sample_flow["flows"][3]["nodes"][0]["actions"][0]["classifier"]

        classifier["uuid"] = classifier_uuid

    return sample_flow
