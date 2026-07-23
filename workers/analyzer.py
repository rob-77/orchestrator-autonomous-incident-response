def analyzer(state):

    print("Analyzer running...")

    state.analysis_payload = {
        "incident": "Database outage",
        "severity": "High"
    }

    return state