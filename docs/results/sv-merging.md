# Merging SV calls from two callers

Question: if a customer runs both pbsv and Sniffles on PacBio HiFi data, which way of combining
the two call sets gives the best SV calls, and is it better than either caller alone?

Every number here comes from [`sv-merge/metrics.md`](sv-merge/metrics.md), written by
`make sv-merge` from a real run. The data are the long-read module's calls (GIAB HG002, PacBio
HiFi Revio 48x, `chr20:1000001-6000000`), scored against the draft GIAB v5.0q benchmark with the
same `truvari bench` and `truvari refine` settings as the [hand-off](longread/QC_SUMMARY.md). The
region has 52 benchmark SVs, so a difference of one or two calls is within noise.

## What was compared

| Strategy | How it was made | Calls of 50 bp or more |
|---|---|---:|
| pbsv | pbsv alone, PASS calls | 46 |
| sniffles | Sniffles alone, PASS calls | 46 |
| union | both call sets concatenated, nothing removed | 92 |
| collapse | the union after `truvari collapse` with its defaults (500 bp, 95% size and sequence similarity) | 51 |
| collapse_loose | the same, but merging at the benchmark's own thresholds (2,000 bp, 70%) | 48 |
| intersect | pbsv calls that `truvari bench` matched to a Sniffles call | 42 |

## Results after refinement

| Strategy | Found | Missed | False | Precision | Recall | F1 |
|---|---:|---:|---:|---:|---:|---:|
| pbsv | 48 | 4 | 2 | 0.953 | 0.923 | 0.938 |
| sniffles | 47 | 5 | 4 | 0.909 | 0.904 | 0.906 |
| union | 48 | 4 | 33 | 0.621 | 0.923 | 0.742 |
| collapse | 47 | 5 | 6 | 0.875 | 0.904 | 0.889 |
| collapse_loose | 47 | 5 | 5 | 0.889 | 0.904 | 0.896 |
| intersect | 48 | 4 | 1 | 0.975 | 0.923 | 0.948 |

The numbers before refinement, and the record counts, are in
[`sv-merge/metrics.md`](sv-merge/metrics.md).

## What the results show

**A plain union is the worst option.** Most events are called by both tools, so the union holds
two records for them. The benchmark can match only one, and the second counts as a false call.
After refinement, recall is no higher than pbsv alone, because every event Sniffles found, pbsv
found too.

**Collapsing the union fixes most of that, but it still loses to pbsv alone.** With truvari's
defaults, collapse removed 41 calls as duplicates of 40 others. Some pairs that describe one event
in two ways were not similar enough to merge, and both stayed. At one SVA insertion near 4.03 Mb,
collapse kept the Sniffles record, which does not match the benchmark, so a true event became both
a missed and a false call. Merging at the benchmark's looser thresholds removed one more false call
and changed nothing else.

**Most of the false calls left after collapsing come from Sniffles.** Sniffles made four calls
the benchmark does not contain. Two are insertions near 1.60 Mb that pbsv did not call, supported
by 3 and 6 reads where Sniffles reports coverage of only 3 to 7 reads. One is its version of the
SVA insertion above. The fourth is an insertion in a tandem repeat at 1.77 Mb that pbsv also made.
A union-style merge keeps every call that either tool makes alone, so it keeps the first two.

**Requiring both callers to agree gave the best result.** The intersection removed one of pbsv's
two false calls and, after refinement, missed nothing that pbsv found. The false call it kept, an
insertion in a tandem repeat at 1.77 Mb, was made by both callers. Agreement between two callers
removes errors that only one of them makes, not errors they share.

## Recommendation

For this data type and benchmark, give customers pbsv's calls, and flag the calls Sniffles also
makes as higher confidence, instead of merging the two sets into one. That keeps pbsv's recall and
lets a customer who wants fewer false calls filter to the agreed set. A merged union should not be
the default delivery. If one is needed, collapse it and check it against the benchmark, because the
defaults did not merge every duplicate here.

## Limits

- 52 benchmark SVs in one 5 Mb region of one sample. The intersection's advantage over pbsv is a
  single false call. The case against a plain union does not depend on sample size, because it
  comes from how duplicates are scored.
- v5.0q is a draft benchmark. Before refinement, every strategy missed the same two 33 kb
  deletions and four events in tandem repeats, so combining these two callers does not help there.
- The intersection uses pbsv's representation of each event. A different base caller, or
  `truvari collapse --keep maxqual`, could change which version is kept.
- Only truvari was used for merging. SURVIVOR and Jasmine were not tested.

## Reproduce

```bash
make longread      # if not already run: calls, benchmark and hand-off
make sv-merge      # the six strategies above, about 6 minutes on 8 cores
```

The workflow is [`wdl/optional/sv_merge.wdl`](https://github.com/ericwootton/wgs-release-validation/blob/main/wdl/optional/sv_merge.wdl).
