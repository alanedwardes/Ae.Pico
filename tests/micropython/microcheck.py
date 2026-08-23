failures = []

def check(label, cond, detail=''):
    if cond:
        print('PASS', label)
    else:
        print('FAIL', label, detail)
        failures.append(label)

def summarize():
    print()
    if failures:
        print('FAILURES:', failures)
        raise SystemExit(1)
    print('ALL CHECKS PASSED')
