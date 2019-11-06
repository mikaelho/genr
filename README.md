# genr

Simple concurrency with minimum mental overhead.

Builds on `concurrent.futures`, and uses `return value` in a generator, limiting use to Python 3.3 and above.

Note that while this is working code that I use in my (simple) projects, it is work in progress, and is mainly intended to act as a concrete expression of my need for simpler async coding.

## Usage

### `yield` as a synchronization point

Functions and generators with `genr` decorator are executed in a new thread, with a special handling of the `yield`s. For example, in the following:

    @genr
    def example1():
        task1()
        task2()
        yield
        task3()
        
Tasks 1 and 2, also decorated with `genr`, are executed in parallel. `yield` waits until they are both complete, after which task 3 gets to run.

End of the function also acts as a collection  point, i.e. we wait for all called functions to complete before returning. Thus, in the example above, there is little practical difference whether `task3` is executed in a separate thread or not.

### `yield` to get results

Decorated functions return a `concurrent.futures` `Future`, which can be used in the usual way, but for more readable code, we use a Tornado-inspired way of `yield`ing the result. The classical example below demonstrates retrieving several web pages in parallel:

    @genr
    def example2():
        return yield [ fetch(url)
            for url in (
                'https://python.org',
                'https://pypi.org'
            )]
        
    @genr
    def fetch(url):
        return requests.get(url).text

### Ad hoc threads

Being a decorator, `genr` can be used to start parallel execution of individual functions inline, with the following syntax:

    genr(func_name)(param1, param2, ...)

While this avoids having to create named one-line functions just for the sake of parallel execution, the syntax is not especially readable, and quickly becomes untenable if you need to add timeouts, exception management etc.
                        
### Interrupting execution
        
Aligned with `concurrent.futures`, `genr` plays nice with being `KeyboardInterrupt`ed. To wait for a `genr` thread to complete in the main thread, you can simply wait for the result:

    main_function().result()

## Discussion

### Pros

- Minimum cognitive load, no need to even understand the concept of a future.
- Move quickly from need to implementation without needing to understand asyncio.
- For relatively easy cases, functional need for parallel execution translates into a clear story in a single main function.
- One decorator for the different use cases:
    - Launching a single parallel function
    - Multiple parallel threads
    - Collecting results

### Cons

- Likely to suffer from the same challenge that drove the creation of asyncio: it is not very visible whether a function is being called in a separate thread or not, which can lead to hard-to-see bugs.
- Overloads generator semantics in a way that is not Pythonic.
