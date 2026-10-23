# Incident report template

Blameless: describe systems and decisions, not people. Copy to `docs/incidents/INC-NN-short-name.md`.

| Field | Value |
|---|---|
| Incident ID | INC-NN |
| Date | YYYY-MM-DD |
| Status | Resolved / Monitoring |
| Severity | SEV1 (wrong results delivered) · SEV2 (release blocked) · SEV3 (caught before release) |
| Detected by | Automated check / customer / review |

## Summary

What happened, in two or three sentences.

## Impact

Who and what was affected, for how long, and whether any results left the building.

## Timeline

| Time | Event |
|---|---|
| | Change made |
| | Detected |
| | Mitigated |
| | Resolved |

## Root cause

The technical cause, then the process gap that let it through.

## Detection

How it was noticed, and how long that took. Would we have noticed without the check that fired?

## Resolution

What was done to restore a good state.

## Prevention

| Action | Owner | Status |
|---|---|---|
| | | |

## Lessons

What went well, what did not, where we got lucky.
