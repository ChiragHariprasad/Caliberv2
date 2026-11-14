# CALIBRE: How We Got Here

**Presentation notes on how the idea evolved, what changed at each step, and why**

These are speaker notes, not slides. Each act has a headline, what we believed, what we found, what we changed, and a line you can say out loud. Use as many or as few acts as your time allows.

Facts about the 2026 Monaco incident come from public reporting and should be checked against primary documents before you quote them.

---

## The story in one minute

We started with a question from a real incident: what happens when the system that measures an infringement is itself wrong? We first tried to catch bad measurements. We then realised the deeper problem is not bad measurements but **evidence that is not adequate for the decision it supports**. That led to SIA, a deterministic reasoning kernel that judges evidence adequacy decision by decision. We built it, found our first attempt was buggy, rebuilt it with tests that prove the tests themselves are not hollow, and then asked how to put it into a real pipeline. Reviewing the whole picture changed the architecture again. Finally, we asked what it would take to still be useful in ten years and to be a genuine alternative to the present approach. That produced a platform with a small stable specification, replaceable parts, and a clear and honest claim about what it can and cannot replace.

**One-line version:** *We went from "catch a faulty sensor" to "prove whether any decision's evidence can be trusted, and keep proving it for a decade".*

---

## Act 1: The spark

**Headline:** A real incident exposed a gap nobody was watching.

**The incident (as publicly reported):**
- Pit-lane speed is an average computed from the time between two timing loops and the distance between them, and it is enforced strictly.
- The first-zone distance, 2,692 cm, followed a standard survey process and was correctly entered. But it was about 77 cm longer than the shortest feasible line after a layout change, so speeds were overstated by roughly 2.9%.
- It surfaced after the race, when a team used its right of review and its own telemetry. Penalties were rescinded, then the court of appeal restored the original classification, reportedly on fairness grounds. A formal measurement procedure followed.

**The question we asked:** what happens when the system measuring an infringement is itself making a measurement error?

**What we learned from it:**
- A system can be online and still provide wrong evidence.
- A sensor can report plausible values while its reference is wrong.
- A common timing system can affect many drivers at once, so individual drivers look guilty when the problem is systemic.
- Independent checking happened only after the fact, and only because one party had its own data.

**Say it out loud:** *"The procedure was followed. The distance was entered correctly. The evidence was still not fit for the decision."*

---

## Act 2: From "find the faulty sensor" to "judge the evidence"

**Headline:** We kept moving the problem one level up.

| Stage | What we tried | What it taught us |
|---|---|---|
| 1 | Detect measurement integrity problems | Spotting a bad number is not enough; the number may be plausible |
| 2 | Cross-check evidence from timing, vehicle telemetry and environment, with uncertainty-aware outcomes | Never trust one measurement blindly |
| 3 | Recognise common-cause failures | Agreement is not independence: two feeds can agree because they share one upstream |
| 4 | Separate integrity from rule evaluation | A central kernel should decide whether evidence is usable; downstream systems decide what it means |
| 5 | Formalise as SIA (Scoped Integrity Algebra) | Contracts, typed time, provenance, corroboration, verdict envelopes, deterministic hashing, revision history |

**The big shift:** from *detecting a faulty measurement* to *evaluating the integrity of the evidence supporting any particular decision*. That is why SIA became the reasoning core and the specialist agents became evidence providers.

**The architectural boundary we fixed here and never changed:**
*Agents observe. Kafka transports. SIA evaluates. Flink executes. Analytics interprets. Humans retain sporting authority.*

**Say it out loud:** *"Traditional monitoring asks: is my system working? SIA asks: given this evidence, its origin, its timing and its history, is this particular decision justified?"*

---

## Act 3: The five gaps that defined SIA

These are the problems SIA exists to solve. Each one is a talking point.

1. **A healthy feed is not healthy evidence.** Everything is online; the underlying configuration is wrong.
2. **Agreement is not corroboration.** Two processors on one source are one measurement. SIA tracks independence on two axes: source and processing.
3. **Missing must not mean healthy.** UNKNOWN is a first-class answer. Silence becomes a verdict through scheduled expectations.
4. **One failure must not invalidate everything.** Evidence is judged per decision. A weather outage affects only weather-dependent decisions.
5. **Time itself can be wrong.** Lap-relative, session-elapsed and absolute time are different types, and conversion needs a valid reference. If the reference is missing, time is not invented.

**The four answers SIA gives:** HEALTHY, SUSPECT, UNKNOWN, DEGRADED, ordered so that the weakest requirement wins an AND and the strongest wins an OR. No averaged confidence number, because a number hides which requirement failed.

---

## Act 4: The first plan and its review (v2.1 to v2.2)

**What the first plan proposed:** a pure Java evaluator, a Flink streaming job, ten candidate contracts, five specialist agents (timing, incident and track, environment, vehicle twin, system integrity), and a roadmap from source validation through to benchmarking.

**What the validation review found:** 20 defects and 9 conflicts in the v2.1 working document. The important corrections:
- **Conservative diagnosis.** Do not exclude a source just because it looks like the outlier. Exclude only what every minimal explanation excludes.
- **Conflict-aware bounds.** Late evidence must be allowed to make a verdict worse, not only better.
- **Silent feeds.** If a feed stops, an event-time watermark stops, and an expiry timer based on it never fires, so the last verdict stays HEALTHY. We added an independent clock and stalled/resumed guards.
- **Separate live and replay clocks.**
- **State, resolution and finality are different things.** A verdict can be HEALTHY yet still open.

**Say it out loud:** *"We did not approve our own first design. The review changed the semantics, not just the wording."*

---

## Act 5: The rebuild: why we threw the old code away

**Headline:** The old implementation could not be trusted, so we rebuilt the core test-first.

**What was wrong, in three classes:**

| Class | Examples |
|---|---|
| Idea-level gaps (could not be caught even if perfectly coded) | A single-source evidence set could be HEALTHY with corroboration depth zero; decision-local views hide systemic bias; absence cannot be noticed if decisions only exist when evidence arrives |
| Specified but never wired in | Typed time resolver never called; scope enforcement never used; stalled guards were dead code; cross-role consistency did not exist; many contract fields did nothing |
| Plain correctness bugs | Timestamps compared as strings; timelines extended backwards in time; results depended on arrival order; the evaluation clock sat inside the hash and created 8,279 verdicts for 112 decisions |

**Seven principles we derived from this:**
1. All instants are integers.
2. The evaluator is a pure function of its inputs.
3. Decision slots are scheduled, not arrival-driven.
4. Every constraint field must change behaviour.
5. Hash content excludes the evaluation instant; the chain link includes it.
6. Fail closed, but still terminate.
7. Explain by named witnesses.

**The quantum-inspired decision.** We kept the structural ideas and rejected the physics. Superposition became the set of states a pending quantity may still take; collapse became early resolution; entanglement became shared dependencies; contextuality became "one fact, many contracts". We rejected amplitudes and interference because they destroy replay. We describe it as possible-world logic with entangled dependencies and never claim quantum computation.

**Say it out loud:** *"We took the useful structure from quantum logic and kept everything deterministic and replayable."*

---

## Act 6: Proving the tests are not hollow

**Headline:** 259 tests, and evidence that they would actually catch mistakes.

- 259 tests cover the algebra laws, canonical hashing vectors, typed time, contract validation, ledger admission, 16 scenario groups, and property tests (order invariance, duplicate idempotence, replay equivalence, envelope soundness over 600 random seeds).
- **Mutation check:** we deliberately broke the code ten ways. Eight were caught immediately, one needed a new test (and now has one), one was an equivalent mutant.
- **Mistakes in our own first draft, found by testing:** resilience depended on the clock; a NaN reading crashed identity; diagnosis was too conservative; a resilience cap made the envelope unsound; a default shared parser made every source look like a single point of failure; an envelope widened on expiry and we had claimed it did not. In the last case we changed the claim, not the behaviour, because the widening is real information.

**Say it out loud:** *"We show our mistakes because that is what makes the tests credible."*

**What the core can do today (scenarios covered):** wrong reference caught by a constraint; inflated timing speed; systemic bias via a population monitor; silent feed; stale evidence with a stationary clock; missing or wrong-lap reference; illegal time class; duplicate processors; two providers sharing one upstream; one outlier among three sources; two conflicting sources; weather outage with scope locality; late evidence; post-finality evidence; impossible values.

---

## Act 7: From library to system (Blueprint v3)

**Headline:** The core was a library. The plan was written for a system. We reconciled them.

**What the review of "plan versus what we actually built" found:**

| Topic | Original plan | What the built core made necessary | Change |
|---|---|---|---|
| Language | Java library | Tested Python core | Run the Python core inside the stream job; keep a port as fallback only |
| Build phases | Minimum version, then full version | Everything already built | Collapsed; remaining work is integration and proof |
| Flink's role | Timers, watermarks, broadcast state | Those reintroduce silent-feed and ordering bugs | Flink supplies mechanics only; time, config and schedule are entries in one recorded log |
| Pipeline | One streaming path | Knowledge time must survive restarts | Two jobs: a tiny sequencer that records order and time, and an evaluator |
| Consumer protection | A lease per verdict | Hundreds of heartbeats | One frontier per session |
| Scheduling | "Generate from the session schedule" | Retirements, red flags and safety cars cause false alarms | A scheduler policy plus **voiding** of legitimately absent evidence |
| Systemic faults | Not planned | The core had a population monitor | A monitor job with lineage rules and status facts that expire |
| Late discoveries | Quarantine only | Sealed verdicts must never change | **Amendment notices** from a counterfactual evaluation |
| Proof of usefulness | Last phase | Momentum would build infrastructure first | Benchmark is now a **gate before** the streaming build |

**The five agents were redesigned** around independent measurement origins rather than topic areas: Timing, Vehicle Telemetry, Position and Geometry, Session Context, and an independent Feed Supervisor. The new one that matters most is Position and Geometry: it gives lap boundaries independent of the timing system, re-anchors broken timing chains, and provides the path-length evidence that detects reference-assumption faults.

**The central architectural idea:** everything the evaluator sees is an entry in one ordered, recorded **admission log**. Replay is exact, recovery is replay, and the engine is replaceable.

**We also corrected our own facts.** Checking public reporting showed the incident was a **geometry-model fault**, not a mistyped number, so the right constraint is a one-sided inequality. It also showed that one source linked in our brief was about a different, earlier incident, and that a figure we quoted (11 of 423 passages) does not match public reports.

**Say it out loud:** *"The log is the truth. State is a cache. The stream engine is just the machinery."*

---

## Act 8: Making it last ten years and making it an alternative (Blueprint v4)

**Headline:** A tool for one incident is an anecdote. A platform is a different thing.

**What the new requirement forced:**

| Requirement | Consequence |
|---|---|
| Useful beyond one incident | A domain-neutral platform with domain packs; Formula 1 is the reference pack; a 17-class failure taxonomy; Monaco is one entry, not the target |
| Useful in 5 to 10 years | A small, language-neutral specification suite with conformance tests that outlive any code; a growing golden corpus; capsules and a standalone verifier so a past verdict can be reproduced on a clean machine; a second implementation |
| An alternative to the present system | A precise definition of what that means, and an adoption ladder |

**The five agents stayed, as archetypes.** Defined by function and independence (Measurement, Asset Telemetry, Spatial, Context, Supervisor), so a new provider or sensor replaces the implementation without changing the architecture.

**Kafka and Flink stayed, as the reference execution profile.** Flink releases quickly and connectors change per release, so infrastructure is treated as replaceable. A file-based batch profile is mandatory and permanent.

**Ten irreversible choices frozen before any production log exists:** algorithm-tagged digests, version fields on every record, time-scale tags on instants (leap-second policy is reportedly changing around 2035), namespaced identifiers, pack-defined scope hierarchies, a units registry, versioned vocabularies, a closed set of log entry types, open archive and bundle formats, and version metadata kept outside the hashes. These are cheap now and effectively impossible to change after years of archives.

**Data regimes made the roadmap honest.** Public feeds share one platform upstream, so independence cannot be proven on them. We defined four regimes (public, licensed, institutional, lab). The platform works in all four; what it may claim differs. Real independent corroboration begins with institutional data.

**A new insight about thresholds.** A ±5 cm survey uncertainty over a 26.92 m zone is about ±0.11 km/h at 60 km/h. A 0.1 km/h exceedance is inside the uncertainty of a *correct* procedure. So CALIBRE reports margin against uncertainty. Whether to apply a guard band is a human policy decision.

**Say it out loud:** *"Specifications outlive code. Infrastructure is a replaceable tier. The ability to reproduce the past is a feature we design in on day zero."*

---

## What "better than the present system" means (the honest version)

**What the present approach looks like:** trust the authoritative system by default, monitor whether feeds are alive, investigate manually after a dispute.

**Three meanings of "alternative":**
- **Replace feed-health monitoring:** yes, fully.
- **Replace manual after-the-fact forensics:** yes, with humans signing off.
- **Replace the official timing system:** no, by design. CALIBRE has no privileged sensors and is not a measurement system. It is an independent verifier.

**Where it is better:**

| | Present | CALIBRE |
|---|---|---|
| What is assured | The feed | The specific decision and its evidence |
| Independence | Assumed | Declared, computed and displayed |
| Missing evidence | Often invisible | UNKNOWN or DEGRADED with named reasons |
| References | Procedural | Expire when layout or rules change |
| Threshold decisions | Value against limit | Value plus margin against uncertainty |
| Late corrections | Overwrite or argue | New revisions, or amendments after sealing |
| Audit | Documents, reconstructed | Hash-chained, bitemporal, offline-verifiable bundle |
| Who sees it | Whoever holds the data | Every authorised party |

**The adoption ladder (stating it honestly):**
0. Open observer on public data.
1. Advisory tool for analysts, teams and researchers.
2. Independent verifier piloted with an institution, no decision rights.
3. Evidence gate: threshold decisions deferred unless integrity is adequate or a logged human override exists.
4. Referenced standard with multiple implementations.

Rungs 3 and 4 depend on institutions, not engineering. The design makes rungs 0 to 2 credible without anyone's cooperation.

**Where it is not better:** it makes no measurements; public data cap its claims; it adds governance effort; and its benefit must be proven by benchmark, not asserted.

---

## How we will prove it (a good slide-free talking point)

- A **pre-registered benchmark** against three baselines: a per-feed freshness flag, freshness plus naive source counting, and an engineered monitor.
- Seven original fault classes plus a **blind set authored separately**, with the motivating event held out entirely.
- Gate: fewer false-HEALTHY results than the simple baseline on at least four of seven classes, and a win over the engineered monitor on at least two, with no unacceptable rise in false alarms.
- **Scale-back rule:** if it fails, keep the pipeline and reduce the advanced features through contract configuration. We would rather ship a smaller honest system than a larger unproven one.
- A **living benchmark** re-run every season, published including failures.

---

## Turning points (the five decisions that shaped everything)

1. **Move from detecting bad measurements to judging evidence adequacy per decision.** This created SIA.
2. **Rebuild the core test-first and prove the tests are not vacuous.** This created trust in the kernel.
3. **Make the recorded admission log the single source of truth and keep stream-engine semantics out of verdicts.** This made replay exact and the engine replaceable.
4. **Move the benchmark before the heavy build.** This prevents momentum from outrunning evidence.
5. **Put a small specification, a golden corpus and a few irreversible choices at the centre, and treat everything else as replaceable.** This is what makes ten years plausible.

---

## What we deliberately refused to do

- Produce a single confidence score.
- Use quantum physics claims, or any learned component inside the trust boundary.
- Claim that public data can prove independent sources.
- Claim a small bias is detectable per passage without a measured detectability figure.
- Replace the official timing system or adjudicate outcomes.
- Present any tolerance as calibrated before a calibration record exists.
- Assume institutions will adopt it.

---

## Likely questions and short answers

**Why not just improve feed monitoring?**
Because the failure was not a dead feed. It was a live feed with an unfit reference. Monitoring asks if the system is working; SIA asks if this decision is justified.

**Why not use machine learning?**
Evidence adequacy needs to be reproducible and explainable to a hearing. ML can propose candidates outside the trust boundary, but a verdict must be a deterministic function of recorded evidence.

**Why is there no confidence percentage?**
A percentage hides which requirement failed. Named states and witnesses tell people what to check.

**Why Kafka and Flink for such small volumes?**
Volume is tiny, around tens of thousands of evidence items per race. They are justified by durable ordering, recovery and replay, not throughput, and the design treats them as replaceable.

**Why is the core in Python?**
It already exists and passes 259 tests. A second implementation in another language is planned from the specification, to prove the specification is the truth.

**What if the public data sources disappear?**
Raw data are archived permanently, contracts name roles rather than feeds, and a data-regime model lets us move to licensed or institutional data without changing the architecture.

**Can it detect the Monaco-type fault on public data?**
Partly. It can report stale or expired references, margin against uncertainty, and descriptive concentration of exceedances. Isolating the reference fault needs loop positions that are probably not public, so full detection is demonstrated in the lab and becomes real with institutional data.

**Does it decide penalties?**
Never. It says whether evidence is adequate. Rule evaluation is deferred with reasons; humans decide.

**How do you know it will still work in ten years?**
A versioned specification with conformance tests, a frozen golden corpus replayed on every release, pinned toolchains that can reproduce any past verdict, algorithm-tagged hashes, and governance that does not depend on one person.

**What if SIA itself is wrong?**
Differential testing against a second implementation, the corpus, a verifier job, and offline-verifiable bundles so anyone can re-check a conclusion.

---

## Closing lines

- *"Systems fail quietly when we trust evidence just because the feed is healthy."*
- *"CALIBRE does not tell you who was right. It tells you whether the evidence is good enough to decide."*
- *"We designed it so that in ten years, anyone can take a bundle and verify what we concluded, and why."*