# v0.7 — pre-change v0.6 audit

Frozen replay: 120/120 identical verification decisions. No external calls.

26/40 = 11 correct answers + 15 correct refusals. 25 answerable = 11 correct + 13 false refusals + 1 literal reference mismatch. CAR 15/15; FAR 13/25. No denominator bug found; strict literal judge limitation retained.

| Case | Refusal | Root cause |
|---|---|---|
| exact-05 | semantic_support_not_established | Mock window ends at «Срок» before value; chunk has full value. Citation selection/window error, not retrieval. |
| multi-hop-01 | incomplete_multi_hop | Mock returns one citation although both source pages are retrieved. Verifier correctly rejects incomplete multi-hop. |
| multi-hop-02 | incomplete_multi_hop | Mock returns one citation although both source pages are retrieved. Verifier correctly rejects incomplete multi-hop. |
| multi-hop-03 | incomplete_multi_hop | Mock returns one citation although both source pages are retrieved. Verifier correctly rejects incomplete multi-hop. |
| multi-hop-04 | incomplete_multi_hop | Mock returns one citation although both source pages are retrieved. Verifier correctly rejects incomplete multi-hop. |
| multi-hop-05 | incomplete_multi_hop | Mock returns one citation although both source pages are retrieved. Verifier correctly rejects incomplete multi-hop. |
| paraphrased-01 | semantic_support_not_established | Mock chooses postmortem/40-minute scenario instead of RPO; relevant source rank 1. No semantic intent mapping. |
| paraphrased-02 | semantic_support_not_established | Mock chooses outage scenario rather than P1 reaction value; source rank 1. Requires condition-to-severity relation. |
| paraphrased-04 | semantic_support_not_established | Mock chooses document identifier instead of project identifier; source rank 1. Entity/field confusion. |
| paraphrased-06 | no_evidence | No lexical synonym records kept→Retention; mock hash vectors not semantic. Relevant source absent from top 5. |
| paraphrased-08 | no_evidence | No lexical synonym restoration→Recovery; relevant source absent from top 5. |
| paraphrased-09 | semantic_support_not_established | Recovery ranked above Backup; Mock picks Recovery. Relevant Backup rank 2; key completeness fails correctly. |
| paraphrased-10 | no_evidence | No lexical synonym stored activity→Logging; relevant source absent from top 5. |

## Implementation plan

Separate structured fact semantics and sufficiency from citation existence; bounded query refinement with permission/version checks; extractive repair using only validated source spans; frozen v1 comparison plus disjoint calibration/holdout fixtures; persist diagnostics in existing JSON histories; extend localized dashboard and run all regression checks.

Retrieval baseline remains primary-pass metrics; re-retrieval success is measured separately. Keep literal reference scoring unchanged for comparable v1 results.