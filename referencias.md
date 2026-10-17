# References

Works reviewed during this project, with their exact reference and what each one
contributed. Works that **support a method decision** are listed separately from
those consulted and not used.

A reference carries ✓ only when the source itself was opened and its authors,
year, title and the claim attributed to it were confirmed against the original
text. All ✓ entries below were verified on **14 October 2026**. Entries without
✓ were found but not opened, and **nothing in any deliverable rests on them.**

---

## 1. The data

**Centers for Disease Control and Prevention.** *FluSight Forecast Hub,
2026–2027 season.* GitHub: [`cdcepi/FluSight-forecast-hub`](https://github.com/cdcepi/FluSight-forecast-hub).
MIT licence. ✓

> The target series and its revision history. The primary target is
> `wk inc flu hosp`, weekly laboratory-confirmed influenza hospital admissions
> from NHSN, over horizons −1 to 3. The challenge runs **7 October 2026 to
> 26 May 2027**.
>
> **Why this project uses it:** `target-data/target-hospital-admissions.csv` is
> committed weekly, so the repository's git history is a vintage archive, and
> the revision triangle is reconstructible with `git log` rather than an as-of
> API. One commit is titled *"Fixed duplicates in time series"* — a dated
> correction with its reason in the message.
>
> Two of its documented rules draw the distinction this project measures:
> *"rate-trend targets are scored using finalized data"*, and *"horizon −1
> targets are excluded from summary evaluations"*.
>
> Users of the hub's forecasts are asked to contact `flusight@cdc.gov` about
> attribution of the source forecasts.

**Delphi Research Group, Carnegie Mellon University.** *Delphi Epidata API.*
[cmu-delphi.github.io/delphi-epidata](https://cmu-delphi.github.io/delphi-epidata/) ✓

> Revision metadata as columns: `release_date`, `issue` and `lag` accompany each
> value. Its FluView documentation states that *"participating providers may
> report data late, or correct previously reported data"* and that the `issues`
> and `lag` parameters *"allow you to access historical versions of the data as
> they were reported on specific dates"*. Its Doctor Visits documentation gives
> the pattern explicitly: a value for one date may first appear days later and
> be revised again after that, while values more than 45 days past are expected
> to remain fairly static.
>
> **Limitation, recorded rather than discovered later:** FluView is served by
> the legacy V3 API; Delphi recommends V5 (`fluview_ilinet`) for new work, and
> dates the V3/V4 client deprecations to October 2026. The `epidatpy` client is
> at version **0.7.0**, and Delphi's own documentation describes a full-featured
> Python client as *still in development*, which is why this project calls the
> REST endpoint directly.

---

## 2. The decision: when to retrain

**Regol, F., Schwinn, L., Sprague, K., Coates, M. and Markovich, T.** (2025).
*When to retrain a machine learning model.* In **Proceedings of the 42nd
International Conference on Machine Learning**, PMLR 267:51369–51404.
arXiv: [2505.14903](https://arxiv.org/abs/2505.14903) (20 May 2025) ✓

> **The project's method anchor, and the only peer-reviewed work here that
> addresses the decision directly.** Its claim, in the authors' words:
> *"Distribution shift detection falls short as it cannot account for the cost
> trade-off."* It proposes *"an uncertainty-based method that makes decisions by
> continually forecasting the evolution of model performance"*, and reports that
> it *"consistently outperforms existing baselines on 7 datasets"*, on
> classification tasks.
>
> This is why phase F compares policies by realised value under a declared cost
> rather than by whether they detect shift.

**Dasari, S.** (2026). *When to Retrain: An Empirical Study of Retraining
Policies for Streaming ML Under Concept Drift, Budget, and Latency Constraints.*
arXiv: [2608.19488](https://arxiv.org/abs/2608.19488) (19 August 2026) ✓

> Compares periodic retraining, error-threshold triggering, drift-triggered
> retraining (ADWIN) and a no-retrain baseline, *"under a unified system model
> that makes retraining budgets and training-plus-deployment latency explicit"*,
> across three budget levels and up to five latency levels.
>
> Its finding is **conditional, and the condition matters**: *"simple periodic
> retraining significantly outperforms both reactive policies under abrupt and
> gradual drift, while reactive policies retain an advantage only under
> recurring drift."* Its headline is something else again — that the dominant
> design choice *is not the retraining policy but whether the deployed model
> learns incrementally*. With per-sample incremental updates, for the linear
> online learner studied, *"no policy differs from the no-retrain baseline by a
> practically significant margin in any of 54 paired comparisons"*; without
> them, *"policy choice separates outcomes by 15-55 percentage points of
> post-drift accuracy."*
>
> **Single-author preprint with no venue.** It supplies the policy set phase F
> compares, and its conditionality is carried into how that phase is reported.

---

## 3. Drift detection and false alarms

**Singh, R. S.** (2026). *When Drift Detectors cry Wolf: False Alarm Rates in
continuous ML Monitoring.* arXiv: [2607.17336](https://arxiv.org/abs/2607.17336)
(19 July 2026) ✓

> Compares false-positive behaviour of PSI, KS, MMD, LSDD and adversarial
> validation under continuous monitoring. PSI *"produc[es] frequent false alarms
> at small sample sizes"* and *"stabilizes and improves substantially once batch
> sizes exceed approximately 200 samples"*; KS, MMD and LSDD show *"persistent
> fluctuations across batch sizes"* but are *"comparatively more reliable than
> PSI in low-data regimes"*. Bonferroni correction lowers false positives
> *"often at the cost of reduced true positive sensitivity"*.
>
> **The reason phase D controls the alarm rate before interpreting any alarm:**
> a detector run continuously is a sequential multiple-testing problem, and the
> stability–sensitivity trade-off is explicit in this paper's abstract. It
> reports no specific false-positive rates there. Single-author preprint.

**Cerqueira, V., Gomes, H. M., Heyden, M., Pfahringer, B. and Bifet, A.** (2026).
*A Framework for Evaluating and Benchmarking Concept Drift Detection Methods.*
Accepted at **KDD '26**. arXiv: [2606.07789](https://arxiv.org/abs/2606.07789)
(5 June 2026) ✓

> *"We benchmark 14 widely used drift detection methods on 7 real-world datasets
> across 4 drift types."* Its protocol uses *"a drift simulation method that
> injects controlled distributional changes into real-world datasets via Monte
> Carlo trials, enabling supervised evaluation"*, and *"all code and experiments
> are publicly available."*
>
> **Peer-reviewed, and the right source for the detector set and the detection
> metrics.** Its injection step is what this project does not need to do:
> revisions here are already dated by the source. That is a difference in
> setting, stated as such — **the paper does not claim that real drift points
> are unknown, and no such claim is attributed to it.** See the note at the end
> of this file.

---

## 4. Data revisions and real-time evaluation

**Agyekum, L. and Obese, O.** (2026). *Forecasting in the Fog: Real-Time versus
Revised-Data Evidence on Machine Learning's Edge over the Phillips Curve.*
arXiv: [2608.09033](https://arxiv.org/abs/2608.09033) (10 August 2026, stat.AP) ✓

> **The closest executed antecedent, and it sets this project's expectation.**
> It asks *"whether the ML advantage over the Phillips curve documented in
> Agyekum (2026) survives when models are trained and evaluated on real-time
> (ALFRED) vintages rather than revised series"*, building vintage-consistent
> panels for four traditional and four ML models.
>
> **Its aggregate answer is negative-to-null:** *"Real-time/revised accuracy
> differences are small and, apart from one exception at 6 months … 
> indistinguishable under Diebold-Mariano tests"* — the exception being Gradient
> Boosting against the Phillips curve at 6 months, p = 0.097.
>
> **But the effect it did find is the one this project pursues:** the Random
> Forest's reliance on PCE inflation under revised data is *"substantially a
> hindsight artifact"*, since real-time data shifts its importance toward
> current CPI. Same accuracy, different learned structure. That is the
> hypothesis phase E transfers to a series with larger and faster backfill.

**Kuang, Y. (Kyle).** (2026). *Revision Risk in Real-Time Macroeconomic
Forecasting.* arXiv: [2607.05882](https://arxiv.org/abs/2607.05882)
(v1 7 July 2026, v2 26 July 2026) ✓

> Treats later-outcome uncertainty as **partially identified** when only the
> marginal histories of early errors and revisions are known, and derives *"a
> sharp Frechet-Makarov set"*. It reports that *"first-release to roughly
> 180-day revisions account for 8.3 percent of later-outcome MSE across
> real-activity targets, versus 3.6 percent across inflation targets"* on SPF
> data.
>
> **What it does not say, and was wrongly attributed to it during this project's
> framing:** it makes no claim that the choice of outcome vintage changes
> forecast *rankings*. Its claim concerns uncertainty statements — a vintage
> choice *"is not the same uncertainty statement"*. It does not mention the Bank
> of England's Forecast Evaluation Report. Both errors are recorded in the note
> below. The paper is cited here for the partial-identification framing only.
> Single-author preprint.

**Carriero, A., Pettenuzzo, D. and Shekhar, S.** (2026). *MACROCAST: A
Vintage-Consistent Time Series Foundation Model for Real-Time Macroeconomic
Forecasting.* arXiv: [2606.28670](https://arxiv.org/abs/2606.28670)
(27 June 2026) ✓

> *"A lightweight Time Series Foundation Model (TSFM) for real-time
> macroeconomic forecasting"*, fine-tuned on *"vintage-specific ALFRED data"*,
> with *"fine-tuning us[ing] only real-time vintages"*, evaluated on FRED-MD *"in
> a genuine real-time out-of-sample exercise"*.
>
> Cited as evidence that vintage-consistent training is current practice rather
> than this project's invention. **Not implemented here:** a foundation model is
> outside this project's scope and would not answer its question.

**Ahmad, T.** (2026). *Time-Series Foundation Models That Understand Data
Revisions.* arXiv: [2609.28576](https://arxiv.org/abs/2609.28576)
(23 September 2026) ✓

> Proposes *"VINTAGE-TS, a revision-aware adaptation of a time-series foundation
> model"* that *"distinguishes observation time from information-availability
> time"*, motivated by the observation that *"forecasting from a contemporary
> download can therefore expose a model to information unavailable"* at the
> prediction date.
>
> **Cited for the vocabulary and the clock distinction, not for a result.** The
> paper states that *"Real ALFRED and Chronos-2 experiments have not been
> executed"* — only a synthetic demonstration and a 25-configuration sensitivity
> suite — and that *"no empirical foundation-model advantage is claimed"*. It is
> a protocol. Single-author preprint.

---

## 5. Consulted, not verified — and therefore not used

Found during the literature search, **not opened**, and no deliverable rests on
any of them. Listed so that the search is reproducible and so that none is
quietly promoted later without being checked.

- arXiv 2510.25573 — CUSUM monitoring of the calibration of predicted probabilities.
- arXiv 2505.04608 — WATCH: adaptive monitoring via weighted-conformal martingales.
- arXiv 2512.23602 — distribution-free process monitoring with conformal prediction.
- arXiv 2601.00908 — conformal prediction under distribution shift, COVID-19 natural experiment.
- arXiv 2606.20216 — learner-based concept drift detection.

## 6. Ruled out, with the reason named

| Work | Reason |
|---|---|
| **Sudijono et al. (Netflix), programme-level experiment optimisation** | **Does not answer the question.** Optimises which experiments to run, not whether an alarm is real |
| **MACROCAST / VINTAGE-TS as implementations** | **Out of scope.** Foundation models are a different question; both are cited for framing |
| **Entering the FluSight competition** | **Out of scope.** The hub's 28–32 groups are used as a reference field; this project submits no forecast and claims no forecasting advantage |
| **Feature stores, Kubernetes, managed cloud ML** | **Declared boundary.** See the README's "Outside Scope" — stated, not omitted |

---

## A note on the use of these references

Every figure attributed to published work here was checked against the original
text rather than against a search summary. **That check corrected three claims
and one number that had already been written into this project's framing:**

1. Kuang was credited with showing that the choice of outcome vintage changes
   forecast rankings. **The paper makes no such claim**; it concerns uncertainty
   statements and partial identification. The project's question was reframed
   accordingly, away from ranking change and toward what the model learns.
2. Kuang's revision share was quoted as 8.2 percent. **It is 8.3 percent**, and
   it is attributed to SPF data rather than specifically to median forecasts.
3. Kuang was said to use the Bank of England's Forecast Evaluation Report as a
   motivating example. **It is not mentioned in the paper.**
4. Cerqueira and co-authors were quoted as stating that drift points are
   typically unknown in real-world data. **That sentence is not in the abstract**;
   the stated purpose of their injection step is *"enabling supervised
   evaluation"*. An argument built on the misquotation was withdrawn.

Of the nine verified entries, **two are peer-reviewed** (Regol et al. at ICML
2025; Cerqueira et al. at KDD '26), one has established authors in its field
(Carriero, Pettenuzzo and Shekhar), and **four are single-author preprints with
no venue** (Kuang, Dasari, Singh, Ahmad). The project's method decisions rest on
the first group; the preprints supply vocabulary, policy sets and expectations,
and are labelled as such wherever they are used.

### Corrections of 15 October 2026

The same check, run again when the project was re-scoped, corrected two more
claims. **They are recorded, not edited away**, for the same reason as the first
four: the record of the correction is worth more than the claim it corrected.

5. The Delphi entry above states that *"Delphi's own documentation describes a
   full-featured Python client as still in development, which is why this project
   calls the REST endpoint directly"*. **That is now out of date.** `epidatpy`'s
   own README presents V5 as current, says *"New code should use the current V5
   methods"*, carries no in-development banner, and documents
   `epidata_snapshot()`, `epidata_archive()` and `epidata_meta()`. The project
   therefore uses the official client instead of hand-rolling the protocol. Two
   details were measured rather than read: in the released **0.7.0** those
   methods are **methods of `EpiDataContext`**, not module-level exports — a
   first check of the module namespace wrongly concluded they were absent — and
   the V3/V4 methods *"are being deprecated as of October 2026, and calling them
   now emits a warning"*, which is why the ILINet/FluView path was retired rather
   than merely left unused.

6. **A contradiction in the primary documentation, now settled by measurement.**
   Delphi's V5 overview page describes `/archive/` rows as change records — *"Each
   row represents a 'diff' (when the value for a specific key changed)"* — while
   the installed client's docstring for `epidata_archive` says *"Every version of
   each value is returned, one row per report_time"*. Both are primary
   documentation and they disagree.

   **G0 measured it on 16 October 2026 and neither reading is right.** With both
   axes bounded to 2025-09-01 … 2026-10-10, 100 of the 102 publications in that
   window carried a row for `confirmed_admissions_flu_ew`, and a given event week
   appeared in 17 of them at the median (minimum 2, maximum 41). Unchanged
   republications are therefore kept — against the diffs reading — and keys are
   absent from most publications — against the every-version reading. Each
   release restates a trailing window of weeks. Reconstructing a snapshot from
   the archive reproduced the direct `/snapshot/` exactly at three test cuts.

   The claim is recorded here rather than replaced because **this is the whole
   point of the rule that "verified in documentation" and "measured in data" are
   different states**: two primary sources agreed with each other less than
   either agreed with the data, and only a query could tell.

---

## 7. Architecture, operations and tooling sources

Consulted for the re-scoping and checked by opening each page on the dates given.
These support **design decisions**, not empirical claims, and none of them
certifies that this pilot works, complies with anything, or runs at scale.

**Delphi Epidata V5 — API overview, queries, metadata and keys.** ✓ 15 Oct 2026
[v5](https://cmu-delphi.github.io/delphi-epidata/api/v5.html) ·
[queries](https://cmu-delphi.github.io/delphi-epidata/api/v5_api_queries.html) ·
[NHSN signals](https://cmu-delphi.github.io/delphi-epidata/api/v5-signals/nhsn.html) ·
[API keys](https://cmu-delphi.github.io/delphi-epidata/api/api_keys.html)

> Endpoint semantics, the `hosprep_*` coverage family, the ~20% / ~2% revision
> figures used as a reconstruction control, and the access limits: anonymous
> access is *"rate-limited to 60 requests per hour"* with multiple selections on
> at most two parameters, which a free key lifts.

**CDC and CMS — hospital respiratory reporting regime.** ✓ 15 Oct 2026
[CDC weekly metrics](https://data.cdc.gov/Public-Health-Surveillance/Weekly-United-States-Hospitalization-Metrics-by-Ju/ype6-idgy) ·
[CMS QSO-25-05](https://www.cms.gov/files/document/qso-25-05-hospitals-cahs.pdf)

> Mandatory to 2024-04-30; voluntary 2024-05-01 to 2024-10-31, a period CDC flags
> as possibly not fully representative; mandatory again from 2024-11-01. This is
> what the declared eligible universe is built from.

**CDC — FluSight evaluation.** ✓ 15 Oct 2026
[2025-26 report](https://www.cdc.gov/flu-forecasting/evaluation/2025-2026-report.html)

> The hub scores quantile forecasts with **relative WIS** over 23 quantiles, plus
> 50% and 95% coverage. Cited as the reason **not** to borrow WIS: this prototype
> emits point forecasts, and adopting a quantile score for prestige would mean
> producing quantiles nothing else needs.

**GitHub — scheduled workflow limits.** ✓ 15 Oct 2026
[events that trigger workflows](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows)

> Scheduled runs *"can be delayed during periods of high loads"*, *"some queued
> jobs may be dropped"*, and in a public repository schedules are disabled after
> 60 days without activity. The reason the capture reconciles instead of assuming.

**RFC 3161 and OpenTimestamps — the upper bound of the freeze seal.** ✓ 15 Oct 2026
[RFC 3161](https://www.rfc-editor.org/info/rfc3161/) ·
[RFC 3161 for git commits](https://github.com/Ocead/timestamping) ·
[OpenTimestamps in signed commits](https://petertodd.org/2016/opentimestamps-git-integration)

> A timestamp proves data existed no later than the moment it was issued. Free
> TSAs usable with `openssl ts` carry no availability or legal guarantee, which
> is sufficient for a technical proof. An OpenTimestamps proof is **pending**
> until anchored and only counts once `ots upgrade` completes it.

**Framework references, used for vocabulary only.** ✓ 15 Oct 2026
[NIST AI RMF Playbook](https://airc.nist.gov/airmf-resources/playbook/) ·
[AWS Well-Architected ML Lens](https://docs.aws.amazon.com/wellarchitected/latest/machine-learning-lens/)

> Govern / Map / Measure / Manage, and the monitoring and lineage vocabulary. **No
> compliance is claimed**, and neither is voluntary guidance a certification.
