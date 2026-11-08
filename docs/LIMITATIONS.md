# Current limitations and safety boundaries

- One dimension only: **not** a panel-nesting, 2D, angled-mitre, grain-direction, cross-section, or load-bearing design program.
- Kerf is modelled as one cut per part. This is a conservative planning convention; actual cutting sequences, machine setup and end-piece assumptions may vary.
- End trims reduce capacity; the software assumes the stock IDs represent homogeneous material and does not prevent mixing incompatible widths, species or strengths.
- No formal proof of safety or suitability for machining. Human verification is required.
- Exact optimality is restricted to small, bounded instances; heuristics are not completeness or quality guarantees.
- Material costs are user-supplied integer cents, not price quotations. A zero-cost offcut is an accounting assumption, not an appraisal.
- Reusable offcuts are reported but not yet persisted as a separately reconciled inventory, serialized with physical IDs, or automatically carried into a subsequent job.
- No multi-user concurrency or automated backups. There is no file-watcher or background worker.
- Input validation caps job size. Unexpectedly large or malformed JSON will be rejected rather than automatically scaled.
- Synthetic samples and tests do not imply production use, releases, external adopters or historical maintenance.
