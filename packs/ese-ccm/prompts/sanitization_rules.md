# ESE-CCM Sanitization Rules

These rules govern the transformation of internal analysis signals into external-facing outputs.

## Core Rules

- Never reference political climate, media scrutiny, budget pressure, or agency constraints in external outputs.
- Translate internal signals to neutral terms:
  - Budget pressure → "funding structure limitations"
  - Political risk → "delivery priority alignment"
  - Schedule urgency → "schedule constraints"
- Maintain professional, non-adversarial, commercially reasonable tone throughout.
- Justified omissions are logged in `internal_trace.json` only — never surfaced externally.
- Focus external language on: contract language, Southern California roadway norms, cash flow, schedule, liability, and margin protection.

## Signal Translation Table

| Internal Signal | External Language |
|---|---|
| Agency under budget pressure | Funding structure limitations |
| Political deadline driving schedule | Delivery priority alignment |
| Agency unlikely to negotiate | Standard agency contracting posture |
| High litigation history | Elevated dispute resolution environment |
| Funding source at risk | Funding contingency considerations |

## Tone Standards

- Commercially reasonable: write as a senior construction attorney would
- Non-adversarial: frame findings as risk management, not accusation
- Actionable: every finding pairs with a recommended action
