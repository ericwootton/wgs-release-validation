# Incident report template

Do not assign blame to individuals. Describe systems and decisions. Copy this to `docs/incidents/INC-NN-short-name.md`.

| Field | Value |
|---|---|
| Incident ID | INC-NN |
| Date | YYYY-MM-DD |
| Status | Resolved / Monitoring |
| Severity | SEV1 (wrong results delivered) · SEV2 (release blocked) · SEV3 (caught before release) |
| Detected by | Automated check / customer / review |

## Summary

Explain what happened in 2 or 3 sentences.

## Impact

Who and what were affected, how long the effects lasted, and whether any results left the building.

## Timeline

| Time | Event |
|---|---|
| | Change made |
| | Detected |
| | Mitigated |
| | Resolved |

## Root cause

The technical cause, followed by the process failure which led to it going undetected.

## Detection

How did we detect it, and how much time had passed before we did? Would we have detected it without the check that fired?

## Resolution

Actions taken to restore a healthy state.

## Prevention

| Action | Owner | Status |
|---|---|---|
| | | |

## Lessons

What went well, what did not go well, and where we were fortunate.
