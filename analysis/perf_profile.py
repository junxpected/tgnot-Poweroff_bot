from __future__ import annotations

import cProfile
import pstats
import tracemalloc
import sys
from pathlib import Path
from time import perf_counter

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from services.address_lookup import AddressLookup


def benchmark_lookup(lookup: AddressLookup, iterations: int = 5000) -> tuple[float, int]:
    samples = [
        ("Рівне Київська", "12"),
        ("Томахів", "1"),
        ("Рівне Шевченка", "7"),
        ("Невідома", "99"),
    ]

    found = 0
    start = perf_counter()
    for i in range(iterations):
        street, house = samples[i % len(samples)]
        result, err = lookup.find_queue(street, house)
        if err is None and result is not None:
            found += 1
    elapsed = perf_counter() - start
    return elapsed, found


def main() -> None:
    lookup = AddressLookup()

    tracemalloc.start()
    t0 = perf_counter()
    lookup.load()
    load_time = perf_counter() - t0
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    print(f"load_time_sec={load_time:.4f}")
    print(f"rows_city={len(lookup.city_rows)} rows_region={len(lookup.region_rows)}")
    print(f"memory_current_kb={current / 1024:.1f} memory_peak_kb={peak / 1024:.1f}")

    profiler = cProfile.Profile()
    profiler.enable()
    elapsed, found = benchmark_lookup(lookup)
    profiler.disable()

    print(f"lookup_iterations=5000 elapsed_sec={elapsed:.4f} found={found}")
    stats = pstats.Stats(profiler).sort_stats("cumtime")
    print("top_functions:")
    stats.print_stats(10)


if __name__ == "__main__":
    main()
