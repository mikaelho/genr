import unittest, time

from genr import genr

class TestBasics(unittest.TestCase):
    
    @genr
    def small_wait(self):
        time.sleep(0.1)

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

    def test_exception_propagation(self):
        with self.assertRaises(TypeError):
            self.error_raiser().result()
        
        
if __name__ == "__main__":
    unittest.main()
