# Architecture

Coordinator
- Controls graph execution
- Routes between workers
- Prevents infinite loops

Analyzer
- Extracts structured incident information

Actor
- Maps validated actions to mocked tools

Validator
- Detects malformed outputs
- Rejects invalid actions

Reporter
- Produces the final incident report

Global Middleware
- Redacts sensitive telemetry
- Manages conversation context to reduce token usage