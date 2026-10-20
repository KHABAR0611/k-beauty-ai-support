"""Frozen generalization evaluation with unchanged fact/source/status rubric."""
import sys
from evaluate_mvp import main
if __name__=='__main__':
    try:raise SystemExit(main(corrective=True,generalization=True))
    except Exception as exc:
        print('evaluation_failed category='+type(exc).__name__,file=sys.stderr)
        raise SystemExit(2)
