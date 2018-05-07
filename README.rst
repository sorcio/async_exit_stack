=======================
AsyncExitStack backport
=======================


.. image:: https://img.shields.io/pypi/v/async_exit_stack.svg
        :target: https://pypi.python.org/pypi/async_exit_stack

.. image:: https://img.shields.io/travis/sorcio/async_exit_stack.svg
        :target: https://travis-ci.org/sorcio/async_exit_stack

.. image:: https://readthedocs.org/projects/async-exit-stack/badge/?version=latest
        :target: https://async-exit-stack.readthedocs.io/en/latest/?badge=latest
        :alt: Documentation Status




AsyncExitStack backport for Python 3.5+


* Free software: PSF license
* Documentation: https://docs.python.org/3.7/library/contextlib.html#contextlib.AsyncExitStack

This package contains code from the CPython project.


Usage example
-------------

    from async_exit_stack import AsyncExitStack

    async def some_async_function():
        async with AsyncExitStack() as stack:
            connections = [await stack.enter_async_context(get_connection())
                for i in range(5)]
            # All opened connections will automatically be released at the end of
            # the async with statement, even if attempts to open a connection
            # later in the list raise an exception.


Reference
---------

Refer to Python 3.7 contextlib documentation: https://docs.python.org/3.7/library/contextlib.html#contextlib.AsyncExitStack


`class AsyncExitStack`
An asynchronous context manager, similar to ExitStack, that supports combining both synchronous and asynchronous context managers, as well as having coroutines for cleanup logic.

The close() method is not implemented, aclose() must be used instead.

`enter_async_context(cm)`
Similar to enter_context() but expects an asynchronous context manager.

`push_async_exit(exit)`
Similar to push() but expects either an asynchronous context manager or a coroutine.

`push_async_callback(callback, *args, **kwds)`
Similar to callback() but expects a coroutine.

`aclose()`
Similar to close() but properly handles awaitables.
