import functools
from concurrent.futures import ThreadPoolExecutor

executor = ThreadPoolExecutor(max_workers=50)


def run_in_thread(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        executor.submit(func, *args, **kwargs)

    return wrapper
