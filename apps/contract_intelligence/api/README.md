# API Boundary

This directory now contains the first thin product API for the
contract-intelligence lifecycle.

Current responsibilities:

- trigger local bid-review runs
- commit reviewed packages into committed-contract state
- trigger monitoring runs from the committed obligation baseline
- retrieve latest project, run, commit, obligation, monitoring, and alert state
- reject missing or non-directory project paths before orchestration runs
- validate optional input files before commit and monitoring actions
- keep interactive docs disabled by default unless explicitly enabled through environment configuration

Near-term expansion:

- project and document upload endpoints
- human-review actions
- richer filtering over findings, obligations, and alerts
