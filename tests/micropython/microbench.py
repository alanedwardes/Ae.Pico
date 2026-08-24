import time
import gc

def _warm(fn, ms=300):
    t0 = time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(), t0) < ms:
        fn()

def bench(label, fn, min_ms=100, repeat=5):
    _warm(fn)

    iters = 1
    while True:
        t0 = time.ticks_us()
        for _ in range(iters):
            fn()
        elapsed = time.ticks_diff(time.ticks_us(), t0)
        if elapsed >= min_ms * 1000:
            break
        iters *= 2

    best = None
    total = 0
    for _ in range(repeat):
        t0 = time.ticks_us()
        for _ in range(iters):
            fn()
        elapsed = time.ticks_diff(time.ticks_us(), t0)
        total += elapsed
        if best is None or elapsed < best:
            best = elapsed

    gc.collect()
    before = gc.mem_alloc()
    fn()
    alloc = gc.mem_alloc() - before

    best_us = best / iters
    mean_us = total / (repeat * iters)
    print('%-40s best %10.1f us  mean %10.1f us  alloc %6d B' % (label, best_us, mean_us, alloc))
    return best_us

def compare(label_a, fn_a, label_b, fn_b, batch_ms=5, rounds=100):
    _warm(fn_a)

    iters = 1
    while True:
        t0 = time.ticks_us()
        for _ in range(iters):
            fn_a()
        if time.ticks_diff(time.ticks_us(), t0) >= batch_ms * 1000:
            break
        iters *= 2

    def batch(fn):
        t0 = time.ticks_us()
        for _ in range(iters):
            fn()
        return time.ticks_diff(time.ticks_us(), t0)

    a_us = 0
    b_us = 0
    half = rounds // 2
    for i in range(rounds):
        if i < half:
            a_us += batch(fn_a)
            b_us += batch(fn_b)
        else:
            b_us += batch(fn_b)
            a_us += batch(fn_a)

    n = rounds * iters
    a_per = a_us / n
    b_per = b_us / n
    print('%-24s %8.2f us  vs  %-24s %8.2f us  (b/a: %.3f)'
          % (label_a, a_per, label_b, b_per, b_per / a_per))
    return a_per, b_per