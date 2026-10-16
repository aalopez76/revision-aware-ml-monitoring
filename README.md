# When the Past Moves

**Revision-Aware ML Monitoring & Decision Reliability**

> **Status, stated first: nothing has been measured yet.** This document is the
> framing, written before the analysis exists. Every figure about these data is
> deliberately absent rather than estimated, and each one appears below as the
> gate that will produce it. Figures attributed to published work have been
> checked against the original text; see [`referencias.md`](referencias.md).

---

## 1. The operational problem

A deployed model is watched by a monitor. When the monitor fires, the standard
response is to retrain — and that assumes the alarm means the world changed. But
in surveillance, macroeconomic statistics, marketing attribution and accounting
closes, **the record of the past moves too**: values arrive late, get corrected,
and are restated weeks after the period they describe. On top of that, *who
reports* changes: in this series the number of hospitals submitting data varies
week to week, and a jump in admissions can come from more of them reporting.

So an apparent degradation has several readings that call for opposite responses,
and the cheapest wrong move is to retrain a model onto a restatement.

**The question:**

> When a model is evaluated against revisable records, how much does knowing the
> revision history and the reporting coverage change the maintenance
> recommendation — and under what cost conditions is intervening justified?

## 2. Headline result

**Not evaluated yet.** G2 produces it.

When it exists it will be stated as **N1, the discordance of recommendations**:
the share of scheduled national decision cuts at which the recommendation
changes once revision and coverage information are available, reported with its
numerator, its denominator, and the abstentions counted as a category rather than
dropped.

It will not be called "the value of information" — that names a specific
decision-theoretic quantity this is not — and a recommendation that changes under
a counterfactual will not be called a false alarm.

## 3. The figure

**Not produced yet.** G1 produces it.

One picture, and it is the point of the project: a forecast as it was originally
issued and never rewritten, the successive published versions of the outcome it
was scored against, and the reporting coverage of those weeks on its own axis.
No causal arrows: three series that moved, shown as three series that moved.

## 4. The system

Six small responsibilities, one batch process, no platform.

```
sources  ──►  as-of panel  ──►  forecast  ──►  monitor  ──►  decision  ──►  evidence
(two        (what was        (immutable,    (five        (recommend,    (manifest,
 channels)   knowable at      issued once)   typed         never        hashes, run
             a cut)                          signals)      deploy)      record)
```

Two doors and no others: [`src/revmon/sources.py`](src/revmon/sources.py) is the
only module that touches the network, and
[`src/revmon/panel.py`](src/revmon/panel.py) the only one that reads `data/`.
The project's central quantity is *what was knowable when*, so a second route to
the data would be a second definition of that quantity — which is how a
look-ahead gets in without anyone seeing it.

### The as-of contract

Every read is bounded by a decision cut, in one of three modes: `PUBLIC_REPLAY`
(only versions the source declared published before the cut), `OBSERVED_REPLAY`
(and that this system had actually fetched by then), and `LIVE`. Because the
source's publication date has day granularity and no verified hour, a public
replay places the cut a day after the declared publication rather than claiming
same-day visibility.

The gate refuses to invent: when the history needed for a cut is missing it
returns `INCOMPLETE_HISTORY`, and the monitor is allowed to `ABSTAIN`. It is
enforced in the data path and checked with generated histories rather than a
handful of examples — the invariant is universal, so the test is too.

## 5. The 2x2 and what it can say

Two information factors, crossed, with everything else identical at the same
cut: **R** (revision history available) and **C** (coverage indicators
available).

| | no C | with C |
|---|---|---|
| **no R** | `d_00` base | `d_01` |
| **with R** | `d_10` | `d_11` |

Crossed rather than chained, because a sequential ablation measures the
contribution of coverage *conditional on* having added revisions first, and that
number depends on the order. Crossing removes the order dependence and makes the
interaction observable — and if coverage only helps when revision history is
absent, the specialised monitor is redundant, which is a publishable finding.

**What it does not claim.** This is an ablation of *decision information*, not a
causal partition. Freezing an aggregate coverage figure does not reconstruct a
world in which the same hospitals reported; aggregate data cannot say which
facilities stopped reporting or how many admissions they would have contributed.
Discordance is a non-additive functional of the four arms, so the two interaction
contrasts need not coincide and neither is a linear interaction term. Both are
reported, as descriptives.

**Results: not evaluated yet.**

## 6. Consequences and the cost frontier

**Conditional on G2, and not promised.** If — and only if — the discordance has
enough support to be worth it, four maintenance policies are simulated as
complete trajectories from the same initial state: never retrain, periodic,
reactive to mature error, and revision-and-coverage aware. Retraining changes the
model, and the model changes later predictions, errors and alarms, so applying
one alarm vector to four policies would invalidate the comparison.

The output is a **region of costs**, not a number:
`L_p(c) = e_p + c·r_p`, with `c` in units of predictive loss per period — not
money and not health. A single break-even `c*` is reported only where the
crossing is positive and stable, and never as "dollars saved".

## 7. The decision this would support

A section, not a casebook, and labelled as a proposal: the monitor shows
degradation while the evaluated records were revised and coverage moved. Four
functional perspectives — data steward, data scientist, model owner, operations —
weigh continuing, waiting for maturity, investigating the data, or evaluating a
candidate. **No meetings happened, nobody approved anything, and no
organisation adopted this.** The scenario is anchored in a run the pilot actually
executed, and the parts that are proposals say so.

## 8. Where it fails

Written with the results, and already known to belong here: the delay maturity
introduces between a week ending and the first moment its label can be scored;
the dependence between consecutive weeks and across states, which means the row
count is not the effective sample size; periods with no eligible label at all;
and the share of comparable periods in which the specialised policy decides
*worse* than the simple one, with its denominator and its magnitude rather than
only its frequency.

## 9. Reproduce

```bash
uv sync --locked --extra dev        # builds .venv from the committed uv.lock

uv run ruff check .
uv run pytest
uv run python scripts/verify_results.py
uv run python scripts/weekly_capture.py   # one capture; leaves a dated record
```

Everything runs inside `.venv`, built from the committed `uv.lock`. CI, the
scheduled job and the container all install with `--locked`/`--frozen`, so drift
between the lockfile and `pyproject.toml` fails the build rather than quietly
resolving a different set of versions: a figure produced under other versions is
not the same figure.

**External access.** The Delphi V5 channel reads its key from
`DELPHI_EPIDATA_KEY`. Anonymous access is capped at 60 requests per hour and
allows multiple selections on at most two parameters; a free key lifts both. The
hub channel needs no credentials. Source archives are not redistributed here, so
the capture step comes first.

*Processing is Python over flat files, so there are no SQL queries, entity
relationship diagram or interactive dashboard to show. Development was carried
out with AI assistance (Claude Code); every figure cited was produced by the
scripts in this repository, and every published claim was verified against its
primary source.*

---

## 10. Data, and what the sources actually guarantee

**Delphi Epidata V5, `source="nhsn"`** is the candidate canonical channel.
Target `confirmed_admissions_flu_ew` (CDC field `totalconfflunewadm`), weekly,
week ending Saturday. Coverage comes from the `hosprep_*` family:
`hosprep_confirmed_admissions_flu_ew` is *"Number of acute care hospitals
reporting influenza admissions"* — a facility count, not an admissions count.
`/archive/` carries version history, `/snapshot/` reconstructs a past state, and
`/metadata/report_times/` lists the source's publication calendar. Access goes
through `epidatpy`, Delphi's own client, because the V3/V4 methods are being
deprecated as of October 2026 and reimplementing the wire protocol would buy
nothing.

**The FluSight hub's git history** is a second, independent reconstruction of
what was published when. A commit is evidence of what the hub put in its own
repository; it is **not** the instant a value became available from NHSN, and not
an independent epidemiological measurement. The two are compared, never fused.

Three things recorded now rather than discovered later:

* **Data coverage is not version coverage.** The signal's `reference_time`
  coverage starts 2020-08-08. That says nothing about how far back the
  `report_time` history reaches, and the documentation does not say. Measuring it
  is G0's first question — confusing the two is precisely the error this project
  studies.
* **An open contradiction about `/archive/`.** Delphi's V5 overview describes its
  rows as diffs — *"Each row represents a 'diff' (when the value for a specific
  key changed)"* — while the installed client's docstring says *"Every version of
  each value is returned, one row per report_time"*. The difference **is** the
  denominator of the revision rate: if unchanged republications are omitted,
  dividing by the returned rows inflates it. Settled in G0 against `/snapshot/`,
  not by assumption.
* **A reporting-regime change sits inside the history.** Hospital reporting was
  mandatory to 2024-04-30, **voluntary from 2024-05-01 to 2024-10-31** — a period
  CDC flags as possibly not fully representative — and mandatory again from
  2024-11-01 under a CMS requirement. A regime change moves coverage without
  moving the phenomenon, so the eligible universe is **declared before looking at
  results**: from the resumed mandate, and preferably by measured coverage rather
  than a calendar cut.

**Maturity is declared, not inherited.** An earlier version of this project
carried `MATURITY_DAYS = 45`, taken from Delphi's documented behaviour on a
different series; it has been removed, because it had started to read as a
property of this target. A maturity policy is supplied explicitly, says where it
was declared, and is reported against the pre-declared grid of 45/60/90 days.
Delphi documents that roughly 20% of values in the preceding two months are
revised, with a median difference near 2% — used here as a **control on the
reconstruction**, not as a result of it.

## 11. Build order, and the gate

| Gate | Produces | Publishable on its own |
|---|---|---|
| **G0** | Measured source windows, `archive`→`snapshot` reconstruction, cross-channel discrepancy table | Yes — what a public surveillance archive does and does not contain |
| **G1** | One real run end to end, and the figure | Yes |
| **G2** | **The gate.** N1 and the 2x2, with uncertainty and limits | Yes, and it is the core |
| **G3** | Policy trajectories and the cost region — **only if G2 supports it** | Yes |

If G2 finds the discordance small, the support insufficient or the missing
periods dominant, that is the result: the project publishes why specialising is
not justified and closes short. **No configuration is searched until something
fires, and the scope is not widened to rescue a negative gate.**

The method is frozen before the confirmatory cohort is scored, and the freeze
needs two bounds: an external value embedded in the act gives a lower bound,
while an RFC 3161 timestamp or a *completed* OpenTimestamps proof gives the upper
one. A commit date of our own is not evidence — the committer date is an
environment variable.

## 12. Scope & caveats

**Declared now, because these are scope decisions rather than results.**

* **No platform layer.** No Kubernetes, Databricks, orchestrator, feature store
  or managed cloud ML. Scoring is a batch job in a container, scheduled by GitHub
  Actions. The mapping to a managed platform is described, not built: a shallow
  version of the other half would demonstrate less than saying where the line is.
* **No model-lifecycle machinery.** No registry, promotion gate, automated
  rollback or incident subsystem. A retraining policy needs a function that
  refits and a manifest.
* **No causal attribution.** Revision, coverage and genuine change are not three
  exclusive causes identifiable from aggregate data.
* **One national decision per week.** Fifty states are not fifty replicates of a
  decision about one national model, so state rows characterise the data and do
  not enter N1's denominator. The support will be small and is reported as such.
* **Forecast accuracy is not the headline.** The hub already runs that
  competition — it scores quantile forecasts with relative WIS over 23 quantiles,
  which is why this prototype, which emits point forecasts, does not borrow that
  rule for prestige. No forecast is submitted and no advantage is claimed.
* **A declared cost is not an observed one**, and `c` excludes the cost of
  investigating, of waiting, and of everything this loss function does not model.
* **One season, one disease, one country.** The procedure transfers; the
  magnitudes do not. The closest executed antecedent (Agyekum and Obese, 2026)
  finds real-time versus revised accuracy differences *"small and … 
  indistinguishable under Diebold-Mariano tests"*, so the expectation here is
  modest and written down before measuring.
* **Not clinical.** Public data, a hypothetical organisation, no CDC endorsement,
  no patient or public-health decision.

### Three things this project will say out loud

* The extra information changed this recommendation — **and that alone does not
  mean it improved it.**
* Aggregate coverage movements were **not** read as admissions caused by
  hospitals that stopped reporting; those per-facility data are not held.
* A recommendation to retrain is **not** an automatic update of a production
  system: the consequences were compared in a validated replay, with no claimed
  approvals and no deployment.

## 13. Primary sources

Verified by opening the source; see [`referencias.md`](referencias.md) for the
full list, the works consulted and not used, and the corrections that this
verification produced — which are recorded, not deleted.
