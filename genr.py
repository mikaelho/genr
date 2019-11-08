
import concurrent.futures as cf
from functools import partial, wraps
import threading, inspect, traceback

def genr(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        thread = threading.current_thread()
        thread.collector = getattr(thread, 'collector', set())
        executor = cf.ThreadPoolExecutor()
        if inspect.isgeneratorfunction(func):
            gen = func(*args, **kwargs)
        else:
            gen = _func_wrapper(func, *args, **kwargs)
        future = executor.submit(_gen_runner, gen)
        thread.collector.add(future)
        executor.shutdown(wait=False)
        return future
    
    return wrapper
    
def _func_wrapper(func, *args, **kwargs):
    yield
    return func(*args, **kwargs)

def _gen_runner(gen):
    thread = threading.current_thread()
    thread.collector = getattr(thread, 'collector', set())
    first_round = True
    prev_value = None
    try:
        while True:
            if first_round:
                value = next(gen)
                first_round = False
            else:
                value = gen.send(prev_value)
            for future in cf.as_completed(thread.collector): pass
            thread.collector.clear()
            if type(value) is cf.Future:
                prev_value = value.result()
            elif (
                type(value) in (tuple, list, set) and
                all((type(elem) is cf.Future for elem in value))
            ):
                prev_value = type(value)([future.result() for future in value])
            else:
                prev_value = value
    except StopIteration as stop:
        for future in cf.as_completed(thread.collector): pass
        thread.collector.clear()
        return stop.value
    except Exception as e:
        traceback.print_exc()
        raise

def wait_for(future):
    future.result()

if __name__ == '__main__':
    
    import time, requests, bs4
    
    @genr
    def main():
        login()
        weather = yield get_weather()
        print(f'Weather is {weather}')
        
        results = yield [fetch(url)
            for url in (
                'https://python.org',
                'http://omz-software.com/pythonista/',
                'https://pypi.org'
            )]
        print('Retrieved pages:', results)
        
        waiting_for_weather = get_weather()
        waiting_for_result = genr(lambda url: requests.get(url).text)('https://iki.fi')
        
        print('Is the weather still', waiting_for_weather.result())
        
        result = (yield waiting_for_result)
        print('Result:', result[:40])

        results = yield [
            genr(lambda url: requests.get(url).text[:20])(url)
            for url in (
                'https://python.org',
                'https://pypi.org'
            )]
        print(results)
        logout()
    
    @genr
    def login():
        time.sleep(1)
        print('Logged in')
        #raise Exception('Testing exception')
        
    @genr
    def get_weather():
        time.sleep(0.5)
        return 'fine'
        
    @genr
    def fetch(url):
        text = requests.get(url).text
        soup = bs4.BeautifulSoup(text, 'html.parser')
        title = soup.find('title')
        return title.string
        
    def logout():
        print('Logged out')
        
    wait_for(main())
