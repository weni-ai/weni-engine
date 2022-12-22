import json


def add_classifier_to_flow(sample_flow: str, classifier_uuid: str, ticketer_uuid: str = None):
    with open(sample_flow) as f:
        sample = f.read()

    sample_flow = json.loads(sample)

    if ticketer_uuid:
        classifier = sample_flow["flows"][1]["nodes"][2]["actions"][0]["classifier"]
        ticketer = sample_flow["flows"][2]["nodes"][0]["actions"][0]["ticketer"]
        ticketer["uuid"] = ticketer_uuid

    else:
        classifier = sample_flow["flows"][3]["nodes"][0]["actions"][0]["classifier"]

    classifier["uuid"] = classifier_uuid

    return sample_flow
