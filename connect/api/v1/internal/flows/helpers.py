import json

def add_classifier_to_flow(sample_flow, classifier_uuid):
    with open(sample_flow) as f:
            sample = f.read()

    sample_flow = json.loads(sample)

    for actions in sample_flow["flows"][0].get("nodes"):
        if len(actions["actions"]) > 0:
            if "classifier" in actions["actions"][0].keys():
                classifier = actions["actions"][0].get("classifier")
                classifier["uuid"] = classifier_uuid
                print(classifier)
    return sample_flow





