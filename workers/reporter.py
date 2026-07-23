def reporter(state):

    print("Reporter running...")

    state.report = (
        "Database restarted successfully. Incident closed."
    )

    return state
