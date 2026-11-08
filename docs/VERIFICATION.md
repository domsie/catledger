# Verification record (8 November 2026)

This record describes the tests **actually run during initial authoring**. It must not be confused with a public CI result, a professional security audit or real-world usability evidence.

## Environment

- Linux container, CPython 3.13.5.
- Python standard-library `unittest` runner; test source under `tests/`.
- Input fixtures are synthetic and free of customer/personal data.

## Executed checks

1. `PYTHONPATH=src python -m unittest discover -s tests -p 'test_*.py'` — **76 tests passed**.
2. The randomized oracle test generated **100 valid small synthetic jobs** and compared every feasible result of the exact solver to a deliberately independent exhaustive enumeration; infeasible jobs were checked for explicit rejection. Deterministic random seed `20261108`. This is one unittest method, not 100 separately reported unittest cases.
3. `python -m pip wheel --no-deps --no-build-isolation -w ... .` — created a `catledger-0.1.0-py3-none-any.whl` distribution successfully.
4. Installed the wheel using `pip install --no-index --no-deps --target ... catledger` and ran the installed module against the synthetic workshop fixture.
5. Ran `python -m catledger verify` on the generated plan — output `"valid": true` with objective values matching the generator.
6. A saved golden plan at `examples/expected-workshop.plan.json` is checked in the test suite and by the proposed CI workflow.

## Verified sample result

For `examples/workshop.json` in exact mode:

- New material cost: **1,180 cents**.
- Used stock: **4 units** (two new 2,100 mm boards and two already-owned 1,300 mm offcuts).
- Unrecoverable length: **302 mm** under the documented kerf/trim/offcut convention.
- Total unused length: **579 mm**, of which 343 mm meets the reuse threshold.
- Saved plan verifies against the canonical job fingerprint and quantity/dimension constraints.

## Not verified

- **No hosted GitHub Actions runs** were executed at the time of this record; the repository was not yet published.
- **No Windows or Python 3.11/3.12 runs** were executed locally. The CI matrix is proposed for verification once uploaded.
- No external users, installation counts, workshop deployment, performance benchmark at scale, or machining safety certification are claimed.
- The output verification checks physical consistency and supplied metadata, not the mathematical proof behind the solver's `proven_optimal` claim.
