class AgentState(BaseModel):

    raw_input: str

    incident_id: str | None = None

    incident_type: str | None = None

    severity: str | None = None

    diagnosis: dict = {}

    tool_calls: list = []

    validated: bool = False

    report: str = ""

    round_number: int = 0

    error_log: list = []

    messages: list = []

    telemetry: dict = {}