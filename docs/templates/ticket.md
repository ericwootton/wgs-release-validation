# Support ticket write-up template

Copy this to `docs/case-studies/CS-NN-short-name.md`. Use plain language for the customer-facing
reply. Technical language can be used for all text above it.

| Field | Value |
|---|---|
| Ticket ID | CS-NN |
| Date opened / closed | YYYY-MM-DD / YYYY-MM-DD |
| Severity | P1 (results wrong or blocked for many) · P2 (one customer blocked) · P3 (workaround exists) · P4 (question) |
| Customer | (fictional) |
| Reported symptom | "The customer's own words, quoted." |

## 1. Summary

Explain what happened and how we responded in 2 sentences which non-specialists could understand.

## 2. Impact

- Which samples, runs, or deliverables are affected?
- Does the content already provided contain any errors? If so, who needs to be notified and by when?

## 3. Timeline

| When | What |
|---|---|
| | Reported |
| | First response |
| | Root cause found |
| | Resolved / customer confirmed |

## 4. Investigation

Record commands in execution order and the evidence each produced (tables, read-level
evidence, igv-reports pages). Also record attempts which reached a dead end. This can
save time for the next person taking over.

## 5. Root cause

Describe this in 1 paragraph. Distinguish *what* failed from *why* the failure was possible.

## 6. Resolution

Work we completed for this customer (reruns, corrected files, and recommendations).

## 7. Prevention

Changes made to the code, checks, or documentation to prevent this incident from recurring, and links to the corresponding commits.

## 8. Customer-facing reply

> The message as it would be sent. Lead with the answer and explain it in plain language.
> State what we will do and by when, and what we cannot promise.
