# Cache-layout byte witnesses

The former EvoBench runtime suite was retired in v16.0.0. This location is
witness-only: `baselines/` contains exactly the ten immutable
`layout_invariant_v*.yaml` files required by A-2.4.

Historical EvoBench JSON baselines and optimization history are archived under
`docs/cycle-archive/v15.2.0/evobench-baselines/`. They are evidence, not live
runtime inputs, and must not be copied back into `baselines/`.

Verify the witnesses with:

```bash
python -m pytest tests/test_layout_invariant_multi_baseline.py -v
```
