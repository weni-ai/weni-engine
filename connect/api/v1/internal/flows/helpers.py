import json


def add_classifier_to_flow(sample_flow, classifier_uuid):
    with open(sample_flow) as f:
        sample = f.read()

    sample_flow = json.loads(sample)
    classifier = sample_flow["flows"][3]["nodes"][0]["actions"][0]["classifier"]
    classifier["uuid"] = classifier_uuid

    return sample_flow
