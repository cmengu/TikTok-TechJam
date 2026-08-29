<!--
The Pivot Sequence — generated 29 Aug 2026 from Pivot_sequence.html
Regenerate: python3 tomd.py Pivot_sequence.html
-->

> **Plain-text rendering of `Pivot_sequence.html` (same directory), which is the authoritative source — the HTML carries eight SVG diagrams; each is reduced below to a `[diagram …]` line listing the diagram's own text labels.**
>
> Architecture direction, the refusals, one-owner-per-field arbitration over 13 papers, and ten capability scopes. Companion to `Execution_runbook.md`, which sequences these into runnable steps.
>
> Facts marked `[TREE]` were verified against `beating-nise` at commit `3e22b28` on 29 Aug 2026.
> Facts marked `[GIVEN]` are inherited from the task-space page — re-verify before relying on one.
> ⚠ Not yet reconciled with `~/Downloads/kuairand-starter-kit/README.md`: splits are **temporal, not by user**;
> `evaluate.py` is the sole scoring authority and must not be reimplemented; the submission key is
> `row_id` (not `sample_id`), and `(user_id, video_id)` is **not** unique; the kit is **numpy-only**.
> See `Runbook_reconciliation.md` (same directory) for the verified list of conflicts and the precedence rule.

---

_TikTok TechJam 2026 · Track 2 · execution order_

# The Pivot Sequence

Where the architecture is going, what it deliberately refuses to become, and which published system each decision came from. The file-by-file order sits at the bottom, where it belongs — it is the consequence of the direction, not the direction itself.

- **Repo:** beating-nise
- **main:** b1e7193
- **Standing on:** docs/phase-9-handoff
- **Open PRs:** 5 · 4 clean
- **Dataset:** not downloaded
- **Deadline:** 1 Sep 12:00

## One round — what actually runs  ·  _the mechanism, in order_

Before any architecture. This is the loop end to end, and everything else on this page exists to make one of these seven stages honest. Read it once and the rest of the document is commentary on it.

- **01 propose** — three, by p_win · cost: tokens

- **02 gate** — rules + shapes · cost: ~0 s

- **03 smoke** — all survivors · cost: ≤60 s each

- **04 screen** — ALL of them · cost: ~40 s each

- **05 replicate** — advancers, 3 seeds · cost: ~2 min

- **06 oracle** — promotions only · cost: ~40 s

- **07 attribute** — observables moved? · cost: ~0 s

Whole round: comfortably under ten minutes of one CPU core.

**Step 1 — Propose three**

Drawn from the hypothesis bank in order of probability of clearing ε, with anything matching the forbidden store filtered out before it reaches the model. Each proposal must declare its edit surface, the mechanism it claims, and its observables — a proposal missing any of the three is not a proposal. This is the one thing kept from AgentX’s six-term score, and it is kept as a gate rather than a weight.

**Step 2 — Gate before spending**

Constraint filter, then semantic review. Both reject before anything runs, and together they are effectively free. A rejection here costs one LLM call; a rejection after training costs forty seconds and a slot in a two-day budget.

**Step 3 — Smoke every survivor**

Sixty-second cap each, one epoch, truncated rows. Catches crashes, divergence and shape errors — the failures that have nothing to teach us and should never reach a scoring run.

**Step 4 — Screen every survivor**

One seed each, roughly forty seconds apiece. This is the step that replaces the model’s guess about which candidate is best with three real numbers. It is the whole reason we can refuse to rank before running.

**Step 5 — Replicate the advancers**

Three seeds, only for candidates the screen advanced. Separates a real effect from a lucky draw before anything is built on top of it.

**Step 6 — Consult the oracle on promotion only**

Score the candidate on the randomly-exposed split — the one free of the logging policy’s bias. This is the reading that turns a closed loop on its own metric into a loop validated from outside itself, and it is the same reading that later serves as the overfitting monitor.

**Step 7 — Attribute, then remember**

Did the observables the proposal declared actually move? Clear promotes. Unclear withholds promotion and queues one diagnostic instead — the number is not disputed, only the story about why it moved. Either way a lesson is written and any new forbidden pattern is appended, so the next round cannot spend tokens re-proposing this one.

**Step 8 — x — Stop, and submit the incumbent**

When ε is not cleared for N consecutive rounds, the incumbent at that moment is the answer. x = a predictions file written from the validation-best checkpoint, plus a run report in which every number was produced by the measurement layer rather than asserted by a model, every promotion carries an oracle reading beside it, and the autonomy level claimed at the top is derived from the event log rather than typed into a slide.

The alternative we are refusing

NOVA generates four candidates, asks a model which looks most promising, and runs only that one. Substituting stage 4 with a judgment call.

It spends tokens — which we are scored on — to save forty seconds, which we are not. That trade is correct at Tencent’s evaluation costs and inverted at ours. It is the single clearest case on this page of a good decision from a good paper being the wrong decision here, and the reason the arbitration below is by named axis rather than by reputation.

## Where this is going  ·  _direction_

A search loop in which no result is believed on the strength of the same distribution that produced it.

That single sentence is the architecture. Everything the harness already does — propose, gate, measure, judge, log — is machinery in service of it, and the one thing it cannot yet do is the thing the sentence turns on. Today a candidate is promoted because it scored well on the validation split the search is already steering by. That is a loop closing on its own opinion.

The published ladder for autonomous research agents splits the closed-loop tier in two, and the split is about who validates rather than how much the agent does. L4-m is mechanical: results feed back, but the trigger is the loop's own internal metric. L4-v is validated: revisions are gated by an oracle outside the search. Of twenty-four systems the survey audits, nine reach L4 — seven mechanical, one author-claimed, and exactly one externally validated, which is CAMEO from 2020 and not an LLM system at all.

KuaiRand hands us the missing oracle for nothing. log_random_4_22_to_5_08_pure.csv is roughly 1.18 million randomly exposed impressions — served without the production recommender choosing them. A model that scores well by agreeing with the logging policy gets no credit from it. That is what makes it an oracle rather than a second validation set.

- **L1** — Tool-augmented — a human drives, the model assists

- **L2** — Stage-local — autonomous inside one bounded task

- **L3** — Pipeline — chains several stages without approval at each step

- **L4-m** — Closed loop, mechanical — results revise the next hypothesis, but the trigger is the loop’s own metric  ← **YOU ARE HERE**

- **L4-v** — Closed loop, validated — promotion is gated by a measurement the optimiser cannot influence  ← **THE DESTINATION**

- **L5** — Open-ended — aspirational; nothing occupies it

One boundary the rules impose, and it is worth stating precisely because it is easy to overclaim: the scored submission is fixed as the validation-best checkpoint at convergence. So the oracle gates what the search keeps, not what it finally submits. Both halves are true at once, and together they are the L4-v claim — validation still selects; the oracle steers.

## What we are building  ·  _target loop_

Four stages, one rule. A hypothesis is proposed, cheap gates reject it before anything expensive runs, deterministic code produces every number, and judgment decides only whether the result is believed. Eleven of the fourteen boxes already exist.

[diagram — see the HTML/artifact version. Labels: 1 · PROPOSE · 2 · GATE — CHEAP REJECTS · 3 · MEASURE — DETERMINISTIC · 4 · JUDGE · hypothesis bank · bank.yaml — aimed at dead ends · LLM proposer · agents/researcher.py · trajectory memory · lessons.jsonl — wire broken · forbidden patterns · rules.jsonl — no consumer · semantic gate · V_sem · agents/contract.py · local smoke · V_loc · smoke rung, 60 s cap · runner + classifier · retry table · watchdog · noise band + ladder · σ off by 12× · external oracle · random-exposure holdout · attribution check · built, pinned to "clear" · promote / reject · measure.py verdict · submission writer · wrong CSV schema · append-only event log — every box writes to it, nothing holds private state · events.jsonl · typed events · replay reconstructs the whole run · verdict → trajectory memory + new forbidden rule → next proposal · built and correct · built, but wrong or disconnected · absent — and it is the one that defines the destination]

_The loop is not missing machinery. It is missing one component and four connections — and the dashed return arc is the part every paper below agrees is what separates a search from a sequence of guesses._

The organising rule underneath all of it: an LLM is permitted to be wrong only on judgment; every objective fact is produced by deterministic code. Metrics come from result.json, verdicts from ladder arithmetic, priorities from evidence folded over our own log. That rule is also what condemns several mechanisms in the next section — asking a model to rank untested candidates is asking it to judge something numerical, when we could simply measure instead.

## What we are not building  ·  _refusals_

Every item here is defensible somewhere, and most are load-bearing in the papers they come from. Grouped by why they fail here, because the reason is the interesting part — and because each refusal is a sentence the write-up can make rather than a silence it has to cover.

### Cut because the economics inverted

These mechanisms all exist to avoid spending an expensive evaluation. At Tencent and Kuaishou an evaluation costs GPU-hours and, at the end, real traffic. Here a full training run is forty seconds on one CPU core. The scarce resource moved to iterations and tokens, so machinery that trades cheap generation for expensive evaluation now runs backwards.

**Ranking K candidates before running one**

NOVA generates four, ranks them, evaluates the winner. Generate three, run all three, and keep three measured numbers instead of one model’s guess about which diff looks best. Two minutes of CPU buys what a ranking prompt only estimates — and the ranking violates our own rule that no LLM judges anything numerical.

**Expert-panel supermajority voting**

AgentX runs N experts and requires ⌈2N/3⌉ to agree before a candidate proceeds. It is a way of buying confidence without paying for a run. We can pay for the run.

**SGPO prompt self-evolution**

Refines a subagent’s prompt, then admits the edit only if a paired replay beats the old one by ε. Real results — 75.2% to 98.0% over five rounds — but it needs a trace corpus and a replay harness, and we have neither. GEPA is the same idea at roughly a hundredth of the cost, and is the right thing to reach for in September.

**A four-model judge ensemble**

Same objection, sharper: it spends tokens, which are scored under Feasibility, to approximate a number we can compute exactly for free.

### Cut because the organizers already measured it flat

The kit is unusual: it publishes the ablations its authors already lost time on. These are not open questions, and under a convergence rule spent three failures at a time, proposing one is not a cheap experiment — it is a third of the remaining runway. They become pre-loaded forbidden rules, not hypotheses.

**More static features**

CWM’s full 13 fields scored 0.5940 against 0.5950 for the kit’s 5 — inside noise, marginally worse. Four of the ten current bank entries aim here.

**More capacity, and the deeper architectures behind it**

Embedding width k = 8/16/32 gave 0.5895 / 0.5902 / 0.5887 — flat across a 4× sweep. The organizers rank DeepFM, DCN and xDeepFM fifth of seven for exactly this reason: 1.14M rows will not support a larger model.

**Anything constant within a user**

Ranking happens strictly inside each user, so a pure user-side term contributes exactly zero however predictive it looks. Verified, not asserted — item_pop × user bias scores identically to plain item_pop, digit for digit. Two bank entries risk this trap.

### Cut because the thing it targets does not exist here

Not a judgment call — the referent is simply absent, and keeping the machinery would mean reporting on something that cannot happen.

**The online experiment stage**

NOVA’s seventh agent ships the best offline candidate to a 5% traffic A/B, and its whole objective has an online half. There is no traffic. The offline score is the entire objective, and no equivalent is needed.

**GPU-hour accounting**

The ranking denominator is currently gpu-min, which is now identically zero — dividing by it breaks the arithmetic outright. The judging criteria replaced it with agent wall-clock for the same reason.

### Deferred, not cut — the queue for the far side of 1 September

These are the ones worth wanting. Each is a real improvement to the architecture and none of them fits inside two and a half days without putting the submission at risk.

**MLE-STAR’s block ablation**

The best available answer to “which component should I search inside”, and cheap — four blocks at forty seconds is under three minutes. It computes NOVA’s weak_components mechanically instead of asking a model for it. First thing to add if the build lands early.

**DIN / SIM behaviour sequences**

Second on the organizers’ ranked list and the largest of the seven by a distance: the FM’s shared offset table has no sequence slot, so it is an architecture change rather than a feature. The one genuinely high-value direction to leave closed.

**GEPA, and the auto-fine-tuning branch**

Reflective prompt evolution under Pareto selection, beating GRPO by ~6% with up to 35× fewer rollouts. Past the deadline the honest framing of this project stops being “a hackathon entry” and becomes a task-agnostic search harness whose first task happened to be a recommender.

## One field, one owner  ·  _arbitration_

The worry is the right one. There is a great deal of published machinery aimed at ranking candidates, scoring proposals and self-improving agents, and most of it overlaps. Adopting several systems’ answers to the same question is how a harness ends up with three half-wired mechanisms that disagree. So the page uses one rule.

> **THE ARBITRATION RULE**

Each capability area gets exactly one owning paper. A second paper targeting an occupied area is rejected by default, and admitted only if it beats the incumbent on a named axis that matters here — not on general merit, and not because it is newer. NOVA and AgentX are the default incumbents, because they are the two systems closest to what we are building and both are deployed.

Anything admitted over them must survive one question: what does this do that the incumbent cannot, given forty-second evaluations, two days, and one run?

| Capability area | Owner | What we take | Rejected in this area, and why |
|---|---|---|---|
| Search topology how candidates relate | AIDE | Tree over whole solutions; draft / debug / improve under a fixed policy; a depth limit on debugging. | Uncontested. Neither NOVA nor AgentX does tree search — both iterate a single lineage. Admitting AIDE creates no conflict. |
| Pre-run verification rejecting before spending | NOVA | The four-level cascade: constraint filter, semantic review, local smoke, then measure. | FunSearch — same area, but it contributes a principle and no additional mechanism. Cited, no code. Adding a second verifier would mean two things deciding the same rejection. |
| Failure memory not repeating a mistake | NOVA | Forbidden patterns as records: edit pattern → defect class → round. | AgentX’s Experiment KB — genuinely the same area. Rejected because it is built from years of production launch reviews, while NOVA’s version is a checkable record generated by the run itself. We have a run; we do not have years. |
| Feedback format what a round hands the next | NOVA | The three fields — weak components, directions, forbidden — as headings rather than prose. | AgentX’s six-term weighted proposal score. Same area, and rejected on a hard constraint: six weights need data to fit and we will have roughly ten rounds. See the translation below for what we keep from it. |
| Attribution did the change cause the gain | AgentX | Declare a policy and named observables before writing code; refuse to credit a gain whose observables did not move. | Uncontested. NOVA has no equivalent — its verification is about validity before the run, not causality after it. The two are complements, not competitors. |
| Numerical honesty who is allowed to be wrong | AgentX | A model may be wrong on judgment, never on an objective fact. | Uncontested, and it is the rule that decides several rows above. Anything asking a model to rank untested candidates loses to it automatically. |
| Evaluation integrity is the measurement trustworthy | AIRA-2 | Fixed splits, externalised scoring, and the decoupling of the signal that steers from the signal that selects. | This is the one area where NOVA and AgentX are both beaten, and it is worth saying why: both resolve trust by shipping to live traffic at the end. With an online A/B available you do not need an offline oracle. We have no traffic, so we need the offline discipline they could afford to skip. |
| Where to search next which component is the bottleneck | MLE-STAR | Ablate the candidate’s own code blocks and measure which one moves the score. Deferred, not cut. | Admitted over NOVA rather than against it: NOVA names this field as weak_components and supplies no cheap method for computing it. MLE-STAR fills the incumbent’s own declared gap, which is the only clean reason to admit a second paper. |
| Agent self-improvement the harness editing itself | GEPA | Nothing, in this iteration. Named as the September route. | SGPO — same area, and the incumbent, since it is AgentX’s own layer. Rejected anyway: it needs a corpus of recorded traces or merged code changes plus a replay harness. GEPA needs only its own rollouts. When the incumbent requires infrastructure we do not have and the challenger does not, the challenger wins. |
| Cheap-then-expensive validation two loops at different costs | Self-Evolving RecSys | The two-loop shape, as a mental model only. No separate code. | Overlaps AIRA-2’s decoupling, so it is deliberately demoted to framing. Two papers may share an area only if one of them contributes no mechanism — which is the case here. |
| Autonomy claim what we are allowed to say | the survey | The L0–L5 ladder, and its failure-mode list as a checklist of things not to claim. | Uncontested. Neither industrial paper grades itself on an external ladder — they report business metrics instead. |
| Overfitting a public split and knowing whether we did | Blum & Hardt | The threshold-ladder mechanism, and three monitors. See the section below. | A genuinely vacant area — neither NOVA nor AgentX addresses it, because neither competes on a public leaderboard. Admitting an outside paper here creates no clash, which is exactly why it is worth admitting. |

### Where the papers actually contradict each other

Five real disagreements, and the resolution in each. These are the places where copying two systems at once would have produced incoherent behaviour.

**Rank before running, or run everything?**

NOVA generates four candidates, ranks them, and evaluates the winner. AIRA-2 finds that the compute-optimal number of parallel attempts grows with the square root of the budget — breadth over depth.

**AIRA-2 wins** — Directly on cost. NOVA’s ranking is an economy measure for expensive evaluations. Ours cost forty seconds, so ranking spends tokens to avoid spending something cheaper than the tokens.

**Learn from a knowledge base, or from the run itself?**

AgentX queries four curated knowledge bases for precedent. NOVA accumulates forbidden patterns from its own failures as it goes.

**NOVA wins** — Purely on what exists. A knowledge base is an asset you must already own; a forbidden-pattern store is generated by the thing you are about to run. With one run and a 700-line kit, only the second is available.

**Vote on a candidate, or measure it?**

AgentX convenes an expert panel needing a two-thirds supermajority before a candidate proceeds.

**Measurement wins** — And it is AgentX’s own rule that decides it. A panel voting on untested candidates is a model judging something numerical, which their numerical-honesty principle forbids. The panel is what you build when you cannot afford to measure; we can.

**Pick the best node, or pick the best validated node?**

AIDE takes a plain maximum over every node it explored. AIRA-2 shows that selecting on the same signal you searched with is where a large part of the reported gap comes from.

**AIRA-2 wins** — With one boundary we do not control: the competition fixes the submission as the validation-best checkpoint. So the decoupling operates one level in — every promotion along the way is gated by the oracle, and the final maximum is taken over a set already filtered by something the search could not influence.

**Score proposals on six weighted terms, or on one?**

AgentX ranks ideas on a weighted sum of objective alignment, business validity, feasibility, handoff completeness, evidence and risk.

**One term wins** — On a calibration argument, not a philosophical one. Six weights are parameters, and parameters need data to fit. AgentX has years of launch outcomes to fit them against. We will have about ten rounds, so six untuned weights would be six guesses dressed as a formula. The translation below keeps the two terms that change behaviour and drops the four that would be noise.

## Where each decision comes from  ·  _provenance & mechanism_

Every borrowed mechanism, explained rather than named, with what we take, what we refuse, and why. All nine arXiv identifiers in this section were re-resolved today and return the titles quoted, as were the four in the overfitting section below. Terms are defined at first use, and collected again in the glossary at the end.

### NOVA
arXiv:2606.27243 ↗

Tencent, 20 authors. A Verification-Aware Agent Harness for Architecture Evolution in Industrial Recommender Systems. The closest published relative of this tree: an agent that repeatedly rewrites a recommender’s architecture, under a budget, with machinery for rejecting bad ideas before they cost anything.

**The verification cascade — what each gate actually asks**

“Cascade” means a chain of tests ordered cheapest-first, where failing any one stops the chain. The point is never the individual test; it is the ordering. You never spend an expensive check on something a cheap check could have killed.

NOVA runs four levels. The first is a hard constraint set the paper calls Ω — a purely mechanical filter asking whether the proposed change even produces a legal model: do the tensor shapes line up, do the data types match, do the features it references actually exist, does it fit the latency, parameter and computation budgets the production system imposes. Nothing intelligent happens here; it is closer to a compiler than a reviewer.

The second is the one that carries the paper’s name — Vsem, a semantic review. An agent reads the code change and asks whether it does what the hypothesis claimed it would do. It never runs anything. This catches the failure that a crash-check cannot: code that executes perfectly and implements the wrong idea.

The third, Vloc, is a local smoke test — run it on one machine, on a sliver of data, with a short time limit, and see whether it survives. It catches crashes, numerical blow-ups and models that diverge. Only what survives all three reaches the fourth level, the expensive one: train properly and measure.

In plain terms

It is airport security. ID check, then bag scan, then the pat-down — in that order, because reversing it would be absurd. Each step is slower and more thorough than the last, and each one exists to make sure the slow step only ever runs on things worth its time.

The unusual member is the semantic review. Most pipelines only ask “did it crash?”. This one asks “did it do what you said it would?” — which is a different question, and the one that catches the expensive mistakes.

[diagram — see the HTML/artifact version. Labels: SURVIVORS · WHAT THIS GATE THROWS AWAY · 1 · CONSTRAINT FILTER Ω · cost: milliseconds · mechanical · Shapes that do not line up, wrong data types, · features that do not exist, over budget. · 2 · SEMANTIC REVIEW V_sem · cost: one read of the diff · nothing runs · Code that runs perfectly and implements · the wrong idea. The expensive mistake. · 3 · LOCAL SMOKE V_loc · cost: 60 s cap · tiny slice of data · Crashes, numbers blowing up to infinity, · training that diverges instead of learning. · 4 · TRAIN & MEASURE · 40 s here · GPU-hours at Tencent · Nothing — this one produces the number. · Everything above exists to protect it.]

_Our equivalents: the constraint filter is hardcoded and small (mostly leakage checks), agents/contract.py reading rules.jsonl is Vsem, and the smoke rung with its 60-second cap is Vloc. All three are built. The width of each bar is illustrative, not measured._

**Why we keep the cascade for a different reason than NOVA has**

This distinction matters enough to state in the write-up, because inheriting a mechanism without re-checking its justification is how plans go stale. At Tencent, an evaluation costs GPU-hours and eventually real user traffic, so every gate that rejects early saves money. Here a full training run is forty seconds on one CPU core, so measured in compute the cascade saves almost nothing.

What it saves instead is an iteration. The competition’s convergence rule ends the run after three consecutive rounds without a meaningful improvement — and a candidate that crashes, or that violates the task contract, still consumes one of those three. Under that rule the gates are not an efficiency; they are the difference between a run that reaches a good idea and one that dies before it gets there.

**Forbidden patterns as structured memory — how it actually works**

Most agents that “learn from failure” do it by pasting the last error message into the next prompt. That is memory, but it is memory a machine cannot check, and it decays as the conversation moves on. NOVA does something narrower and much more useful: it converts each confirmed failure into a record with fields, and those fields are chosen so that a later check can test a new proposal against them mechanically.

A record maps an edit pattern — the generalisable shape of the change that failed, not the specific diff — to a defect class, which names why it failed as a category rather than as an incident. It is tagged with the round that produced it, so the store carries its own provenance and you can see what the search learned and when.

The paper’s own example was learned in its seventh round:

**pattern:**       sequence self-attention without a causal mask
**defect class:**  future-information leakage
**round:**         7

Unpacking that: self-attention is a mechanism that lets a model look at every position in a sequence at once. A causal mask is the constraint that stops each position from seeing positions that come after it. Leave the mask out while modelling a user’s history and the model can see what the user did tomorrow while predicting today — it scores brilliantly offline and is worthless in production. That is future-information leakage, and it is a whole family of bugs, not one bug. Written as a pattern, one round’s diagnosis immunises every future round against the entire family.

The store is then read from two places, which is the part that makes it a loop rather than a log. Before generation it goes into the proposer’s prompt as a list of things not to suggest. After generation it becomes a set of checks the semantic gate applies to the new diff. One is soft prevention, the other is hard rejection.

In plain terms

Every time the agent gets burned, it writes itself a new lint rule — the kind of automated check that flags a known bad pattern in code — and from then on that rule is enforced on everything it writes. The difference from a normal lint rule is that the agent diagnoses the failure and authors the rule itself.

The reason it must be a pattern rather than the specific broken diff is generalisation. “This exact line was wrong” protects you from one mistake. “This shape of change causes this class of defect” protects you from all its cousins.

[diagram — see the HTML/artifact version. Labels: LEARNING — RUNS ONCE PER CONFIRMED FAILURE · a candidate fails · crash · rule trip · went negative · root-cause it · why, as a category · generalise the shape · pattern, not this one diff · append a record · pattern · class · round · the forbidden-pattern store · rules.jsonl — grows as the run learns · into the proposer's prompt · soft — do not suggest these · into the semantic gate · hard — reject on a match · read twice, every round]

_Our rules.jsonl already has this record shape — statement, pattern, severity, source. Both consumers are the gap: nothing appends new records during a run, and agents/contract.py does not read the file. Fixing those two wires is what turns a static checklist into memory._

**The architecture gradient, and what its three fields mean**

First, the word. In ordinary machine learning a gradient is a set of numbers telling you which direction to nudge each parameter to make the model better. NOVA borrows the word as a metaphor: its gradient is not numbers and does not touch parameters. It is a structured report telling the search which way to move next — a direction in idea-space rather than parameter-space. Calling it a gradient is a claim that it gets recomputed from fresh evidence every round, rather than being a plan fixed at the start.

It is computed from four inputs: the edit that was just tried, the diagnostics the verification gates produced about it, the measured change in the objective, and the entire history so far. It produces three named fields.

- Weak components — which part of the system is currently the bottleneck. NOVA splits an architecture into three parts: the model graph (its structure), the structural hyper-parameters (its sizes and shapes), and the feature configuration (what goes in). This field says which of the three is holding the score back, so the next proposal aims there instead of somewhere arbitrary.
- Directions — which families of idea to explore next, given what has worked so far. This is the field most systems have in some form; it is essentially a ranked shortlist.
- Forbidden — the accumulated patterns that failed, were invalid, or made things worse. The store described above.

In plain terms

After each experiment the agent writes itself a three-line memo: where the problem is, what to try next, and what never to try again. The insight is that these are three genuinely different kinds of knowledge and a single score cannot carry any of them. A number tells you an idea did not work; it does not tell you whether the fault was the features, the model or the setup.

Where we stand against it: our queue’s family-evidence ranking implements directions. rules.jsonl is forbidden, with its consumer missing. Weak components has no implementation at all — nothing in the harness currently asks which part of the pipeline is the bottleneck. That is the honest gap, and MLE-STAR below is the cheap mechanical way to fill it.

**EPR, LPR and SFR — the three numbers, and the trap they expose**

These are just pass rates, but the way they factor is the useful part.

EPR  =  LPR  ×  (1 − SFR)

LPR, landing pass rate — of the changes generated, the fraction that actually ran to completion. Did it get off the ground.

SFR, semantic failure rate — of the changes that ran, the fraction that did the wrong thing. Ran, but wrong.

EPR, effective pass rate — the fraction that both ran and were right. The only one that matters.

A single “success rate” hides a trap, and NOVA’s ablation demonstrates it exactly. When they removed the step that grounds a change in the source paper it was drawn from, the landing rate rose to 91.7% — more code than ever ran cleanly — while the semantic failure rate ballooned to 63.6%. Effective pass rate fell from 60.0% to 33.3%. The system generated more working code and got substantially worse.

In plain terms

A student who hands in every assignment on time, fully complete, having answered the wrong question. Their submission rate looks superb. Track only that number and you would conclude they are your best student.

We can report all three with no new instrumentation, because our event log already distinguishes the two failure kinds: a failure event is a landing failure, and a rule_trip is a semantic one. That is a results table almost no other team will have.

[diagram — see the HTML/artifact version. Labels: 100 CHANGES GENERATED — NOVA WITHOUT ITS GROUNDING STEP · 33.4 effective · ran and were right · 58.3 ran, and were wrong · invisible if you only ask "did it crash?" · 8.3 · never ran · landing pass rate 91.7% — the number that went UP when the system got worse · full NOVA reached 60.0 effective — the teal block would end here · what the semantic grounding step recovers · Segments computed from the paper's reported LPR 91.7% and SFR 63.6%; 0.917 × 0.364 = 0.334, matching its reported EPR of 33.3%.]

_The amber block is the whole argument for a semantic gate. It is code that compiled, trained, produced a number, and implemented the wrong idea — and no crash-counter anywhere in the system can see it._

**What its ablation says about where to spend the remaining time**

An ablation is the experiment of removing one component and re-measuring, to find out what that component was worth. NOVA’s is unusually useful because it tells you which part to protect when you run out of hours.

| Configuration | Effective pass rate | What it means |
|---|---|---|
| NOVA, complete | 60.0% | Reference. |
| without solution design | 18.2% | Removing the step that turns a goal into a concrete plan costs two thirds of the performance — more than removing any verification component. Planning is the load-bearing part. |
| without paper grounding | 33.3% | More code runs, far more of it is wrong. The row the chart above decomposes. |
| without gradient feedback | 37.5% | Failures stop becoming search knowledge, and the loop starts repeating itself. |
| a plain agent, no harness | 7.1% | The harness is the contribution, not the model behind it. |

For us that reads as an instruction: with two days left, an hour spent on the hypothesis bank and the opening order is worth more than an hour spent adding a fourth gate.

**The decisions**

- [Adopt] The cascade, already built as agents/contract.py plus the smoke rung.
- [Re-justify] Its stated purpose changes. It protects an iteration, not compute. Say this explicitly rather than inheriting NOVA’s reasoning unexamined.
- [Adopt] Forbidden patterns as records of pattern → defect class → round. The schema is already right; both consumers need wiring.
- [Adopt] The gradient’s three fields as the feedback format. We have directions, we have the forbidden store, and we have no weak-components implementation.
- [Adopt] Reporting EPR, LPR and SFR separately. Free — the log already separates the two failure kinds.
- [Reject] Generating four candidates, ranking them, and evaluating only the winner. This exists because at Tencent an evaluation costs GPU-hours, so it is worth paying an LLM to guess which candidate is best. Here the trade runs backwards: generation costs tokens, which are scored under Feasibility, and evaluation costs forty seconds. Generate three, run all three, and hold three measured numbers instead of one guess. It also breaks our own rule — ranking untested candidates is a numerical judgment, and we said no model makes those.
- [Reject] The online experiment stage. NOVA’s seventh agent ships the best offline candidate to 5% of live traffic, and half its objective function is online business metrics. There is no traffic here and no online half. Keeping the stage would mean reporting on something that cannot happen.

### AgentX
arXiv:2606.26859 ↗

Kuaishou, 62 authors, deployed in production. Towards Agent-Driven Self-Iteration of Industrial Recommender Systems. Four staged agents over a shared knowledge layer, plus a layer that rewrites the agents themselves.

**Attribution — the mechanism, and the example that justifies it**

Attribution here means: did the thing you changed actually cause the improvement you measured? It is a stricter question than “did the number go up”, and AgentX is built around refusing to accept the second as an answer to the first.

The mechanism runs before any code is written. The agent must first declare a policy: what it is changing, the causal mechanism it claims will produce the gain, and a set of observables — named, measurable signals with thresholds that should move if the claimed mechanism is real. The paper’s own example of an observable reads: gate activation above 0.5 after step 1000 indicates a live gate; approximately zero indicates collapse. The verification step then checks two things — that the code change semantically matches the declared direction, and that every declared observable actually appears in the code, so it can be measured at all.

Then the example that makes the case. In one round the agent added a multiplicative gate — a small learned component that scales a signal up or down. The code was correct and the score improved by +0.0003. It was rejected. The declared observable showed gate activation sitting near zero for the entire run: the standard weight initialisation made the gate’s input approximately zero, which zeroed its output and blocked gradients from flowing through it. The gate never actually fired. So whatever produced the +0.0003, it was not the gate — and crediting the gate would have taught the search a false lesson about which family of ideas works.

The next round applied a residual fix — restructuring the gate so that its default state passes the signal through unchanged rather than annihilating it. Activation recovered, every link in the causal chain checked out, and the +0.0022 was accepted and recorded.

In plain terms

You add a feature to an app and sales go up 0.3%. Then you check the logs and discover nobody ever opened the feature. Sales still went up — but not because of you, and if you file it as a win you will spend next quarter building more of something that does nothing.

Why this matters specifically for us, in numbers: run-to-run noise on this task is about 0.0008, and the improvement threshold is 0.002. A lucky, meaningless +0.0025 would clear the bar, reset the convergence counter, and drag the search into a family of ideas that does nothing — spending the remaining rounds there. The attribution check is the brake on exactly that. Our measure.py already implements the “unclear” verdict path; what is missing is the declaration of observables that feeds it.

**The state machine, and why every stage has a hard exit**

AgentX’s model-development stage is a strict sequence: declare a policy, then loop between writing code and verifying it for at most three rewrites, then run it, then a final review. Exhausting the rewrite budget fails the round cleanly rather than escalating into an open-ended repair session. Execution itself contains no model at all — it is plain code that submits a job, polls for it, and extracts metrics from the training log by pattern-matching.

In plain terms

Every stage has a defined way to give up. That sounds pessimistic and is the opposite — an agent without a hard exit condition does not fail, it hangs, and a hung agent silently eats the budget that a clean failure would have released for the next idea.

**The knowledge layer, and the one rule worth stealing from it**

AgentX maintains four separate knowledge bases: past launch reviews with their outcomes; a domain wiki about the system itself; metric definitions and statistics; and a base of papers decomposed into typed claims — problem, assumption, method, finding, limitation.

The wiki is built in three layers: a schema layer defining field types and how they relate, a wiki layer of standardised entries, and a raw-source layer linking every entry back to the code it was extracted from. That third layer is the transferable idea. An entry is trusted only because it links back to the source it came from. It is the same discipline as our rule that no state exists which is not a fold over the event log — nothing is believed on its own authority.

**How it scores its own proposals — and the surprising term**

Ideas are ranked on a weighted sum of six things: alignment with the objective, business validity, feasibility, handoff completeness, evidence drawn from the knowledge bases, minus risk. Handoff completeness is the unexpected one: a proposal is scored partly on whether it is specified well enough for the next agent to act on without having to ask a question. In a pipeline of agents, an underspecified good idea is worth less than a fully specified mediocre one, because the vagueness becomes a failure two stages later.

It also buckets ideas as ready-to-implement, probe-first, or moonshot-backlog rather than sorting them on one axis. That is a better fit for our convergence rule than a single expected-gain number, and it is the shape our reseeded bank should take.

**The decisions**

- [Adopt] An LLM may be wrong on judgment, never on an objective fact. Every metric comes from a result file, every verdict from ladder arithmetic, every priority from evidence folded over our own log. Unchanged by the pivot and the strongest single thing we have to say under a criterion judged on reasoning.
- [Adopt] Declared policy and observables, then refuse to credit an unattributed gain. Nearly free for us: if a pairwise loss works for the reason claimed, then GAUC should move more than nDCG@5 and the training loss should get worse while the ranking score improves. Both numbers are already computed — declaring them in advance is the entire cost.
- [Adopt] Hard exit conditions and a fixed rewrite budget, with execution as plain deterministic code.
- [Adopt] The source-linking discipline — the principle, not the infrastructure.
- [Adopt] Bucketing ideas rather than ranking them on one axis, and scoring a proposal partly on how completely it is specified.
- [Reject] The four knowledge bases as built. They are constructed by extractor agents over a production codebase and years of launch reviews. Our entire domain is a 700-line starter kit whose README already states its own findings. Building a knowledge base here would be infrastructure wrapped around four facts.
- [Reject] The expert panel and its two-thirds supermajority vote. Running several model instances and requiring most of them to agree is a way of buying confidence in a candidate without paying for a run. We can pay for the run — it costs forty seconds. And a panel voting on which untested candidate is better is once again a model judging something numerical.
- [Reject] SGPO, the prompt self-evolution layer. Genuinely impressive — it diagnoses a subagent’s failures in language, rewrites that agent’s prompt, and admits the edit only if replaying identical tasks scores better, taking one agent from 75.2% to 98.0% over five rounds. But one variant needs a corpus of recorded agent traces and the other needs a history of merged code changes, and both need a replay harness to verify each edit. We have none of the three and two days. GEPA below is the same idea at a fraction of the cost, and is the right thing to reach for in September.

### The verification-gap survey
arXiv:2608.05179 ↗

Autonomous Research Agents: A Survey of AI Scientists and the Verification Gap. Where the autonomy ladder at the top of this page comes from, and the source of the destination.

**What the audit found, and why it is good news for us**

The survey grades twenty-four runnable systems and reports two numbers that define the gap in its title. 83% of them release their code — but only 38% release the random seeds or execution traces needed to actually re-run what they claim, and only 38% report any method for verifying that a result is novel. Its conclusion is that code availability has stopped being the scarce thing. Evidence that a claim can be checked is what is scarce.

A seed is the number that initialises all the randomness in a training run — same seed, same result; different seed, a slightly different one. Without recorded seeds, a reported number cannot be reproduced even with the code in hand. A trace is the ordered record of what the agent actually did.

Why this is good news

Our harness is unusually well positioned against this specific critique, and by accident of design rather than intent. The run is the trace — an append-only event log, replayable, with seeds recorded per rung. We are strong on precisely the axis the survey says almost nobody is. That deserves a paragraph in the write-up citing this paper for why it matters, rather than being left as an implementation detail.

**Its failure-mode list, read as a list of things not to claim**

- The novelty-proxy gap — measuring whether an idea is new by a stand-in, such as its distance from existing papers in some embedding, rather than by actually verifying novelty.
- The compile-versus-reproduce gap — code that runs is not the same as results that reproduce. The same distinction EPR is built to expose.
- LLM-as-judge unreliability — using a language model to score outcomes, which is exactly what our numerical-honesty rule forbids.
- Absence of negative results — reported runs that contain only successes, which is a reporting artefact rather than a property of the search.

The last one is worth acting on directly: our write-up should include the rejections and the failed rounds, not just the promoted node. It costs nothing and it is the difference between a results table and a trace.

**The decisions**

- [Adopt] The ladder as the definition of “better”. It grades on who validates rather than on how much the agent does — the only framing under which our remaining work is one component instead of a wish list.
- [Adopt] Its critique as a claim to answer, and its failure-mode list as a checklist of things not to claim.
- [Reject] Any claim to L5, or to novelty. The survey is explicit that L5 is aspirational and unoccupied, and that novelty verification is the least-served part of the field. Claiming either would be exactly the overreach the paper is written to criticise.

### AIRA-2
arXiv:2603.26499 ↗

Overcoming Bottlenecks in AI Research Agents. The most design-relevant paper here, and the one that overturns a result the field had accepted.

**The result it overturns**

Some background first. Agents in this literature are measured on a benchmark of past Kaggle competitions, and scored by how often they would have won a medal. Earlier work noticed something odd: if you picked the agent’s final submission by its true score on held-out test data instead of by its validation score, medal rates rose by 9 to 13 percentage points. The field read that as the agent overfitting the validation split during its search — memorising the split it was steering by, so that its own choice of best candidate was systematically wrong.

AIRA-2’s ablations say it was mostly something else: evaluation noise. Metrics the agent reported about itself, splits that were re-drawn between runs, and outright bugs in scoring code that produced perfect validation scores regardless of input. The agent was not memorising the answer. The measuring instrument was broken.

Why this changes what we build

The two diagnoses call for opposite fixes. If the problem is overfitting, you add regularisation and hold back more data. If the problem is a broken instrument, you fix the instrument — and everything else you do is arithmetic on noise until you have. That is the same conclusion our own recalibration reaches from a completely different direction, which is a reasonable sign both are right.

**Hidden Consistent Evaluation — the three rules, and our score against them**

- One fixed split, made once, reused identically across every run. We have this — the splits are fixed date ranges, not resampled each time.
- Labels hidden from the agent. Partly. KuaiRand is public, so the test labels are physically on our disk and cannot be hidden in the cryptographic sense. What we can do — and what the plan does — is make them structurally unreachable: the adapter never writes test-dated rows to any path a candidate can read. Reachability, not secrecy.
- Scoring externalised, outside the agent’s reach. We have this, and better than most: evaluate.py is supplied by the organizers, frozen, and never edited.

Then the part that follows from all three, and the part we are missing: decouple the signals. One split steers the search; a different one selects what is finally kept. Removing this discipline costs about 13 percentile points in their measurements — the largest single effect in the paper. That decoupling is the destination at the top of this page, arrived at by a different route.

**Breadth beats depth, and by how much**

Their second finding is a scaling relationship: the compute-optimal number of agents to run in parallel grows roughly as the square root of the total budget. In plain terms — given more resources, you gain more by trying several ideas at once than by pursuing one idea further. On a task where a full training run takes forty seconds, that is a direct argument for running all three candidates rather than asking a model to pick one, and it happens to agree with the reason we already rejected NOVA’s ranking step.

**The decisions**

- [Adopt] Decoupling the steering signal from the selection signal. The destination.
- [Adopt] Breadth over sequential depth — run the candidates, do not rank them.
- [Adopt] Its diagnosis as our framing. Recalibrating the ladder is not housekeeping; it is fixing the instrument, and this paper is the citation for why that comes first.
- [Reject] Hiding labels by isolation. Their scoring runs in a separate container precisely so the agent cannot reach the labels. On a public dataset already on disk that is theatre. We get the same guarantee more cheaply and more honestly through the capability wall the runner already enforces — the candidate is handed paths, and no path it receives leads to a label it should not see.

### MLE-STAR
arXiv:2506.15692 ↗

NeurIPS 2025. Machine Learning Engineering Agent via Search and Targeted Refinement. The mechanism our loop is missing on the generation side.

**What it does differently**

Most agents ask a model what to try next. MLE-STAR instead runs an ablation over the candidate’s own code: it takes the pipeline apart block by block — the data loading, the feature construction, the model, the training loop — swaps or removes each in turn, and measures which block moves the score most. Then it concentrates the search inside that block. It is a nested loop: the outer one picks the target, the inner one explores variants of it.

In plain terms

Rather than guessing which part of the pipeline is holding you back, you find out by measurement — the same way you debug a circuit by testing each component, not by staring at the schematic and forming a theory.

This is exactly NOVA’s weak components field — the one we have no implementation of — computed cheaply and mechanically instead of being asked of a model. And it is a case where measuring is not just more honest than asking, it is also faster: on a forty-second training run, ablating four blocks costs under three minutes.

It also attacks our specific worst failure mode. Three duds in a row ends the run, and a proposal aimed at the block that measurably matters is far less likely to be a dud than one taken in order from a bank of priors.

**The decisions**

- [Defer] First in the queue if the build lands early, and the natural way to fill the weak-components gap afterwards. It is deferred purely on schedule risk, not on merit — it needs the task layer working before an ablation over blocks means anything, and that is phase 3 of 8.

### AIDE
arXiv:2502.13138 ↗

AI-Driven Exploration in the Space of Code. Machine-learning engineering as a tree search over Python scripts, where each node is a whole solution and each edge is an attempt to improve it.

**The direct ancestor of our tree**

Three operators, applied under a hard-coded policy rather than a learned one: draft a new solution from scratch, debug a broken one, or improve the best working one. The policy is a simple decision procedure — draft if there are too few solutions so far, debug if there are broken nodes still within the depth limit, otherwise improve the best non-broken node. Our tree is this design, down to the depth limit on debugging and the same vocabulary for node kinds.

Its weakness is the part we replace. AIDE picks its final answer by plain argmax — the highest-scoring node wins — with no defence against having overfit the validation split along the way. That is precisely the hole AIRA-2 diagnosed and precisely what the external oracle fills. Stating the lineage this way is useful: we are not inventing a tree search, we are adding the one thing its ancestor lacked.

**The decisions**

- [Adopt] Already adopted — the tree is this. No work required; the value is in naming the lineage in the write-up.
- [Reject] Its final-answer rule. A plain argmax over all nodes is what lets a lucky validation score win. Our selection is fixed by the competition rules as the validation-best checkpoint, but every promotion along the way is gated by the oracle — so the argmax is taken over a set that has already been filtered by something the search could not influence.

### Self-Evolving RecSys
arXiv:2602.10226 ↗

YouTube’s deployed system. End-To-End Autonomous Model Optimization With LLM Agents. Our exact domain, running in production.

**The two-loop shape**

A fast inner loop filters candidates on cheap proxy metrics; a slow outer loop validates survivors against delayed ground truth — what actually happened to users, which only becomes knowable later. An “experiment journal” carries online outcomes back to the offline agent, so it learns why a model that looked good offline failed online. Reported gains are +0.06% to +0.14% on production metrics, with roughly a hundredfold increase in experiment velocity.

Those percentages look tiny and are not. At YouTube’s scale a tenth of a percent is enormous, and it is worth internalising as calibration: in a mature recommender, real improvements are small. It is the reason this task’s improvement threshold sits at 0.002 rather than somewhere comfortable, and the reason a harness that cannot resolve small effects cannot do this work at all.

The two-loop split is the general form of what the random-exposure log buys us in miniature: a cheap signal that steers, and a more trustworthy one that confirms.

**The decisions**

- [Adopt] The two-loop shape as the mental model for what the oracle is doing, and its calibration lesson about the size of real gains.
- [Reject] The outer loop itself, and the experiment journal. Both are built on delayed ground truth from real users. We have no users, no delay and no online metrics — the random-exposure log is a static substitute for a live signal, and the substitution should be stated rather than glossed.

### GEPA
arXiv:2507.19457 ↗

ICLR 2026 oral. Reflective Prompt Evolution Can Outperform Reinforcement Learning. The affordable version of AgentX’s self-improvement layer.

**Why it is the realistic route to a self-improving harness**

A model reads its own failures, writes a diagnosis in plain language, and proposes a revised prompt. A population of prompts is kept and selected by Pareto ranking — meaning candidates are kept when nothing else beats them on every criterion at once, rather than by collapsing performance into one score and taking the top. That preserves prompts that are unusually good at one thing, which single-score selection discards.

The headline is the efficiency: it beats reinforcement learning by around 6% on average, up to 20%, while using as much as 35 times fewer rollouts — a rollout being one full attempt at a task. That efficiency is the entire reason it belongs on the roadmap when SGPO does not.

**How it differs from SGPO, since they target the same thing**

Both take a failing agent and rewrite its prompt from a diagnosis of its own failures. They differ on three axes, and only the first is decisive for us.

|  | SGPO — inside AgentX | GEPA |
|---|---|---|
| What it needs to start | A corpus you must already own. One variant needs recorded dialogue traces of the agent; the other needs a history of merged code changes, filtered to drop reformats, reverts, and diffs that are trivially small or enormous. | Nothing but the task. It generates its own failure data by attempting the task and reflecting on what went wrong. |
| How it selects | Hill-climbing on a single incumbent prompt: propose one edit, replay the same tasks, accept only if the score improves by more than a threshold. | Keeps a whole population and selects by Pareto dominance — a prompt survives if nothing else beats it on every task at once, so a prompt that is unusually good at one thing is not discarded for being average overall. |
| What the diagnosis looks like | A natural-language failure report plus a structured “semantic gradient” naming missing constraints, weak step ordering, underspecified evidence. | Natural-language reflection driving a mutation. Less structured, and it does not need to be, because selection is doing the filtering. |
| Reported result | One agent from 75.2% to 98.0% over five rounds, with legible accepted edits — make the task contract explicit, require an evidence index, standardise the candidate schema. | Beats reinforcement learning by ~6% on average and up to 20%, at up to 35× fewer rollouts. |

The difference that decides it

SGPO improves an agent by studying a record of what that agent already did. GEPA improves it by trying things. We have no record — this harness has never completed a run — so the method that needs a corpus cannot start, however good it is, and the method that generates its own can.

The Pareto selection is the second reason, and it becomes the real one later. Hill-climbing on a single prompt tends to converge on something adequate everywhere and excellent nowhere. Keeping a population preserves the specialists.

**The decisions**

- [Defer] Explicitly post-deadline. Any form of harness self-improvement needs a corpus of the harness’s own runs to learn from, and we will have exactly one. After September, with several runs recorded, this becomes the natural next build.

### MLE-bench, and FunSearch
arXiv:2410.07095 ↗

Context rather than mechanism — one supplies the measuring stick the others report against, the other supplies a principle.

**What each contributes**

MLE-bench is seventy-five Kaggle competitions packaged as a benchmark for agents. Almost every system on this page reports against it, which is why medal rates and percentile points keep appearing. Its only role here is one sentence of context in the write-up: a competition harness is a legitimate research artifact, and this is the literature that established it.

FunSearch pairs language-model generation with an executable verifier that gates on functional validity — nothing is accepted unless a deterministic checker confirms it works. It is the cleanest precedent for the principle our contract gate rests on: generation is only safe when something mechanical can reject it. Read second-hand through the survey rather than in full.

**The decisions**

- [Adopt] FunSearch’s principle as the stated justification for the contract gate.
- [Reject] Reporting against MLE-bench. Different task, different metric, no comparability. Cite it for context, never for a number.

### Terms used above

Collected, in the sense each carries on this page.

- ablation- Remove one component, re-measure, and see what it was worth. The standard way to find out which part of a system is actually doing the work.
- attribution- Whether the change you made is what actually caused the improvement you measured — a stricter question than whether the number went up.
- causal mask- A constraint stopping a model from seeing later positions in a sequence while predicting an earlier one. Omitting it lets the model see the future.
- convergence rule- This competition’s stopping condition: three consecutive rounds without an improvement greater than 0.002 and the run is declared finished.
- GAUC- A ranking-quality score computed separately for each user and then averaged, weighted by how many positive items that user had. Users with no positives or no negatives are excluded.
- gradient (as NOVA uses it)- Not numbers. A structured report — weak components, directions, forbidden — telling the search which way to move, recomputed every round.
- holdout- Data deliberately kept out of training so it can give an honest read on a model that has never seen it.
- logging-policy bias- Ordinary logs only record items the existing recommender chose to show. A model can score well on them by agreeing with that recommender rather than by predicting what users actually like.
- nDCG@5- How good the top five items are, discounted so higher positions count for more, normalised against that user’s best possible ordering. Unlike GAUC, every user counts — including those with no positives, who score zero.
- pointwise / pairwise / listwise loss- What training optimises. Pointwise scores each item alone; pairwise learns that item A should outrank item B; listwise optimises a whole ordering at once. The task is ranking, so the objective and the metric currently disagree.
- random exposure- Impressions served without the recommender choosing them. Free of logging-policy bias, which is what makes such a log usable as an oracle.
- rollout- One complete attempt at a task from start to finish. The unit of cost in prompt-evolution and reinforcement-learning methods.
- seed- The number that initialises every random choice in a run. Same seed, same result — which is why unrecorded seeds make a result unreproducible.
- sigma (σ)- Run-to-run variation from randomness alone, with nothing changed. Here about 0.0008, which sets the smallest difference that can be believed.
- smoke test- A deliberately minimal run — tiny data, short limit — that answers only “does this execute at all?”.
- within-user ranking- Ordering happens strictly inside each user’s own impressions, never across users. This is why anything constant within a user contributes exactly nothing.

Provenance note: NOVA, AgentX, the survey, AIRA-2, Self-Evolving RecSys and AIDE were read in full for the companion research page; MLE-STAR, GEPA, MLE-bench and FunSearch by abstract and search summary only, and the sections above say so where it matters. Two figures are flagged as worth checking against the PDFs before quoting — NOVA’s per-task pass rates, where the abstract and the results table disagreed on that read, and two AIRA-2 ablation rows that returned the same number, which is more likely a parsing artefact than a coincidence. The ablation column reproduced here is the one from NOVA’s results table.

## From mechanism to execution  ·  _the open questions, answered_

Each of these is a place where the page named a mechanism without saying what actually happens on the machine. They are answered in the order they bite.

### If we do not rank four candidates and run one, what do we do?

And do we still need to ground proposals in research papers, which was the component NOVA’s ablation showed mattered most after planning?

We still rank. We rank after measuring instead of before, which is a different thing from not ranking at all. The round is fully specified and costs under ten minutes end to end.

- Propose three, drawn from the bank in order of probability of clearing ε, with anything matching the forbidden store filtered out before it reaches the model.
- Each must declare its edit surface, the mechanism it claims, and its observables. A proposal missing any of the three is not a proposal — this is the one thing we keep from AgentX’s scoring, as a gate rather than a weight.
- Constraint filter and semantic gate reject before anything runs. Effectively free.
- Smoke, all survivors, sixty-second cap each. Catches crashes and divergence.
- Screen, all survivors, one seed each. Roughly forty seconds apiece — this is the step that replaces the LLM’s guess with three real numbers.
- Replicate, three seeds, only for candidates the screen advanced.
- Oracle, only for a candidate about to be promoted: score it on the random-exposure split.
- Attribute, then remember. Whatever the verdict, a lesson is written and any new forbidden pattern appended.

The trade, stated plainly

NOVA spends one LLM call to avoid three training runs. We spend three training runs — about two minutes of one CPU core — to avoid one LLM call. Their side of that trade is correct at Tencent and absurd here, and ours would be absurd at Tencent.

On the research grounding, which is the sharper half of the question: yes, we keep it, and we have already paid for it. NOVA’s paper-reproduction agent exists because the space of architecture changes at Tencent is unbounded, so the literature is what narrows it. Our space is not unbounded — the organizers enumerated it. Seven ranked untried directions, three measured dead ends, published before iteration zero.

So we keep the function of that component — every proposal carries a source it was drawn from — and drop the agent that would go and find one. The grounding corpus is a static file that already exists. That is why the ablation’s warning does not apply to us: removing grounding cost NOVA half its effectiveness, and we have not removed it, we have pre-computed it. Worth stating in exactly those words in the write-up, because on a first read it looks like we skipped the expensive component.

[diagram — see the HTML/artifact version. Labels: ONE ROUND — WHAT ACTUALLY RUNS · propose · three, by p_win · tokens · gate · rules + shapes · ~0 s · smoke · all survivors · ≤60 s each · screen · ALL of them · ~40 s each · replicate · advancers, 3 seeds · ~2 min · oracle · promotions only · ~40 s · attribute · observables moved? · learn · append · Whole round: comfortably under ten minutes of one CPU core. · NOVA's alternative in the amber box: ask a model which of four looks best, then run only that one. · It spends tokens — which we are scored on — to save forty seconds, which we are not.]

_The amber box is where the substitution happens. Everything else is machinery both designs share._

### Attribution: how do we check it, and when does it ever actually fire?

Will the change we make ever not cause the change in the results? If so, when exactly, under what circumstances — and how do we monitor for it?

Yes, and there are exactly three circumstances. They are worth separating because each has a different defence, and conflating them is how people build one mechanism and believe it covers all three.

**Circumstance one — the mechanism never fires**

The code is correct, it runs, the number moves, and the thing you built was inert the whole time. This is AgentX’s gate: correct code, +0.0003, and an activation that sat at zero all run because the initialisation happened to zero its input.

Our concrete version, and it is a real risk rather than a hypothetical. The top-ranked hypothesis is swapping pointwise log-loss for a pairwise objective, which learns from pairs of items where one was a positive and one was not. But a user can only contribute a pair if they have at least one of each. On the published test composition, 27.1% of users have no positive at all and another 9.2% are all-positive — so 36.3% of users cannot produce a single valid pair. A pairwise loss silently trains on roughly two-thirds of the user base.

That creates two different worlds with the same score. Either the gain came from pairwise ranking, which is the claim — or it came from implicitly dropping a third of the users, which is a completely different mechanism that happens to help. Without observables you cannot tell them apart, and the trajectory memory would record the wrong lesson and send the next three rounds after pairwise variants.

Measure this before trusting it

Those percentages are the test split composition as published. The equivalent numbers for train and validation must be measured, not assumed — and that measurement is about ten lines and belongs in phase 3, before the hypothesis is ever proposed.

**Circumstance two — noise**

Nothing fired and nothing broke; the number simply moved on its own. Run-to-run variation is about 0.0008, and the improvement threshold is 0.002. A single-seed comparison between two runs has a spread of roughly 0.0011, so a +0.0025 sits only about 2.2 spreads out — unremarkable enough that over dozens of rounds you should expect several.

Attribution is the wrong tool for this one. The defence is replication: averaging three seeds on each side tightens the spread to about 0.00065, and the same +0.0025 becomes nearly four spreads out. Our ladder tightens it further still by pairing each candidate seed against the same incumbent seed, and measure.py already models that correlation. This is why replication and attribution both exist and neither substitutes for the other.

**Circumstance three — a confounded change**

The gain is real and the mechanism did fire, but the diff also changed something else — a learning rate, a batch size, an epoch count — and the credit belongs somewhere other than where it was claimed. Cheapest of the three to defend: the proposal declares its edit surface up front, and the semantic gate rejects a diff that touches anything outside it.

**How we monitor, concretely**

An observables field on the hypothesis, carrying for each one: a name, how it is computed, the direction it should move, and a threshold. The candidate emits them into its result file alongside the metrics, and a require rule in the contract gate enforces that every declared observable actually appears in the code — otherwise it is a promise nobody can check. After the replicate rung, the harness compares predicted direction against measured and emits a verdict.

For the pairwise hypothesis those observables write themselves, and all three are already computed:

**O1:**   GAUC improves more than nDCG@5, in σ units
— pairwise learns order, which is what GAUC measures; nDCG@5 is top-heavy and should move less
**O2:**   training log-loss gets WORSE while primary improves
— if both improve you did not change the objective's behaviour, you found a better-tuned model
**O3:**   valid pairs per epoch > 0, and users contributing ≥1 pair is recorded
— separates “pairwise worked” from “dropping a third of users worked”

O2 is the one worth pausing on, because it is counter-intuitive and it is the strongest of the three. If you genuinely swap the objective, the old objective should get worse — you stopped optimising it. A change that improves both is a change that did not do what it said.

**What the verdict actually controls — a correction**

An earlier framing of this suggested attribution stops a noise-driven gain from resetting the convergence counter. It does not, and the distinction matters for planning.

The convergence rule belongs to the organizers and is defined on validation score improvement. An unattributed +0.0025 still resets their counter, and we do not get to redefine that. What an unclear verdict controls is everything downstream of it:

- the node does not become the incumbent that later candidates are measured against;
- its family is not credited in the queue, so it does not pull the next three proposals after itself;
- it is recorded as a gain we could not attribute, rather than as a lesson.

The first of those is the one with teeth, and it is a measurement argument rather than a narrative one. Promote an inflated baseline and every subsequent delta is measured against it — which makes real future gains look smaller than they are, at a point in the run where we have three failures of runway left. Attribution protects the measurement chain, not just the story.

[diagram — see the HTML/artifact version. Labels: replicated gain · clears the ladder · did every declared observable · move as predicted? · checked after the replicate rung · yes · no · ATTRIBUTION CLEAR · becomes the incumbent · credits the family · written into trajectory memory as a lesson · the next proposals build on it · ATTRIBUTION UNCLEAR · recorded, but does NOT become the incumbent · family not credited · search is not pulled after it · logged as "gain we could not attribute" · Either way, the organizers' convergence counter resets — it is defined on validation score, and we do not get to redefine it. · attribution governs what the search believes and builds on, not how many rounds remain]

_The dashed band is the honest boundary. Attribution is a brake on what the search believes, not on how much runway it has left._

### The knowledge layer, and the six-term score — what do we actually build?

The knowledge layer is all well and good but how do we implement it? And ideas ranked on a weighted sum of six things — I struggle to translate that to execution.

Start with what the knowledge layer is for, because the four-base architecture obscures it. It does two jobs: give a proposal evidence that it is worth trying, and stop the agent re-running something already known. Both jobs, for this task, are done by two static files totalling well under a hundred lines.

| AgentX has | Which does | Ours is |
|---|---|---|
| Experiment KB — past launches and outcomes | Stops repetition of known results | rules.jsonl, seeded with the three published dead ends |
| Model Research KB — papers as typed claims | Supplies candidate directions with evidence | bank.yaml, seeded from the organizers’ ranked untried list |
| Data Analysis — statistics, segment sizes | Checks a proposal is even measurable | the measured noise band — a proposal that cannot clear ε is not measurable |
| System KB — a three-layer wiki over the codebase | Grounds changes in how the system works | a 700-line starter kit that fits in one prompt |

The one discipline worth carrying across is the third layer of their wiki, and it costs a single field: every entry in both files names its source — a README line, the ablation script, a paper. Nothing is believed on its own authority. That is the whole idea; the infrastructure around it is what you build when your domain is a production codebase rather than seven files.

**The six-term score, translated**

Their formula weights objective alignment, business validity, feasibility, handoff completeness, evidence, and risk. Rather than implement it with six guessed weights, we ask what each term would change here, and keep only those that change something.

| Term | Verdict | Why |
|---|---|---|
| objective alignment feasibility evidence | collapse into one number | All three are asking the same question for us: will this clear 0.002? That becomes p_win, the single ordering key. Three vague terms replaced by one whose meaning is exact. |
| handoff completeness | keep — as a gate, not a weight | Does the proposal declare its edit surface, mechanism and observables? Yes or no. A boolean the contract gate enforces, with nothing to tune. This is the term we would have missed and it is the one that makes attribution possible at all. |
| risk | drop | The cascade already is the risk filter. Scoring risk and then separately gating on it counts the same thing twice, and the gate is the version that can actually stop something. |
| business validity | drop | No business. There is one number. |

Six weighted terms become one ordering key, one boolean gate, and the three buckets AgentX itself uses elsewhere — ready to implement, probe first, moonshot. Nothing to calibrate, which matters because with roughly ten rounds we could never have calibrated it.

> **ROADMAP · DECLARED, NOT BUILT**

**Knowledge Layer (beta)**

Your instinct here is right, and it is worth doing properly rather than as a hard reject. The interface is declared and named; the implementation is explicitly out of scope for this submission. Stated that way it is a strength — it shows we know the shape of what we did not build, and why.

What v2 would hold, and what each needs before it is worth building:

- Run archive — every completed run’s event log, queryable. Needs more than one run. We will have one.
- Outcome memory — which hypothesis families paid off across runs, not just within one. Needs the archive above.
- Claim store — papers decomposed into problem, assumption, method, finding, limitation, each grounded against our feature contract. Worth building only when the direction space stops being a published list of seven.
- Prompt evolution — GEPA over the archive, which is the only one of the four that changes the agent rather than its inputs.

The honest line for the write-up: three of these four are blocked on the same missing asset — a corpus of our own runs — and that asset does not exist until this submission produces the first entry in it. That is a real dependency, not a hedge, and it is a better thing to say than either claiming the layer or ignoring the question.

## Eight capabilities, scoped  ·  _theory → execution_

One owner per field is a decision about architecture. This is the same list turned into work: for each capability, the problem in plain terms, what the repository already has, the shape the code takes, and the tests that decide whether it is done. Pseudocode is indicative, not final — the names are real ones from the tree so each block has an address.

The useful surprise from reading the code with this list in hand: most of these are repairs, not builds. Six of the eight already have a seat in the harness — a constant, an unused file, a parameter with a hardcoded default, a schema that two functions disagree about. Three of them are live defects that no test currently catches. That changes the two days from “implement eight subsystems” into “connect six sockets and write the tests that keep them connected”, which is a different and far more achievable piece of work.

| # | Capability | State in the tree | New lines | Est. |
|---|---|---|---|---|
| 1 | Search topology | policy implicit | ~40 | 45 min |
| 2 | Pre-run verification | rules file orphaned | ~90 | 90 min |
| 3 | Failure memory | schema mismatch | ~35 | 40 min |
| 4 | Feedback format | unstructured | ~45 | 40 min |
| 5 | Attribution | gate wired to a constant | ~60 | 60 min |
| 6 | Numerical honesty | convention only | ~20 | 30 min |
| 7 | Evaluation integrity | PR #13 + oracle path | ~30 | 75 min |
| 8 | Where to search next | node kind reserved | ~50 | deferred |
| 9 | Overfitting monitors | nothing yet | ~55 | 50 min |
| 10 | Autonomy claim | asserted by hand | ~25 | 20 min |

Roughly seven hours of work excluding the deferred one, which is the right size for two days that also contain a dataset download, a protocol file, five open pull requests and a submission write-up. Nine and ten are scoped in the overfitting section below, where they belong.

### Capability 1 — Search topology
_state: partial · owner: AIDE_

**The problem**

A run produces many candidate solutions over two days, and something has to decide which one the next attempt builds on. The naive answer — always extend the current best — collapses into a single lineage and gets stuck the moment that lineage has a flaw near its root. The opposite naive answer — always start fresh — throws away everything learned. AIDE’s resolution is to treat the run as a tree of whole solutions and pick a move type: draft a new root, improve an existing node, or debug a broken one, under a fixed policy with a hard limit on how many times a single node may be debugged before it is abandoned.

**Where it stands**

The structure is fully present. harness/tree.py has the tree, the node states, the legal-transition check, and the three constants that encode the policy: MAX_LIVE_BRANCHES = 3, DEBUG_DEPTH = 3, and a node kind field that already admits draft, improve, debug, ablate, trial and ensemble. What is missing is the function that reads the tree and returns the next move. Right now that choice is spread across the run loop, which means it cannot be tested in isolation and cannot be replayed from the log.

**Shape**

```
# harness/tree.py — one pure function, no side effects
DRAFTS_MIN = 3          # breadth first; AIRA-2: parallelism ~ sqrt(budget)

def select(nodes, budget_left_s) -> Move:
    live = [n for n in nodes if n.state in ("running", "replicating")]
    if len(live) >= MAX_LIVE_BRANCHES:
        return Move(kind=None, parent=None, reason="at branch cap")

    drafts = [n for n in nodes if n.kind == "draft" and n.state == "promoted"]
    if len(drafts) < DRAFTS_MIN:
        return Move(kind="draft", parent=None, reason="breadth floor")

    broken = [n for n in nodes
              if n.state == "failed" and debug_depth(n, nodes) < DEBUG_DEPTH]
    if broken:
        return Move(kind="debug", parent=best(broken), reason="repair before extend")

    return Move(kind="improve", parent=argmax(promoted(nodes)), reason="extend best")
```

**Tests**

- `test_select_drafts_until_min` — Two promoted drafts and no failures yields a draft, not an improve.
- `test_select_repairs_before_extending` — A failed node under the depth limit outranks an available improve.
- `test_debug_depth_is_capped` — A node already debugged three times is abandoned rather than attempted a fourth time — the runaway-repair failure mode.
- `test_branch_cap_blocks_spawn` — Three live branches returns a null move; no fourth process is started.
- `test_select_is_a_fold` — The same node list yields the same move. Selection must be replayable from the event log, or the run is not reproducible.

**Done when:** The run loop calls select() and contains no branching of its own, and a replay of the event log reproduces the identical sequence of moves.

### Capability 2 — Pre-run verification
_state: partial · owner: NOVA_

**The problem**

A generated code change can be wrong in three quite different ways, and they cost wildly different amounts to discover. It can break a stated rule of the competition — cheap to detect with a pattern match. It can be plausible-looking but not actually implement what it claims — needs something that reads code, which means one model call. It can be syntactically fine and semantically fine and still crash on real data — only a run finds that. NOVA’s cascade orders these by cost so the expensive check only ever sees candidates that survived the cheap ones.

**Where it stands**

Level one exists in harness/agents/contract.py, with a hardcoded tuple of forbidden path fragments and five compiled leakage patterns. Level three exists as the smoke rung with its sixty-second cap. Level two does not exist at all.

**Live defect · found in the tree**

candidate/rules.jsonl holds seven declared constraints with severity, mode and pattern fields — and nothing in harness/ reads it. The only reference anywhere is a test that parses the file to confirm it is valid JSON. The constraint layer the architecture describes is real as a document and absent as a mechanism; contract.py enforces a different, hardcoded list that the rules file does not know about.

Two of the seven rules are marked "check": "llm" with a null pattern — they are the semantic level, declared and waiting for an evaluator. And C3 requires the string p_conversion_given_click, which no valid KuaiRand candidate contains, so the moment the rules file is wired up it rejects everything until that rule is retargeted at the new task.

**Shape**

```
# harness/verify.py — new, ~90 lines
def omega(diff, rules) -> list[Trip]:            # level 1 · regex · ~0 s
    for r in [r for r in rules if r.check == "static"]:
        hit = re.search(r.pattern, diff)
        if (r.mode == "forbid") == bool(hit):
            yield Trip(r.id, r.statement, r.severity)

def v_sem(diff, rules, llm) -> list[Trip]:       # level 2 · one call · ~3 s
    # asks for one boolean per statement, with the line it relies on.
    # the model judges code, never numbers — see capability 6.
    return [Trip(r.id, r.statement, r.severity)
            for r, ok in llm.judge(diff, statements(rules)) if not ok]

def cascade(diff, rules, llm, runner, node) -> Decision:
    for level, check in (("omega", omega), ("v_sem", v_sem)):
        trips = check(diff, rules, ...)
        if any(t.severity == "fail" for t in trips):
            return Decision.reject(level, trips)      # short-circuit: no run
    res = runner.run(node, "smoke", timeout_s=SMOKE_TIMEOUT_S)
    return Decision.accept() if res.ok else Decision.reject("smoke", res.failure_class)
```

**Tests**

- `test_omega_forbid_trips` — A diff reading validation click labels trips C1.
- `test_omega_require_trips` — A diff without report.progress trips C5, so the stall watchdog can never be blinded by a silent candidate.
- `test_every_require_rule_matches_the_template` — Fails today. Each require-mode pattern must match the task’s own candidate template. This is the test that catches C3 — and catches the same class of mistake automatically the next time the task changes.
- `test_v_sem_returns_booleans_only` — A parsed semantic response containing a numeric field raises rather than being used.
- `test_cascade_short_circuits` — When omega trips, the LLM call counter and the run counter are both zero. This is the entire economic argument for the cascade, so it should be asserted rather than assumed.
- `test_cascade_emits_one_event_per_level` — Every rejection is reconstructible from the log with its level and rule id.

**Done when:** rules.jsonl is the single source of constraints, contract.py’s hardcoded list has moved into it, and adding a rule to the file changes behaviour with no code change.

### Capability 3 — Failure memory
_state: partial · owner: NOVA_

**The problem**

An agent with no memory of its failures proposes the same broken idea repeatedly, and each repeat costs a full round out of a fixed budget. But an agent that treats every disappointment as forbidden quickly forbids its way into a corner. The distinction that matters is between a change that was defective — it crashed, it diverged, it quietly dropped a third of the data — and a change that was merely unhelpful in one configuration. The first should never be tried again. The second might well work later, attached to a different parent.

**Where it stands**

A memory exists. Tree._append_lesson writes a row to lessons.jsonl after every full-rung run, and researcher.propose reads the last thirty and pastes them into the prompt. The pipe is connected at both ends.

**Live defect · found in the tree**

The writer and the reader disagree about the schema. tree.py:432 writes node, family, delta, gpu_min and diff_summary. researcher.py:165 formats each row as f"- {l.get('heading','lesson')}: {l.get('text','')}" — reading two keys that are never written.

So every lesson reaches the model as the literal string - lesson: with nothing after it. The memory has been faithfully recording thirty rounds of experience and delivering thirty blank lines. Nothing fails, nothing warns, and the loop looks like it is learning. It is the exact failure the survey means by a system that appears autonomous because nobody checked what crossed the boundary.

**Shape**

```
# one schema, agreed by both sides, closed vocabulary for the defect
DEFECTS = {"crash", "diverged", "timeout",
           "silently_drops_rows", "leak_suspected", "no_gain"}

# lessons.jsonl row
{"round": 7, "node": 12, "family": "objective/pairwise",
 "pattern": "pairwise loss without a valid-pair guard",
 "defect": "silently_drops_rows", "delta": -0.0031, "verdict": "rejected"}

def forbidden(lessons) -> set[str]:              # pure fold over the log
    return {l.pattern for l in lessons
            if l.verdict == "rejected" and l.defect != "no_gain"}
    # no_gain is deliberately NOT forbidden: unhelpful once != defective.

def admissible(hyp, forbidden) -> bool:          # runs BEFORE the model is called
    return hyp.pattern not in forbidden
```

**Tests**

- `test_lesson_survives_the_round_trip` — Fails today. Write a lesson through the tree, render it through the researcher’s formatter, assert the rendered line contains the pattern. The single regression test for the defect above, and the one that would have caught it on day one.
- `test_defect_class_is_closed` — An unrecognised defect string raises rather than being silently stored, so the vocabulary cannot drift into free text.
- `test_no_gain_is_not_forbidden` — The judgement above, pinned as a test so a later edit cannot quietly turn the memory into a ratchet.
- `test_forbidden_filter_precedes_the_llm` — Proposing a forbidden pattern consumes zero tokens.
- `test_forbidden_is_a_fold` — Rebuilding from the event log reproduces the live forbidden set exactly.

**Done when:** A deliberately re-proposed defective pattern is rejected before the model is called, and the rejection is visible in the log with the round that first produced it.

### Capability 4 — Feedback format
_state: partial · owner: NOVA_

**The problem**

What one round tells the next is the highest-leverage interface in the whole system, and the tempting design — hand the model a transcript and let it work out what matters — is the one that fails quietly. Free-form history grows without bound, and a model reading it will confidently infer patterns from three noisy numbers. NOVA’s answer is to fix the shape: exactly three fields, generated by code, never by prose. Weak components, directions, forbidden. Anything that does not fit in those three fields does not cross the boundary.

**Where it stands**

harness/agents/brief.py composes a deterministic brief from the organizers’ text, which is the right instinct applied to the wrong half — the static half. The dynamic half, what the last round learned, is currently the thirty blank lesson lines from capability 3 plus a per-family statistics table.

The statistics table is worth defending, because it is already the answer to a question this page spent a long time on. Queue.score_hyp ranks the queue on (mean_delta + sd) / gpu_min — an optimism-under-uncertainty score that favours families which have done well and families we are still uncertain about, falling back to expected_gain / expected_gpu_h before any data exists. That is AgentX’s six-term weighted score, already collapsed to one key, already implemented. The translation we argued for above is not new code. It is a decision to keep what is there and not add five weights on top of it.

**Shape**

```
# harness/feedback.py — the ONLY thing a round hands the next
@dataclass(frozen=True)
class Feedback:
    weak_components: list[str]   # from ablation if run, else worst-mean-delta stage
    directions:      list[str]   # at most 3, each carrying a citation or "no prior"
    forbidden:       list[str]   # the fold from capability 3

def compose(events, lessons) -> Feedback:   # pure fold. no model involved.
    ...

def render(fb) -> str:                      # three headings, fixed order, no prose
    ...

# the researcher prompt = static brief + render(fb). nothing else from history.
```

**Tests**

- `test_render_has_exactly_three_headings` — The format is the contract; a fourth field means someone routed around it.
- `test_compose_is_deterministic` — Same events, same feedback, byte for byte.
- `test_directions_capped_at_three` — An unbounded direction list is how a fixed-shape brief becomes a transcript again.
- `test_every_direction_carries_a_citation` — Or the literal string no prior. Never blank — an unsourced direction is indistinguishable from a hallucinated one.
- `test_prompt_contains_no_raw_event_json` — Asserts the log never leaks into the prompt by another path.

**Done when:** The researcher prompt is reproducible from the event log alone, and diffing two rounds’ prompts shows only the three fields changing.

### Capability 5 — Attribution
_state: wired to a constant · owner: AgentX_

**The problem**

The score went up. Did the thing you changed cause it? These are different questions, and only the second one compounds. If a gain came from somewhere other than the stated mechanism, the lesson written into memory is false, and the next three rounds chase a mechanism that never worked. AgentX’s answer is to make the claim falsifiable before the code is written: name the mechanism, and name the observables that must move if the mechanism is real. Then check them.

**Live defect · found in the tree**

The gate is fully built and permanently open. measure.verdict takes an attribution argument, and at measure.py:398 a value of "unclear" blocks promotion with the reason replicate pass but attribution unclear. There is even a passing test for it.

But tree.py:51 reads ATTRIBUTION_HAND = "clear", and that constant is what gets passed at both call sites. Every verdict the harness has ever produced declared its attribution clear, unconditionally, before looking at anything. This is the single highest-leverage line on the page: we are not building attribution, we are replacing one constant with one function. The socket, the gate, the event field and the test all already exist.

**Shape**

```
# declared at proposal time — step 1 of the round, before any code exists
@dataclass(frozen=True)
class Claim:
    mechanism:   str
    observables: list[Observable]   # name, direction, where it is read from

def attribute(claim, before, after) -> Literal["clear", "unclear"]:
    for o in claim.observables:
        if o.name not in after:
            return "unclear"        # missing evidence is never clear. fail safe.
        if not moved_as_declared(o, before[o.name], after[o.name]):
            return "unclear"
    return "clear"

# tree.py: delete ATTRIBUTION_HAND, pass attribute(hyp.claim, inc_obs, node_obs)
```

Made concrete for the hypothesis most likely to be proposed first — swapping the pointwise loss for a pairwise one. Its three observables are all already computed or one line away:

| Observable | Must move | Why this one |
|---|---|---|
| gauc_delta > ndcg_delta | true | A pairwise objective is a within-user ordering change. If the two halves of the metric move together, whatever helped was not ordering. |
| train_logloss | worse | The counter-intuitive one, and the most diagnostic. Optimising ranking should degrade calibration. If both improve, the change did something else entirely. |
| valid_pairs_per_epoch | > 0, logged | 27.1% of users have no positive and 9.2% are all-positive, so 36.3% can form no valid pair at all. A pairwise loss silently trains on two-thirds of the users. Without this count, “pairwise worked” and “dropping a third of the users worked” are the same number. |

An unclear verdict is not a rejection. The number stands; what is withheld is promotion and the lesson. The node stays, one diagnostic is queued, and the story is settled next round rather than assumed this round.

**Tests**

- `test_all_observables_moved_is_clear` — The happy path, so the gate cannot be accidentally soldered shut in the other direction.
- `test_partial_movement_is_unclear` — Two of three observables moving is not attribution.
- `test_missing_observable_is_unclear` — Absent evidence resolves to unclear, never to clear. The direction of the fail-safe is the whole design.
- `test_attribution_is_computed_not_constant` — Fails today. Asserts no module-level attribution constant reaches a verdict. The regression test for the defect above.
- `test_unclear_blocks_promotion` — Already passing at test_05_measure_pure.py:252. Listed because it is the proof that only the computation is missing.
- `test_valid_pair_count_is_emitted` — The pairwise observable exists in the log before the pairwise hypothesis is ever run.

**Done when:** ATTRIBUTION_HAND is deleted, and at least one node in a real run carries an unclear verdict for a reason a reader can check.

### Capability 6 — Numerical honesty
_state: convention only · owner: AgentX_

**The problem**

AgentX’s rule is that a model may be wrong about judgment and never about an objective fact. It is easy to agree with and easy to violate by accident: a model estimates a gain, the estimate is stored, something later reads the field without remembering where it came from, and a guess has become a measurement. Nothing crashes. The distinction has to live in the code or it does not exist.

**Where it stands**

Observed as a convention and enforced nowhere. The distinction the repository actually needs is sharper than “models may not produce numbers”, because one model-produced number is legitimate and load-bearing: expected_gain, which is a forecast and drives queue order. A measurement is different in kind. The rule is therefore about provenance, not about floats: a model may forecast, and only the measurement layer may report.

**Shape**

```
# harness/events.py — one guard at the single choke point
MEASURED = {"delta_mean", "delta_per_seed", "band", "score",
            "gauc", "ndcg", "holdout_score", "oracle_score"}

def emit(self, type, **fields):
    if MEASURED & fields.keys() and fields.get("producer") != "measure":
        raise NumericProvenanceError(sorted(MEASURED & fields.keys()))
    ...

# forecasts stay legal and stay separate: expected_* may only appear on
# hypothesis_queued, never on a verdict. one namespace per kind of number.
```

Twenty lines, and it converts a principle into something a judge can test in one command. It also settles several arguments elsewhere on this page automatically: any design in which a model ranks untested candidates now fails at the type boundary rather than on debate.

**Tests**

- `test_agent_cannot_emit_a_metric` — An agent-sourced emit carrying delta_mean raises.
- `test_measure_can_emit_a_metric` — The permitted path still works — a guard that blocks everything is not a guard.
- `test_expected_gain_never_enters_a_verdict` — The forecast/measurement boundary, pinned. This is the test that encodes the actual rule.
- `test_every_score_in_the_log_has_a_producer` — A fold over a completed run: no orphan numbers anywhere in the record.

**Done when:** Every numeric field in a completed run traces to task.score, and the report can state that as a checked property rather than an intention.

### Capability 7 — Evaluation integrity
_state: partial · owner: AIRA-2_

**The problem**

Everything above assumes the measurement is trustworthy. If the instrument is bent, a better search finds a better way to be wrong. AIRA-2’s two contributions are that the split must be fixed and scored outside the thing being optimised, and that the signal steering the search should not also be the signal selecting the winner.

**Where it stands**

Three known gaps, all previously identified, and worth restating here as work rather than as findings.

- The holdout rung does not score the holdout. runner.py:390 passes the literal "search" to task.score for every rung. PR #13 introduces a per-rung score_split and fixes it. That merge is load-bearing for the central claim of the submission, not housekeeping.
- The capability wall blocks the oracle. runner.py:547 asserts the candidate environment is a subset of {TRAIN, VALID}, so the candidate never sees the randomly-exposed rows and emits no predictions for them. The oracle is not one extra scoring call; it needs a third path.
- The visit cap contradicts the design. HOLDOUT_VISITS_MAX = 2 against a policy of gating every promotion.

**Shape**

```
# runner.py — widen the wall by exactly one path, and make it safe by construction
assert set(task.candidate_env(paths)) <= {"TRAIN", "VALID", "ORACLE"}

# ORACLE points at a features-only CSV. labels stay harness-side and are joined
# after predictions are written, so the candidate cannot read them even in principle.

HOLDOUT_VISITS_MAX = 12          # was 2; every promotion, plus headroom
# the cap stays, and every visit still emits an event — the count is the
# adaptivity budget from Dwork et al., and it belongs in the final report.
```

**Tests**

- `test_holdout_rung_scores_holdout` — Fails on main today. Passes with PR #13 merged. The most important single test in this list.
- `test_oracle_csv_has_no_label_column` — A structural leak guard on the file itself: if a label column ever appears in the oracle features file, the run refuses to start.
- `test_candidate_env_allowlist` — The widened assertion still rejects a fourth path. Widening a wall by one is only safe if the wall is still a wall.
- `test_every_oracle_visit_emits_an_event` — The adaptivity budget is auditable from the log rather than remembered.
- `test_oracle_budget_is_enforced` — Exceeding the cap raises HoldoutBudgetExceeded rather than quietly continuing.
- `test_score_split_is_per_rung` — Screen and full still score search; only the oracle rung scores the oracle.

**Done when:** A promotion writes both numbers side by side in one event, and the pair can be read out of the log without joining anything.

### Capability 8 — Where to search next
_state: deferred, not cut · owner: MLE-STAR_

**The problem**

NOVA’s feedback format has a field called weak components and no method for computing it, which means in practice a model guesses which part of the pipeline is holding the score back. MLE-STAR’s contribution is to stop guessing: neutralise one block of the candidate’s own code at a time, re-score, and read off which block was actually carrying the result. The blocks that contribute least are the ones worth replacing. This is the only clean reason on this page to admit a second paper into an occupied field — it fills a gap the incumbent declared itself.

**Where it stands**

Reserved and unused. Node.kind already admits "ablate", and that string appears nowhere else in the harness. The seat was designed in and never sat in.

**Shape**

```
# four blocks, screen rung only, run ONCE after the first promotion
BLOCKS = ("features", "objective", "model", "training")

def ablate(node) -> dict[str, float]:
    base = screen(node)                      # ~40 s, already cached
    return {b: base - screen(neutralise(node, b)) for b in BLOCKS}
    # larger drop = more load-bearing. weak_components = the two smallest.

# cost: 4 x 40 s = under 3 min, once. not per round.
```

**Tests**

- `test_ablate_returns_one_entry_per_block` — No silent skips when a block cannot be neutralised.
- `test_ablate_uses_screen_rung_only` — Ablation must never touch the oracle. Four extra oracle visits would burn the adaptivity budget for a diagnostic.
- `test_weak_components_are_the_smallest_drops` — The sign convention, pinned — it is the easy thing to get backwards.
- `test_ablation_runs_at_most_once` — Per lineage, not per round.
- `test_ablation_result_reaches_feedback` — The output lands in Feedback.weak_components, replacing the fallback heuristic.

**Deferred if:** The eight-hour mark passes with capabilities 1–7 and 9 not all green. This is the one item on the list whose absence costs search quality rather than correctness, which is exactly what makes it the right thing to drop.

### The three we are deliberately not scoping

Two of the remaining fields get no code this iteration, and one gets twenty-five lines. Each with the reason, since a refusal without a reason is indistinguishable from an oversight.

> **BETA · SEPTEMBER**

**Agent self-improvement**

The harness editing its own prompts and policies between rounds, owned by GEPA. Declared in the interface as a panel that says what it will do and why it is dark, rather than hidden.

The honest reason it is dark: GEPA improves an agent by trying variations and keeping a Pareto front of them, which needs enough rollouts for a front to mean anything. We will have roughly ten rounds, and every one of them is also being spent on the actual task. Running an outer optimisation loop over an inner loop that has not yet completed once is the definition of premature. The alternative in the same field, SGPO, needs a corpus of recorded traces we do not have — this submission produces the first one.

What makes it viable later: a completed run with a full event log. The reason to name it now is that the log format is being designed this week, and designing it as a replayable record is what makes the September version possible at zero extra cost today.

> **FRAMING ONLY · NO CODE**

**Cheap-then-expensive validation**

Self-Evolving RecSys’s two-loop shape: a fast inner loop on a cheap proxy, a slow outer loop on the real thing. My call is that it earns no implementation, and the reason is specific rather than dismissive — we already built it. Screen and replicate are the cheap loop; oracle is the expensive one. Adding a component named after the paper would be a second mechanism doing what the rung ladder does, which is precisely the clash the arbitration rule exists to prevent.

It stays on the page as the mental model that explains why the ladder has the shape it does. A paper can pay its way as an explanation.

The third, the autonomy claim, does get code — twenty-five lines of it — and it is scoped in the next section alongside the overfitting monitors, because the two answer the same question from opposite ends: what are we entitled to say about this run when it finishes?

## Are we overfitting, and would we know?  ·  _the public-dataset problem_

Every team has the test labels sitting on their disk. That makes the usual protection — the organizers hold the answers — unavailable to everyone equally, and it turns the question from “can we cheat” into “can we demonstrate that we did not, and would we notice if we drifted?”

Two different problems hide under the word overfitting here, and they need separating before either can be answered.

| Problem | What it looks like | Our defence |
|---|---|---|
| Touching the test split a rule, not a subtlety | Reading test labels during development — as a selection signal, a diagnostic, or once out of curiosity. The problem statement puts it out of scope explicitly. | Structural, and demonstrable. The runner asserts that a candidate’s environment contains only the paths it is allowed. No path it receives leads to a test label. We can point at the assertion — which is a far stronger claim than promising we did not look. |
| Overfitting validation during the search the real risk, and it is silent | Never touching test, behaving honourably throughout, and still ending with a model tuned to the quirks of one particular validation split — because that split is what selected every promotion along the way. | Three monitors below. This is where the oracle earns its second use. |

**What the literature actually says, and it is not what you would guess**

This is a well-studied field, and — usefully for the arbitration rule — a completely vacant one from NOVA and AgentX’s point of view. Neither competes on a public leaderboard; both validate by shipping to live traffic. So admitting outside work here creates no clash with anything.

- The Ladder — arXiv:1502.04585 ↗. Blum and Hardt’s mechanism for a leaderboard that resists overfitting, and it is startlingly close to what we are already building: only report an improvement when it exceeds a threshold, and otherwise report the previous best unchanged. Withholding small movements is what stops a sequence of lucky readings from being climbed. Our ε-threshold ladder is this mechanism, and the fact that the organizers set ε at roughly 2.5 times the noise is the same reasoning. Worth citing directly — it turns our recalibration from housekeeping into an implementation of a known defence.
- Preserving Statistical Validity in Adaptive Data Analysis — arXiv:1411.2664 ↗. Dwork and colleagues on the underlying problem: once you ask a held-out set many questions and let the answers shape the next question, it stops being held out. The theory behind budgeting how often a holdout is consulted — and the reason our visit cap existed in the first place, even though it is the wrong cap for this particular split.
- Model Similarity Mitigates Test Set Overuse — arXiv:1905.12580 ↗. The reassuring counterweight: in practice, leaderboard overfitting is milder than the theory predicts, because the models people submit are highly similar to one another and so do not explore the space of ways to fit noise. Useful for calibrating how alarmed to be — the answer is “measure it, do not panic”.
- Do ImageNet Classifiers Generalize to ImageNet? — arXiv:1902.10811 ↗. Built fresh test sets for a heavily-reused benchmark. Absolute accuracy dropped substantially, but the ranking of models was almost perfectly preserved. The lesson we should carry: a score inflated by reuse can still be a valid basis for choosing between candidates. Which is exactly the position we are in.

And the fifth, which is already in the stack above: AIRA-2 is the paper that says a large part of what everyone attributed to validation overfitting was actually evaluation noise. Read together, these four-and-one point the same way — fix the instrument first, then measure the gap, and do not reach for regularisation before you have done either.

**The three monitors, in order of what they cost**

- The oracle gap. On every promotion, record the validation delta and the random-exposure delta side by side, and track the difference across the run. If validation keeps climbing while the unbiased split does not follow, that divergence is search overfitting, made visible. It costs nothing extra once the oracle is wired, which is the point worth noticing: the same build that makes the L4-v claim is also our overfitting detector. One component, two uses — that is the Pareto argument for doing it before anything optional.
- Seed consistency. Whether a promoted gain survives three seeds. At forty seconds a run this is essentially free, and it separates a real effect from a lucky draw before the effect is ever built upon.
- Rank correlation between splits. At the end of the run, check whether the ordering of the nodes by validation score matches their ordering by oracle score. Following the ImageNet result, this is the number that actually matters: if the two orderings agree, our selection was sound even if the absolute validation figure is optimistic. One line to compute from the log, and a genuinely strong thing to put in the results table.

**What to claim, and what not to**

Claim: we never read the test split, and here is the assertion in the runner that made it impossible. Claim: here is the gap between our steering signal and an unbiased one, tracked across the run, and here is the rank correlation at the end.

Do not claim: that we did not overfit validation. Nobody can claim that. Claim instead that we measured it, which is the thing the survey says almost nobody does.

**Yes, every team faces this — and that is the opening**

The question of whether everyone has the same problem has a real answer, and it is not reassuring in the direction people expect. Everyone has the labels, so nobody is protected by secrecy. Everyone is selecting on the same split, so everyone’s reported number is inflated by roughly the same unknown amount. A team that tunes hard against that split will report a higher figure than a team that does not, and honesty will not close that gap. We cannot out-score that by being careful.

What we can do is report a quantity none of them have. The random-exposure log is a second split with a different bias structure, and almost nobody builds the plumbing to use it, because it is only worth building if you already decided your claim is about the method rather than the number. Which is the claim this whole submission is making. The gap between the two splits is not a defensive disclosure — it is the measurement that the closed-loop autonomy the survey describes has no way of producing. That is the reason to spend fifty minutes here rather than on one more hypothesis.

The sharpest version

Most submissions will report a score. A few will report a score with error bars. We can report a score, its error bars, and the distance between the signal that selected it and a signal that could not have been gamed by the selection — tracked at every promotion, not computed once at the end.

### Capability 9 — Overfitting monitors
_state: absent · owner: Blum & Hardt · AIRA-2_

**The problem, stated so it can be built**

Search overfitting is not an event; it is a drift. No round is dishonest. Each promotion clears a threshold on a validation split, and the split’s particular noise gets a vote in every one of those decisions. After ten promotions the incumbent is fitted to the task and, by a small unknown amount, to that split. Nothing in the log looks wrong. The only way to see it is to hold a second measurement alongside the first and watch whether they separate.

One thing worth making explicit, because it turns an existing constant into a citation. measure.py:31 holds LADDER_ETA = 0.005 — the threshold below which an improvement is not reported as an improvement. That is precisely the Ladder mechanism from Blum and Hardt: withhold small movements, and a sequence of lucky readings cannot be climbed. We did not implement their paper; we implemented the same idea for the same reason and can now say so. The consequence is that the number of accepted ladder steps is our count of adaptive queries against the split, which is the quantity Dwork’s bound is stated in terms of. It is a number we can print.

**Shape**

```
# harness/overfit.py — three pure folds over the event log, no new runs

def oracle_gap(events) -> list[tuple[int, float]]:
    # per promotion: validation delta minus oracle delta. the trend is the signal,
    # not any single value — one promotion can diverge by luck.
    return [(e.node, e.delta_mean - e.oracle_delta)
            for e in events if e.type == "verdict" and e.state == "promoted"]

def seed_consistency(node_events) -> float:
    # fraction of the 3 seeds whose delta shares the sign of the mean.
    # 2/3 is a coin flip wearing a promotion.
    ...

def split_rank_corr(events) -> float | None:
    # Spearman between node ranking by validation and by oracle.
    # returns None below 3 promotions. undefined must not read as 0.0.
    ...

def ladder_queries(events) -> int:
    # accepted steps = adaptive queries against the split. goes in the report.
    return sum(1 for e in events if e.type == "verdict" and e.state == "promoted")
```

**What each monitor means, and what we do about it**

| Monitor | Trips when | What it means | Action |
|---|---|---|---|
| Oracle gap every promotion, free | gap widens over 3 consecutive promotions | Validation is climbing and the unbiased split is not following. This is search overfitting, made visible while there is still runway to respond. | Raise the promotion bar: require the oracle delta to be positive, not merely the validation delta. Costs nothing and cannot be gamed by the search. |
| Seed consistency every replicate, free | < 3 of 3 seeds share the sign | The gain may be a draw rather than an effect. This one catches the problem before it enters the tree, which is the cheapest possible place to catch it. | Downgrade to inconclusive and re-queue at lower priority — machinery that already exists in measure.inconclusive_next. |
| Split rank correlation once, at the end | ρ < 0.6 (n ≥ 3) | The two splits disagree about which candidates are better. Following the ImageNet retest, this is the number that actually matters: an inflated absolute score with preserved ordering still selected correctly. | Report it either way. A high correlation is the strongest single defence available; a low one is a finding worth stating plainly rather than hiding. |

**Tests**

- `test_oracle_gap_is_a_fold` — Computed from the log alone, with no run state. It must survive a crash and a resume.
- `test_gap_alarm_needs_three_promotions` — A single divergent promotion does not trip the alarm. Guards against reacting to the noise we are trying to measure.
- `test_rank_corr_returns_none_below_three` — Undefined must not silently render as 0.0 in the report — that would read as a catastrophic finding when it means no data.
- `test_seed_sign_flip_downgrades` — Two-of-three seeds resolves to inconclusive rather than promoted.
- `test_ladder_queries_matches_promotion_count` — The adaptivity budget in the report is derived, not typed.

**Done when:** The final report carries four numbers we did not have to be trusted about: the primary score, its spread over seeds, the oracle gap trend, and the number of adaptive queries that produced it.

### Capability 10 — Autonomy claim
_state: asserted by hand · owner: the survey_

**The problem**

The submission’s central claim is a rung on a ladder — that this is a loop validated from outside itself rather than one grading its own homework. A claim like that, typed into a slide, is worth nothing; it is exactly the kind of assertion the survey says the field makes without support. If it is derived from the run’s own log, it is worth quite a lot, and it costs twenty-five lines.

**Shape**

```
# harness/outputs.py — the claim is a return value, never a string in a template
def claim_level(events) -> str:
    promos = [e for e in events if e.type == "verdict" and e.state == "promoted"]
    if not promos:
        return "L3"                  # no closed loop was demonstrated
    if not all(has_oracle_reading(e, events) for e in promos):
        return "L4-m"                # mechanical: closed on its own metric
    return "L4-v"                    # validated: every promotion checked outside
```

The value of writing it this way is that it can go down as well as up. If the oracle wiring is not finished, the report says L4-m by itself, in our own words, before a judge has to work it out. A system that states a weaker claim when the evidence is weaker is making a stronger claim overall — that its claims track its evidence at all.

**Tests**

- `test_claim_downgrades_without_oracle` — A log of promotions with no oracle readings returns L4-m, not L4-v.
- `test_claim_is_derived_not_asserted` — The level appears in the report only via this function — no literal rung string anywhere in the templates.

**Done when:** Deleting the oracle events from a copy of the log changes the claim in the regenerated report.

## The read, in one screen  ·  _verdict_

The three pages are right about the destination and right about the nine gaps. Reading the code underneath them changes two things about how you get there.

The good news is bigger than the pages claim. The external oracle — the component that defines the L4-v claim — is not missing machinery. TaskPaths already carries a holdout_validation slot; measure.py already has a holdout rung with its own seed budget and event; and runner.py already refuses, by assertion, to hand a holdout path to a candidate. The oracle is a file binding plus three small unblocks, not a build.

The bad news is that it is inert today. On main, runner.py:390 scores every rung against the search split, holdout included. The holdout rung currently measures seed variance on validation and calls it a holdout. PR #13 fixes exactly this. So merging is not housekeeping you do before the real work — it is the first load-bearing step of the oracle itself.

## Why every number in the ladder is wrong  ·  _calibration_

The single most consequential fact in the pivot, drawn to scale. The harness was calibrated for a regime where noise is around 0.02. The organizers measured 0.0008 across five seeds and set ε at roughly 2.5σ.

[diagram — see the HTML/artifact version. Labels: WHAT THE HARNESS BELIEVES · 0.005 · 0.010 · 0.020 · LADDER_ETA · PROMOTE_FLOOR · SIGMA_UNSTABLE · 6.3σ · 12.5σ · 25σ · 0.0008 · 0.002 · σ, five seeds · ε, organizers · 1σ · 2.5σ · WHAT IS TRUE · every real decision lives in here]

_Logarithmic axis. Not one harness constant is inside the range where this task's decisions are actually made — the nearest is three times past ε, and the instability guard sits at 25σ, so it can never fire. REPLICATE_K = 3 is the one constant that survives: at forty seconds a run, three seeds is two minutes._

## Six things you can only see from inside the code  ·  _findings_

Each of these was verified in the tree, not inferred. Three of them change the plan; three change an estimate.

### F1 — The holdout rung does not read the holdout  ·  _changes the plan_

runner.py:390 reads metrics = self.task.score(preds, "search") — a literal, with no reference to the rung it was called for. Every rung, holdout included, is scored against the search-validation labels. The holdout rung as it stands on main retrains the candidate under three seeds and re-scores it on the split it was already selected on.

This is the foundation of the entire L4-v claim, and it is a one-line defect. PR #13 replaces it with a rung table — RUNG_SPECS["holdout"] = RungSpec(score_split="holdout", …) — and routes through spec.score_split.

**Consequence:** Merging #13 is step one of the oracle, not a chore preceding it. Until it lands, any oracle number the run reports is a validation number wearing a different label — which is precisely the self-reported-metric failure AIRA-2 is about.

### F2 — A capability wall blocks the oracle's plumbing, and it should stay  ·  _changes the plan_

runner.py:547 asserts set(task.candidate_env(paths)) <= {"TRAIN", "VALID"}, and the surrounding code strips any environment key or value containing holdout. A candidate can never be handed the oracle split. That is the property the L4-v claim needs — an oracle the search cannot game — already enforced mechanically rather than by policy.

It also means the oracle is not one extra evaluate() call. The candidate emits predictions keyed by row; task.score joins them against harness-held labels. For the oracle to score anything, the candidate must have emitted rows for the random-exposure impressions — and it cannot, because it never saw them.

**Recommendation:** Split the file in two. The oracle's features are ordinary public impressions and carry no information the logging policy can leak; its labels stay harness-side. Widen the assertion to exactly {"TRAIN","VALID","ORACLE"}, where ORACLE points at a features-only CSV with long_view stripped, and write one test that fails if that file ever contains a label column. That test is the L4-v claim, in executable form — worth more in the write-up than the prose around it.

### F3 — The visit cap contradicts “gate every promotion”  ·  _open decision_

HOLDOUT_VISITS_MAX = 2, enforced twice — measure.py:460 raises HoldoutBudgetExceeded, and tree.py:592 checks the private counter directly. The target architecture asks the oracle to gate every promotion. Those cannot both hold.

The guard was correct for what it was built for: a holdout carved out of train, small, and capable of being overfit by repeated visits — the classic reason to ration holdout looks. The random-exposure log is a different object. It is 1.18M rows collected under a different policy, it never selects the submission (the rules fix that as the validation-best checkpoint), and it only ever gates what the search keeps.

**Recommendation:** Raise the cap to the iteration budget rather than deleting the guard, and keep emitting a visit number on every measurement event. You keep the audit trail, you lose the false constraint, and the write-up can say plainly why rationing does not apply to this particular split.

### F4 — The contract gate rejects every valid KuaiRand candidate  ·  _changes the plan_

Rule C3 in candidate/rules.jsonl is a require with pattern p_conversion_given_click, severity fail. C1 forbids VALID.*(click|conversion). A correct KuaiRand candidate writes a score column and never mentions conversion, so it fails C3 on every attempt — and under the convergence rule a contract violation still burns a round.

The pages call this a rename. It is closer to a fuse: the semantic gate is not merely stale, it is inverted, and it will wedge the run in the first iteration rather than degrading quietly.

**Also missing:** No rule forbids opening the test log. The task page is explicit that this must be enforced in code rather than by discipline — and the cleanest enforcement is not a rule at all, it is the adapter simply never writing test-dated rows to a candidate-visible path.

### F5 — There is a fifth pull request, and it should be closed  ·  _estimate_

The pages count four open PRs. There are five: #11, “App batch 2: header strip + Dashboard”, +625/−72, and it is the only one reporting CONFLICTING. Its content ships inside #15, which carries batches 2 and 3. Resolving its conflicts would be work spent to land code you already have.

**Action:** gh pr close 11 with a note pointing at #15. Then the merge train is four clean PRs and no conflict resolution anywhere in the pivot.

### F6 — One missing module hides the suite, and the suite takes 12 minutes  ·  _estimate_

tests/test_07_tuner.py fails collection outright — ModuleNotFoundError: optuna — and pytest aborts the entire run before executing a single test. Excluding that one file, the measured result is 123 passed, 1 failed, 11 deselected, in 12 min 40 s; the remaining failure is test_00_skeleton::test_every_module_imports, tripping over the same missing module. So a single absent dependency accounts for both, and installing it should turn the suite green.

The twelve minutes are their own tax. Collection alone runs past two, because torch gets imported on a task whose reference pipeline is numpy-only.

**Consequence:** Until optuna is installed, “tests pass” is not a claim anyone can make without also passing --ignore. Fix it in the first hour — this is the instrument you check every phase below with, and taking torch off the candidate path shortens a loop you will run dozens of times before Tuesday.

## How the oracle actually wires up  ·  _mechanism_

The seat exists. Three things sit between it and a working external oracle, and they are the three red pins.

[diagram — see the HTML/artifact version. Labels: candidate process · template.py · sandboxed · env: TRAIN · VALID · CAPABILITY WALL · runner.py:547 — assert env ⊆ {TRAIN, VALID} · preds · row_id, score · task.score(preds, split) · joins by row_id · search labels · 0422–0428 · steers the search · oracle labels · log_random_4_22_to_5_08 · 1.18M rows · gates promotions · 1 · runner.py:390 sends every rung to "search" — PR #13 fixes · 2 · no ORACLE features → no rows to score · 3 · HOLDOUT_VISITS_MAX = 2 caps this branch at two visits]

_Labels never cross the wall in either branch — the candidate emits scores and the harness decides what they are scored against. That is why the oracle is unrunnable today and cheap once unblocked: the hard part, keeping the oracle out of the candidate's reach, was built in phase 3 and never removed._

## The sequence that follows from it  ·  _execution detail · eight phases_

The direction above decides all of this; what remains is order. Ordered by what must be true for the next phase to be checkable, not by size. Each phase ends in a gate you can actually run. Where a phase maps to a gap in the status page, the tag says so.

The capability scopes say what each piece is and how it is tested. This says when, and the two are ordered differently on purpose: scopes are grouped by architecture, phases by dependency. Evaluation integrity spans phases 1 and 3, since it is half a merge and half a new path. Verification and the candidate rules land in phases 3 and 6, where the task layer is repointed. The loop capabilities — topology, memory, feedback, attribution, provenance — land in phase 7, because they are all edits to what crosses the boundary between rounds. The monitors and the autonomy claim land in phase 8, with the run and the write-up. Capability 8 has no phase at all, which is the deliberate part: it is the item that gets dropped if the clock runs out.

---

### PHASE 1 — Make one tree that is true
29 Aug, today · ~1 h · G0

1.1

**Close #11 rather than merging it**

It is the only conflicting PR and its content ships inside #15. Closing it makes the merge train four clean fast-forwards with no conflict resolution anywhere in the pivot.

```
gh pr close 11 -c "superseded by #15 (batches 2+3)"
```

1.2

**Merge #16, then #15, then #17 — #13 closes itself**

Verified in git, not on paper: git merge-base --is-ancestor shows #13’s tip (753e9c0) is an ancestor of #16’s tip (bcea3b2) — every commit in #13 is already in #16, and #16 has exactly one commit #13 lacks. So merging #16 lands the rung → split table that phases 3 and 5 depend on and the 215-line tree.py rewrite in one move, and #13 becomes a no-op to close. (An earlier draft of this page said “#13 first”; that order is stale.) This is where F1 gets fixed.

1.3

**Repair the test instrument**

Install optuna, or guard the import and skip. One missing module currently aborts collection for the whole suite; with the tuner file excluded the pre-merge baseline measures 123 passed, 1 failed, 12 min 40 s, and that single failure has the same cause. Record the number before you merge, so the four PRs are measured against something.

**Gate:** One branch contains all four PRs, the suite runs green with no --ignore, and the post-merge count is written next to the 123.

---

### PHASE 2 — Get ground truth on disk
29 Aug, today · ~1 h · G8

2.1

**Download KuaiRand-Pure and reproduce both anchors**

Only the kit is on disk — seven files, no data. The random self-check comes first because the kit is explicit that if it misses, the harness is broken and nothing else should proceed.

```
cd ~/Downloads/kuairand-starter-kit
wget https://zenodo.org/records/10439422/files/KuaiRand-Pure.tar.gz
tar xzf KuaiRand-Pure.tar.gz
python3 baseline.py --model random   # valid 0.4834 · test 0.4753 ± 0.001
python3 baseline.py --model fm       # valid 0.6016 · test 0.5946 · ~40 s
```

This is deliverable 1 — scored work, not setup.

**Gate:** Two published numbers reproduce locally. If random misses by more than 0.001, stop and fix before anything below.

---

### PHASE 3 — Re-point the task layer
30 Aug, morning · ~3 h · G5, G7

3.1

**Write harness/tasks/kuairand.py against the existing protocol**

Task needs four methods and they are already the right four. Wrap the kit's data.load and data.encode — do not reimplement the split. row_id is the index into the split as data.load() produces it: standard log 0408–0421 first, then 0422–0508, filtered by date, file order preserved. Sort anything and --check rejects the file.

Then the line that carries the whole claim:

```
TaskPaths(
    train              = log_standard, 0408–0421,
    search_validation  = log_standard, 0422–0428,
    holdout_validation = log_random_4_22_to_5_08_pure.csv,   # ← the oracle
)
```

3.2

**Make score() delegate to the kit's evaluator**

Join preds to the split's labels by row_id, then call evaluate(user_ids, labels, scores) unmodified. Never edit evaluate.py — its header freezes every convention, and it is the definition of the score.

3.3

**Take the F2 decision deliberately**

Widen the assertion at runner.py:547 to {"TRAIN","VALID","ORACLE"}. ORACLE points at a features-only projection of the random log with long_view stripped; the labels stay in the harness-only directory beside the digests. Add the test that fails if a label column ever appears in that file.

3.4

**Delete the Ali-CCP layer and write the protocol**

Remove data/ingest.py, data/schema.py, harness/tasks/aliccp.py, protocols/aliccp.yaml — seven NotImplementedError go with them. Then protocols/kuairand.yaml, whose values are unusually all known in advance: splits are date ranges, scores ship in baseline_scores.json, and ε and N are given. Metric block becomes primary over all_impressions, positive long_view, output score; convergence epsilon: 0.002, n_rounds: 3.

**Gate:** One hand-written hypothesis runs end to end and writes a CSV that submit.py --check accepts.

---

### PHASE 4 — Recalibrate the ladder
30 Aug, afternoon · ~2 h · G2

4.1

**Measure your own σ — do not paste theirs**

Run five seeds of the ported baseline through the harness's own screen rung and take the standard deviation. Expect something near 0.0008, but the published figure describes the kit's pipeline, not yours, and the whole point of the exercise is that the number is measured rather than assumed.

4.2

**Rederive every constant from it**

Express each in σ so the arithmetic survives a remeasure. METRIC becomes "primary".

| Constant | Was | In σ | Becomes | Reasoning |
|---|---|---|---|---|
| SIGMA_UNSTABLE | 0.020 | 25σ | 6σ | A guard that can never fire is not a guard |
| PROMOTE_FLOOR | 0.010 | 12.5σ | 2σ | Lands at ε — promote what the organizers would call a win |
| SCREEN_REJECT_DELTA | −0.010 | −12.5σ | −2σ | Symmetric; screens out real losses instead of nothing |
| LADDER_ETA | 0.005 | 6.3σ | 0.002 | Match the organizers' ε exactly, not 2.5× it |
| REPLICATE_K | 3 | — | 3 | Unchanged, and now nearly free at 3 × 40 s |

4.3

**Resolve F3 — the visit cap**

Raise HOLDOUT_VISITS_MAX to the iteration budget and delete the duplicate private-counter check at tree.py:592 so the rule lives in one place. Keep emitting the visit number on every measurement event; you want the audit trail, not the ration.

**Gate:** A synthetic screen delta of +0.002 is believed and one of +0.0005 is not. Check both directions before trusting the run.

---

### PHASE 5 — Reseed the search
30 Aug · ~1.5 h · G3 — highest leverage per minute

5.1

**Restate the contract rules before anything else in this phase**

F4 first, because it wedges the first iteration. C3's require on p_conversion_given_click becomes a require on the score column; C1's forbid pattern moves from click/conversion to long_view; C2's population clause becomes within-user ranking over each user's logged impressions. C4, C5 and C6 — seed, progress, checkpoint — are task-agnostic and stay exactly as they are.

5.2

**Make the test split unreachable rather than forbidden**

A rule the agent could violate is weaker than a path it never receives. The adapter should never write test-dated rows anywhere a candidate can read. Add the static rule too, as a belt on the braces, but the enforcement is structural.

5.3

**Pre-load trajectory memory from the README**

NOVA earns its forbidden-pattern list over thousands of production rounds. The organizers published theirs before iteration zero. Seed rules.jsonl with all three as forbidden patterns tagged to round 0: static features are flat (13 fields scored 0.5940 against 0.5950 for 5); capacity is flat (k = 8/16/32 → 0.5895 / 0.5902 / 0.5887); anything constant within a user contributes exactly zero. Say this in the write-up in that vocabulary — it is a reasoning point, and reasoning is the bucket it lands in.

5.4

**Rewrite the bank, and change what it sorts on**

Eight of ten current entries aim at published dead ends and two name Ali-CCP columns KuaiRand does not have. Replace the file with the organizers' ranked untried list, loss function first. Then the subtler edit: replace expected_gain with p_win, the probability of clearing ε at all.

Under N = 3 the counter resets on any single win, so a reliable +0.004 outranks a 30%-chance +0.02 — those orderings genuinely disagree, and the bank currently encodes the wrong one. Drop expected_gpu_h while you are in the file; the denominator is wall-clock now.

**Gate:** No entry names a field KuaiRand lacks, none aims at a published dead end, and the first three by p_win are loss-function variants.

---

### PHASE 6 — Rebuild the candidate
30 Aug · ~half day · G5

6.1

**Replace template.py with the kit's FM path**

251 lines of torch, pyarrow, partitioned parquet and CUDA failure injection go. What replaces them is numpy over CSV: 1,141,112 training rows, 124,909 validation, and no GPU anywhere in the reference pipeline.

6.2

**Keep report.progress and checkpoint.save**

The stall watchdog reads progress lines, and rules C5 and C6 require both calls. Port them into the numpy training loop rather than dropping them with the torch code around them.

6.3

**Leave the dormant retry branches alone**

cuda_oom and host_oom with their batch-halving recovery will never fire on a CPU numpy pipeline; crash_code and contract_violation will carry everything. Do not delete the dormant ones. Robustness is scored on how failures are handled, not on how many occur, and a typed table with unused branches reads as coverage, not dead weight.

**Gate:** A candidate trains, writes predictions, and clears all seven contract rules without a human edit.

---

### PHASE 7 — Close the writer
30 Aug, evening · ~2 h · G1, G6

7.1

**Keep the structure, replace the schema**

Write, read back, and emit submission_written only if the read-back passes — that was the expensive decision and it survives. Only the validator's body changes: PREDICTION_COLUMNS becomes (row_id, user_id, video_id, score), the [0,1] clamp at outputs.py:72 goes, NaN and infinity are rejected. row_id is mandatory because (user_id, video_id) is not unique — 3.06% of test rows are repeated pairs, one of them twelve times.

7.2

**Delegate the read-back to submit.read_submission**

So your definition of a valid submission cannot drift from the organizers'. It needs a full data.load, so cache the split rather than reloading on every check.

7.3

**Wire ε and N in, and change the denominator**

Convergence(eps, n_rounds) already implements the organizers' rule exactly. Pass 0.002 and 3 and change nothing else inside it. Separately, swap the family-ranking denominator from gpu-min — now identically zero, which breaks the arithmetic outright — to wall-clock seconds, and add the token counter deliverable 4 needs.

**Gate:** The harness writes submission.csv unattended and submit.py --check accepts it.

---

### PHASE 8 — Run it, then write it
31 Aug · full day

8.1

**Add the negative sentinel before the first run**

A round where every candidate is rejected before training must record a negative delta and continue, not fall through. Without it the loop wedges on exactly the round where the contract gate is doing its job.

8.2

**Unpin attribution**

Add declared observables to Hypothesis, check them after the replicate rung, and feed the unclear path that measure.py:398 already implements. The top-ranked hypothesis makes this nearly free: if a pairwise loss works for the stated reason, GAUC should move more than nDCG@5 and training log-loss should get worse while primary improves. Both numbers are already computed — declaring them in advance is the whole cost.

8.3

**First run, then the clean run**

Expect to intervene on the first. Log every intervention — the count is scored directly under Autonomy, and an honest number with a typed event behind it reads better than a suspiciously round zero.

8.4

**Record the three overfitting monitors as the run goes**

All three are folds over the log rather than new machinery. Track the gap between each promotion’s validation delta and its oracle delta; keep the seed-consistency result the replicate rung already produces; and at the end compute the rank correlation between the two splits across all nodes. The first two cost nothing, the third is one line — and together they are the difference between claiming we did not overfit, which nobody can, and showing that we measured it.

8.5

**Write from the log, not from memory**

Every number in the results table is already an event. Report primary against the 0.8645 ceiling rather than against 1.0, and add the factorisation no other team will have: EPR = LPR × (1 − SFR), where a failure event is a landing failure and a rule trip is a semantic one. Lead the write-up with the L4-v position and the numerical-honesty rule.

**Gate:** A converged run with no human touch, at least one promotion carrying a positive oracle delta beside its validation delta, and --check green on the final CSV.

## If the two days compress to one

- Merge, close #11, fix the test import. Not housekeeping — PR #13 is what makes the holdout rung read the holdout at all, and without a runnable suite you cannot verify anything below it.
- Recalibrate from a σ you measured. Until then every verdict the ladder issues is arithmetic on a noise model that is off by more than an order of magnitude, and no downstream number means anything.
- Reseed the bank and restate the rules. Half an hour, and it decides whether the run reaches the loss function before three duds end it. The contract rules are inside this item, not beside it: as written, C3 fails every valid candidate on the first iteration.

The oracle is fourth. It is the destination and it is genuinely small once #13 lands — but a search that converges on noise before it reaches a real hypothesis has nothing worth validating.

Repo state read directly at b1e7193 plus the five open PR heads, 29 Aug 2026. Constants quoted from harness/measure.py lines 15–47; the scoring-split defect at runner.py:390 and its fix at origin/fix/phase-6-review:416; the capability assertion at runner.py:547; contract rules from candidate/rules.jsonl. Task figures from baseline_scores.json and the kit's file headers. Test-suite behaviour observed by running it.

Companion pages: The KuaiRand Pivot (repo status and the nine gaps), Seven Files (starter-kit teardown), The External Oracle (target architecture). Where this page disagrees with them — the oracle's cost, the PR count, the contract rules' severity — the disagreement is sourced above and comes from reading the tree rather than the plan.
