# Decision 0010 — Give the receipt question its own study contract

2026-09-08 UTC. Plan 0023 implementation authorized after the Plan 0022 PR merged.

The original functioning-transplant outcome combines receipt, health status and reporting.
The new question concerns recorded removal for deceased-donor transplant within 18 months
among the original listing group. Its five-component sum includes unknown post-transplant
status without assigning an unknown health outcome.

Use the [separate specification](../specs/deceased-donor-receipt-0023.md), configuration and
ignored `data/receipt-study/v1/` output. Independently bind source dates before modeling;
do not correct or overwrite original V2's ledger/results in place. Use the existing pinned
sources, two conditional evaluation origins and one fixed Ridge family without report count.
The source feasibility gate may restrict unverifiable sources before scores exist. Report
negative results and apply fixed continuation criteria without promoting a model.

This preserves original evidence and keeps the target change separate from the earlier
report-count and unknown-status investigations. It introduces no application or dependency
change and no new tracked analytical release.
