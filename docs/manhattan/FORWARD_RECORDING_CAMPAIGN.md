# Manhattan forward recording and million-executable campaign

Owner direction, 25 November 2026. This plan supersedes the earlier million-algorithm checklist. Protocol v3.1 and simulation preregistration v2 govern evidence. This document records sequence and scope. Activation, freezes, protocol amendments, data permissions, and spending follow the existing owner approval process.

## Outcome

Start recording blinded paper predictions as soon as the recording path is authorized and verified. Then use a campaign of one million unique executables to feed successive batches. A campaign can finish with zero qualifying candidates. Historical performance is useful for filtering candidates under approved rules. Confirmation for the currently documented markets comes from forward observations.

## 1. Finish integration and verify attempt accounting

- [ ] Complete independent reviews and CI on the live commits for #106, #107, #110 and #111. Land #106 before retargeting #107 to main. Review the other fixes in parallel under their own gates.
- [ ] Run synthetic First Light from main in separate processes. Compare result hashes, the attempt census, and reports. Verify restart and recovery behavior.
- [x] Base binding attempt accounting is on main through [#86](https://github.com/EthanC100/em-macro/pull/86). Its supported APIs bind protected reads to registered attempts and provide transactional result/terminal handling. See [binding accounting](BINDING_ACCOUNTING.md).
- [ ] Independently verify the production paths before using them. Show that the runner binds the verified configuration, frozen executable, allowed data and window to one durable start before protected access. Check atomic results and terminal records, observation provenance and completeness, crash recovery, locking and reconciliation. Choose authoritative ledger and independent anchor custody. Verify the historical campaign's own accounting path. Open exploration and HTE registration are separate from #86's protected paths, and D-10 is open. Record the applicable owner decisions before wiring it. See [HTE accounting decisions](hte_accounting/DECISIONS.md).

## 2. Advance two tracks in parallel

### Validate the statistical methods

- [x] The development workflow [43467828524](https://github.com/EthanC100/em-macro/actions/runs/43467828524) assembled and uploaded a [combined artifact](https://github.com/EthanC100/em-macro/actions/runs/43467828524/artifacts/14116817108). The [collector](https://github.com/EthanC100/em-macro/actions/runs/43467828524/job/132469519409) failed its completeness check. The D04h STD piece covering replication IDs 6–203 exited before finishing and uploaded a partial result. Completion and criterion review have yet to be verified.
- [ ] Recover the artifacts, inventory missing replications and code identities using the [runbook](SIM_RUNBOOK.md), and resume the compatible missing work. Check the HB code-identity impact of the merged ledger changes before combining or rerunning evidence. Record the disposition of every incompatible shard.
- [ ] Evaluate the full development results against every preregistered criterion, including D08 calibration. Keep posterior-based tiers and dormancy inactive if the applicable validation fails. Document any development correction through the existing protocol and preregistration process.
- [ ] Implement the preregistered held-out scenarios, perform the tagged confirmation run under the existing owner-controlled process, and apply the published selection and failure rules. Record the method decision and its evidence before enabling the applicable statistical screening, promotions, tiers or claims. See [simulation preregistration v2](SIM_PREREG_v2.md) and [Protocol v3.1](PROTOCOL_v3.1.md).

### Prepare early forward recording

- [ ] Prepare an always-on paper runner on an owner-approved host. Give write/read credentials by role and keep ledger, raw data and performance keys outside agent and app custody. Verify restart, checkpoints, observation timestamps, gap handling, capture integrity and reconciliation. Test that outcome access is denied to hypothesis authors and the owner in the freeze role.
- [ ] Have Claude prepare the first 10–20 economically reasoned families with fixed predictions and variant grids. Tag each family with its actual channel. A family prepared outside the isolated blind environment is adaptive and has zero evidential weight on reserve history under the current protocol.
- [ ] Once the owner approves the recording-only route and its operational safeguards pass, the owner freezes the batch before its first prediction. Start recording future observations as soon as the authorized route works. Keep the forward performance sealed, record provenance and eligibility, and retain the complete chronological record for later evaluation under the validated protocol. Do not wait for the million-run campaign to finish. Reserve, claims and real-money settings require their separate existing gates.

## 3. Design and benchmark the historical campaign

- [ ] Define the one million as unique executable configurations. Keep stable identities and versioned mappings from mechanism/family to variants to executables, windows and attempts. Track submitted, duplicate, rejected, completed, failed and retried items distinctly. A million executions is a compute target. Scientific evidence remains governed by the protocol's family and variant rules.
- [ ] Keep NT-8/D-1 undecided pending an approved preregistered reconciliation. Identify cross-track dependencies and how inherited results and attempts enter the accounting. Record `p ≤ 0.01` only as an owner-preferred descriptive flag where access and reporting rules allow. A change to a decision threshold, denominator, or correction procedure requires the appropriate formal process.
- [ ] Audit the chosen dataset for prior use by humans, models and automated jobs. Treat the previously used 2020–September 2026 currency, government-bond and commodity-futures window, and earlier development windows, as historical screening material in accordance with the owner-endorsed review. A new instrument or provider alone does not establish independence. Document any genuinely unused candidate window and the remaining model-exposure limitations before making any claim about it.
- [ ] Preregister the staged screen within the governing protocol, including data rights, point-in-time rules, costs, benchmarks, capacities, rejection rules and bias checks. After explicit authorization and read-path verification, run a small engineering data pilot and benchmark representative executables. Keep pilot outputs within their restricted role. Use measured throughput and cost to set compute capacity.
- [ ] Once the simulation and applicable screening gates clear, run the million-executable campaign as a screen. Apply frozen criteria and account for all attempts. Send eligible survivors into successive owner-frozen forward batches. Independently reproduce each advance and verify its specification, data, code and ledger provenance. Forward observations provide confirmation under the validated protocol.

## 4. Build a blinded app

- [ ] Start with synthetic fixtures and a read-only operational projection. Show queue and runner health, frozen-spec and family counts, executable and attempt counts, coverage and workflow status. Explain each algorithm from its frozen hypothesis, rules, assumptions and parameters. Show provenance and gate status, including pending/disabled evidence tiers.
- [ ] Keep return rankings, candidate performance, p-values, and unreleased outcome-driven promotion information behind the evidence release policy. Before validation the app must not expose these through charts, endpoints, exports, logs or summaries. Apply the same blinding to the owner's freeze role and to all agent input.
- [ ] After validation and release approval, restrict performance views to authorized review of frozen finalists. Log each access to unpublished results. Keep the outcome-bearing role separated from anyone approving or generating later blind batches. Test access boundaries and audit records before opening the views.

## Responsibilities

Claude owns hypothesis and investment-algorithm design. Codex owns infrastructure, testing, implementation support and independent review. Ethan owns freezes, access and activation decisions, and any change to the statistical protocol.
