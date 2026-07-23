def actor(state):

    print("Actor running...")

    state.tool_calls = [
        "restart_database"
    ]

    return state