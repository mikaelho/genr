import unittest, time, threading, concurrent.futures, asyncio

from genr import genr, genr_sync


class TestBasics(unittest.TestCase):
    
    @genr
    def small_wait(self):
        time.sleep(0.1)
        
    @genr
    def longer_wait(self):
        time.sleep(0.3)

    def test_simple_run(self):
        future = self.small_wait()
        self.assertTrue(future.running())
        time.sleep(0.2)
        self.assertTrue(future.done())
        
    def test_inline_wrap(self):
        future = genr(time.sleep)(0.1)
        self.assertTrue(future.running())
        time.sleep(0.2)
        self.assertTrue(future.done())
        
    @genr
    def generator1(self):
        yield
        
    def test_generator_run(self):
        future = self.generator1()
        self.assertTrue(future.done())
        
    @genr
    def simple_return(self):
        return 'value'
        
    def test_return_value(self):
        self.assertTrue(
            self.simple_return().result() == 'value')
        
    @genr
    def yield_aggregates(self, aggr_type=None):
        if aggr_type is not None:
            tasks = [self.simple_return() for i in range(3)]
            result = yield aggr_type(tasks)
        else:
            result = yield self.simple_return()
        return result
        
    def test_yield_values(self):
        self.assertTrue(self.yield_aggregates().result() == 'value')
        for aggr_type in (tuple, list, set):
            values = self.yield_aggregates(aggr_type).result()
            self.assertTrue(type(values) == aggr_type)
            self.assertTrue(len(values) == 3 or (aggr_type == set and len(values) == 1))
            self.assertTrue('value' in values)
        
    @genr
    def delayed_yield(self):
        future = self.simple_return()
        yield
        value = yield future
        return value
        
    def test_delayed_yield(self):
        self.assertTrue(self.delayed_yield().result() == 'value')
        
    @genr
    def yield_something_else(self):
        value = yield 'value'
        return value
        
    def test_yield_something_else(self):
        self.assertTrue(self.yield_something_else().result() == 'value')
        
    @genr
    def generator2(self):
        checks = []
        t1 = genr(time.sleep)(0.1)
        t2 = genr(time.sleep)(0.2)
        checks.append(not t1.done())
        checks.append(not t2.done())
        yield
        checks.append(t1.done())
        checks.append(t2.done())
        return checks
        
    def test_yield_as_a_collection_point(self):
        checks = self.generator2()
        self.assertTrue(all(checks.result()))

    @genr
    def generator3(self):
        checks = []
        futures = []
        t1 = genr(time.sleep)(0.1)
        yield
        t2 = genr(time.sleep)(0.1)
        t3 = genr(time.sleep)(0.2)
        checks.append(not t2.done())
        checks.append(not t3.done())
        futures.append(t2)
        futures.append(t3)
        return checks, futures

    def test_return_as_a_collection_point(self):
        future = self.generator3()
        checks, futures = future.result()
        self.assertTrue(all(checks))
        for f in futures:
            self.assertTrue(f.done())

    @genr
    def error_raiser(self):
        raise TypeError()
        
    @genr_sync
    def main_for_error_raiser(self):
        self.error_raiser()
        yield
        return True

    def test_exception_visibility(self):
        with self.assertRaises(TypeError):
            self.main_for_error_raiser()
        
    @genr
    def with_docstr(self):
        '''Docstr'''
        
    def test_docstr_visibility(self):
        self.assertTrue(self.with_docstr.__doc__ == 'Docstr')
        
    @genr(timeout=0.2)
    def runs_too_long(self):
        for _ in range(4):
            time.sleep(0.1)
        
    def test_timeout(self):
        self.runs_too_long().result()
        
    def test_thread_reference(self):
        future = self.small_wait()
        self.assertTrue(hasattr(future, 'thread'))
        self.assertTrue(type(future.thread) == threading.Thread)

    @genr(timeout=0.1)
    def time_out(self, checks):
        checks.append('one')
        time.sleep(0.2)
        checks.append('two')

    def test_timeout(self):
        checks = []
        future = self.time_out(checks)
        with self.assertRaises(concurrent.futures._base.TimeoutError):
            future.result()
        self.assertTrue(len(checks) == 1)
        self.assertTrue(checks[0] == 'one')
        
    @genr(timeout=0.1)
    def timeout_parent(self, checks1, checks2):
        checks1.append('one')
        self.timeout_child(checks2)
        time.sleep(0.2)
        checks1.append('two')
        
    @genr
    def timeout_child(self, checks2):
        checks2.append('one')
        time.sleep(0.25)
        checks2.append('two')
        
    def test_cascading_timeout(self):
        checks1 = []
        checks2 = []
        future = self.timeout_parent(checks1, checks2)
        time.sleep(0.1)
        with self.assertRaises(concurrent.futures._base.TimeoutError):
            future.result()
        self.assertTrue(len(checks1) == 1)
        self.assertTrue(checks1[0] == 'one')
        self.assertTrue(len(checks2) == 1)
        self.assertTrue(checks2[0] == 'one')
        
    @genr
    async def asyncio_small_wait(self):
        await asyncio.sleep(0.1)
        
    def test_async_def(self):
        future = self.asyncio_small_wait()
        self.assertTrue(future.running())
        time.sleep(0.2)
        self.assertTrue(future.done())
        
    @genr
    def genr_mixed(self):
        return 'expected'
        
    @genr
    async def asyncio_mixed(self):
        result = self.genr_mixed()
        return result.result()
        
    def test_async_mixed(self):
        value = yield self.asyncio_mixed()
        self.assertTrue(value == 'expected')
        
if __name__ == "__main__":
    unittest.main()
