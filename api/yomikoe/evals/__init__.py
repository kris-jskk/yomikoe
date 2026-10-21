"""Eval layer (D31-D34): scored suites over fixed datasets, run records and compare.

``python -m yomikoe.evals run <suite ...|all>`` writes one record under ``evals/runs/``;
``python -m yomikoe.evals compare A B`` prints the scorecard between two records. Gate tests
keep their thresholds; evals keep every per-example score (D31).
"""
