import concurrent.futures as cf
from functools import partial, wraps
import threading
import asyncio
import inspect
import traceback
import ctypes

try:
    import asyncio.runners
except ImportError:
    import genr.runners
    asyncio.run = genr.runners.run
    

_loop = None

def _arg_wrap(func):
    """ Decorator to decorate decorators to support optional arguments. """

    @wraps(func)
    def new_decorator(*args, **kwargs):
        if len(args) == 1 and len(kwargs) == 0 and callable(args[0]):
            return func(args[0])
        else:
            return lambda realf: func(realf, *args, **kwargs)

    return new_decorator


@_arg_wrap
def genr(func, timeout=None, clean_up=None):
    @wraps(func)
    def wrapper(*args, **kwargs):
        thread = threading.current_thread()
        thread.collector = getattr(thread, "collector", set())
        executor = GenrThreadPoolExecutor()
        if inspect.iscoroutinefunction(func):
            gen = _asyncio_wrapper(func, *args, **kwargs)
        elif inspect.isgeneratorfunction(func):
            gen = func(*args, **kwargs)
        else:
            gen = _func_wrapper(func, *args, **kwargs)
        if timeout is not None:
            complete_event = threading.Event()
        else:
            complete_event = None
        future = executor.submit(_gen_runner, complete_event, gen, clean_up)
        thread.collector.add(future)
        executor.shutdown(wait=False)
        if timeout is not None:
            threading.Thread(
                target=partial(_timeout_waiter, complete_event, timeout, future)
            ).start()
        return future

    return wrapper


@_arg_wrap
def genr_sync(func, timeout=None):
    @wraps(func)
    def wrapper(*args, **kwargs):
        future = genr(timeout)(func)(*args, **kwargs)
        future.result()
        return future

    return wrapper


def _gen_runner(gen, clean_up):
    thread = threading.current_thread()
    thread.collector = getattr(thread, "collector", set())
    first_round = True
    prev_value = None
    try:
        while True:
            if first_round:
                value = next(gen)
                first_round = False
            else:
                value = gen.send(prev_value)
            for future in cf.as_completed(thread.collector):
                future.result()
            thread.collector.clear()
            if type(value) is GenrFuture:  # cf.Future:
                prev_value = value.result()
            elif type(value) in (tuple, list, set) and all(
                (type(elem) is GenrFuture for elem in value)
            ):
                prev_value = type(value)([future.result() for future in value])
            else:
                prev_value = value
    except StopIteration as stop:
        for future in cf.as_completed(thread.collector):
            future.result()
        thread.collector.clear()
        return stop.value
    except cf._base.TimeoutError:
        for future in thread.collector:
            if not future.cancel() and not future.done():
                future.stop()
        thread.collector.clear()
        if clean_up is not None:
            clean_up()
        raise

def _func_wrapper(func, *args, **kwargs):
    return (yield func(*args, **kwargs))

def _timeout_waiter(complete_event, timeout, future):
    if not complete_event.wait(timeout):
        future.stop()

def _asyncio_wrapper(coro, *args, **kwargs):
    return (yield asyncio.run(coro(*args, **kwargs)))
    '''
    loop = asyncio.new_event_loop()
    try:
        return (yield loop.run_until_complete(coro(*args, **kwargs)))
    finally:
        loop.close()
    '''


# ----- Adjustments to concurrent.futures


class _GenrWorkItem(cf.thread._WorkItem):
    """ Subclassed to set an additional
    attribute `thread` on the Future object
    while the work item is executing. This
    facilitates stopping the execution on
    request. """

    def __init__(self, future, fn, complete_event, args, kwargs):
        super().__init__(future, fn, args, kwargs)
        self.complete_event = complete_event
        self.future.thread = None

    def run(self):
        if not self.future.set_running_or_notify_cancel():
            return

        try:
            self.future.thread = threading.current_thread()
            result = self.fn(*self.args, **self.kwargs)
        except BaseException as e:
            self.future.set_exception(e)
        else:
            self.future.set_result(result)
        finally:
            if self.complete_event is not None:
                self.complete_event.set()
            self.future.thread = None


class GenrFuture(cf._base.Future):
    """ Subclassed to add a method for
    stopping the execution of the future. """

    def stop(self):
        try:
            if not self.thread.isAlive():
                return

            # exc = ctypes.py_object(SystemExit)
            exc = ctypes.py_object(cf._base.TimeoutError)
            res = ctypes.pythonapi.PyThreadState_SetAsyncExc(
                ctypes.c_long(self.thread.ident), exc
            )
            if res == 0:
                raise ValueError("Nonexistent thread id")
            elif res > 1:
                ctypes.pythonapi.PyThreadState_SetAsyncExc(thread.ident, None)
                raise SystemError("PyThreadState_SetAsyncExc failed")
            return True
        except AttributeError:
            return False


class GenrThreadPoolExecutor(cf.thread.ThreadPoolExecutor):
    """ Subclassed to use modified Future and 
    WorkItem on `submit`. """

    def submit(self, fn, complete_event, *args, **kwargs):
        with self._shutdown_lock:
            if self._shutdown:
                raise RuntimeError("cannot schedule new futures after shutdown")

            f = GenrFuture()  # cf._base.Future()
            w = _GenrWorkItem(f, fn, complete_event, args, kwargs)

            self._work_queue.put(w)
            self._adjust_thread_count()
            return f

    submit.__doc__ = cf._base.Executor.submit.__doc__


__all__ = genr, genr_sync


# _______ Queuing helper class and decorator

def queued(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        task = partial(func, *args, **kwargs)
        args[0].queue.put(task)
    return wrapper


class QueueControl:

    def __init__(self):
        self.queue = queue.Queue()
        self._queue_runner()

    @genr
    def _queue_runner(self):
        while True:
            try:
                task = self.queue.get()
                task()
                if task.func.__name__ == 'stop':
                    break
            except Exception as e:
                logging.exception(e)
        yield 

    @queued
    def stop(self):
        pass


if __name__ == "__main__":

    import time, requests, bs4

    @genr_sync
    def main():
        try:
            login()
            weather = yield get_weather()
            print(f"Weather is {weather}")

            results = yield [
                fetch(url)
                for url in (
                    "https://python.org",
                    "http://omz-software.com/pythonista/",
                    "https://pypi.org",
                )
            ]
            print("Retrieved pages:", results)

            waiting_for_weather = get_weather()
            waiting_for_result = genr(lambda url: requests.get(url).text)(
                "https://iki.fi"
            )

            print("Is the weather still", waiting_for_weather.result())

            result = (yield waiting_for_result)
            print("Result:", result[:40])

            results = yield [
                genr(lambda url: requests.get(url).text[:20])(url)
                for url in ("https://python.org", "https://pypi.org")
            ]
            print(results)
            # clean_up()
            yield
            print((yield asyncio_waiter()))
            logout()
        finally:
            print("clean up")
            time.sleep(2)

    @genr
    def login():
        time.sleep(1)
        print("Logged in")
        # raise Exception('Testing exception')

    @genr
    def get_weather():
        time.sleep(0.5)
        return "fine"

    @genr(timeout=5)
    def fetch(url):
        text = requests.get(url).text
        soup = bs4.BeautifulSoup(text, "html.parser")
        title = soup.find("title")
        return title.string

    @genr
    async def asyncio_waiter():
        print('asyncio starts')
        await asyncio.sleep(1)
        return 'asyncio is done'

    @genr
    def crash():
        raise RuntimeError("Some hassle")

    @genr
    def clean_up():
        try:
            crash()
        finally:
            print("Cleaning up")

    def logout():
        print("Logged out")

    main()
