This folder is the output destination for generated artefacts:

  benchmark_report.txt   - written by `python run_benchmark.py`
  faults.db              - written by `python -m ospf_engine.reasoning.kb_sqlite snapshot`
  report_*.txt           - written by `python run_benchmark.py --save-detailed`

These files are regenerated on demand and are listed in .gitignore.
