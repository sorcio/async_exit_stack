#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Tests for `async_exit_stack` package."""


import asyncio
from contextlib import contextmanager
import functools
from test import support
import unittest

from async_exit_stack import AsyncExitStack


def _async_test(func):
    """Decorator to turn an async function into a test case."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        coro = func(*args, **kwargs)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()
            asyncio.set_event_loop(None)
    return wrapper


class _TestBaseExitStack:
    exit_stack = None

    @support.requires_docstrings
    def test_instance_docs(self):
        # Issue 19330: ensure context manager instances have good docstrings
        cm_docstring = self.exit_stack.__doc__
        obj = self.exit_stack()
        self.assertEqual(obj.__doc__, cm_docstring)

    def test_no_resources(self):
        with self.exit_stack():
            pass

    def test_callback(self):
        expected = [
            ((), {}),
            ((1,), {}),
            ((1,2), {}),
            ((), dict(example=1)),
            ((1,), dict(example=1)),
            ((1,2), dict(example=1)),
        ]
        result = []
        def _exit(*args, **kwds):
            """Test metadata propagation"""
            result.append((args, kwds))
        with self.exit_stack() as stack:
            for args, kwds in reversed(expected):
                if args and kwds:
                    f = stack.callback(_exit, *args, **kwds)
                elif args:
                    f = stack.callback(_exit, *args)
                elif kwds:
                    f = stack.callback(_exit, **kwds)
                else:
                    f = stack.callback(_exit)
                self.assertIs(f, _exit)
            for wrapper in stack._exit_callbacks:
                self.assertIs(wrapper[1].__wrapped__, _exit)
                self.assertNotEqual(wrapper[1].__name__, _exit.__name__)
                self.assertIsNone(wrapper[1].__doc__, _exit.__doc__)
        self.assertEqual(result, expected)

    def test_push(self):
        exc_raised = ZeroDivisionError
        def _expect_exc(exc_type, exc, exc_tb):
            self.assertIs(exc_type, exc_raised)
        def _suppress_exc(*exc_details):
            return True
        def _expect_ok(exc_type, exc, exc_tb):
            self.assertIsNone(exc_type)
            self.assertIsNone(exc)
            self.assertIsNone(exc_tb)
        class ExitCM(object):
            def __init__(self, check_exc):
                self.check_exc = check_exc
            def __enter__(self):
                self.fail("Should not be called!")
            def __exit__(self, *exc_details):
                self.check_exc(*exc_details)
        with self.exit_stack() as stack:
            stack.push(_expect_ok)
            self.assertIs(stack._exit_callbacks[-1][1], _expect_ok)
            cm = ExitCM(_expect_ok)
            stack.push(cm)
            self.assertIs(stack._exit_callbacks[-1][1].__self__, cm)
            stack.push(_suppress_exc)
            self.assertIs(stack._exit_callbacks[-1][1], _suppress_exc)
            cm = ExitCM(_expect_exc)
            stack.push(cm)
            self.assertIs(stack._exit_callbacks[-1][1].__self__, cm)
            stack.push(_expect_exc)
            self.assertIs(stack._exit_callbacks[-1][1], _expect_exc)
            stack.push(_expect_exc)
            self.assertIs(stack._exit_callbacks[-1][1], _expect_exc)
            1/0

    def test_enter_context(self):
        class TestCM(object):
            def __enter__(self):
                result.append(1)
            def __exit__(self, *exc_details):
                result.append(3)

        result = []
        cm = TestCM()
        with self.exit_stack() as stack:
            @stack.callback  # Registered first => cleaned up last
            def _exit():
                result.append(4)
            self.assertIsNotNone(_exit)
            stack.enter_context(cm)
            self.assertIs(stack._exit_callbacks[-1][1].__self__, cm)
            result.append(2)
        self.assertEqual(result, [1, 2, 3, 4])

    def test_close(self):
        result = []
        with self.exit_stack() as stack:
            @stack.callback
            def _exit():
                result.append(1)
            self.assertIsNotNone(_exit)
            stack.close()
            result.append(2)
        self.assertEqual(result, [1, 2])

    def test_pop_all(self):
        result = []
        with self.exit_stack() as stack:
            @stack.callback
            def _exit():
                result.append(3)
            self.assertIsNotNone(_exit)
            new_stack = stack.pop_all()
            result.append(1)
        result.append(2)
        new_stack.close()
        self.assertEqual(result, [1, 2, 3])

    def test_exit_raise(self):
        with self.assertRaises(ZeroDivisionError):
            with self.exit_stack() as stack:
                stack.push(lambda *exc: False)
                1/0

    def test_exit_suppress(self):
        with self.exit_stack() as stack:
            stack.push(lambda *exc: True)
            1/0

    def test_exit_exception_chaining_reference(self):
        # Sanity check to make sure that ExitStack chaining matches
        # actual nested with statements
        class RaiseExc:
            def __init__(self, exc):
                self.exc = exc
            def __enter__(self):
                return self
            def __exit__(self, *exc_details):
                raise self.exc

        class RaiseExcWithContext:
            def __init__(self, outer, inner):
                self.outer = outer
                self.inner = inner
            def __enter__(self):
                return self
            def __exit__(self, *exc_details):
                try:
                    raise self.inner
                except:
                    raise self.outer

        class SuppressExc:
            def __enter__(self):
                return self
            def __exit__(self, *exc_details):
                type(self).saved_details = exc_details
                return True

        try:
            with RaiseExc(IndexError):
                with RaiseExcWithContext(KeyError, AttributeError):
                    with SuppressExc():
                        with RaiseExc(ValueError):
                            1 / 0
        except IndexError as exc:
            self.assertIsInstance(exc.__context__, KeyError)
            self.assertIsInstance(exc.__context__.__context__, AttributeError)
            # Inner exceptions were suppressed
            self.assertIsNone(exc.__context__.__context__.__context__)
        else:
            self.fail("Expected IndexError, but no exception was raised")
        # Check the inner exceptions
        inner_exc = SuppressExc.saved_details[1]
        self.assertIsInstance(inner_exc, ValueError)
        self.assertIsInstance(inner_exc.__context__, ZeroDivisionError)

    def test_exit_exception_chaining(self):
        # Ensure exception chaining matches the reference behaviour
        def raise_exc(exc):
            raise exc

        saved_details = None
        def suppress_exc(*exc_details):
            nonlocal saved_details
            saved_details = exc_details
            return True

        try:
            with self.exit_stack() as stack:
                stack.callback(raise_exc, IndexError)
                stack.callback(raise_exc, KeyError)
                stack.callback(raise_exc, AttributeError)
                stack.push(suppress_exc)
                stack.callback(raise_exc, ValueError)
                1 / 0
        except IndexError as exc:
            self.assertIsInstance(exc.__context__, KeyError)
            self.assertIsInstance(exc.__context__.__context__, AttributeError)
            # Inner exceptions were suppressed
            self.assertIsNone(exc.__context__.__context__.__context__)
        else:
            self.fail("Expected IndexError, but no exception was raised")
        # Check the inner exceptions
        inner_exc = saved_details[1]
        self.assertIsInstance(inner_exc, ValueError)
        self.assertIsInstance(inner_exc.__context__, ZeroDivisionError)

    def test_exit_exception_non_suppressing(self):
        # http://bugs.python.org/issue19092
        def raise_exc(exc):
            raise exc

        def suppress_exc(*exc_details):
            return True

        try:
            with self.exit_stack() as stack:
                stack.callback(lambda: None)
                stack.callback(raise_exc, IndexError)
        except Exception as exc:
            self.assertIsInstance(exc, IndexError)
        else:
            self.fail("Expected IndexError, but no exception was raised")

        try:
            with self.exit_stack() as stack:
                stack.callback(raise_exc, KeyError)
                stack.push(suppress_exc)
                stack.callback(raise_exc, IndexError)
        except Exception as exc:
            self.assertIsInstance(exc, KeyError)
        else:
            self.fail("Expected KeyError, but no exception was raised")

    def test_exit_exception_with_correct_context(self):
        # http://bugs.python.org/issue20317
        @contextmanager
        def gets_the_context_right(exc):
            try:
                yield
            finally:
                raise exc

        exc1 = Exception(1)
        exc2 = Exception(2)
        exc3 = Exception(3)
        exc4 = Exception(4)

        # The contextmanager already fixes the context, so prior to the
        # fix, ExitStack would try to fix it *again* and get into an
        # infinite self-referential loop
        try:
            with self.exit_stack() as stack:
                stack.enter_context(gets_the_context_right(exc4))
                stack.enter_context(gets_the_context_right(exc3))
                stack.enter_context(gets_the_context_right(exc2))
                raise exc1
        except Exception as exc:
            self.assertIs(exc, exc4)
            self.assertIs(exc.__context__, exc3)
            self.assertIs(exc.__context__.__context__, exc2)
            self.assertIs(exc.__context__.__context__.__context__, exc1)
            self.assertIsNone(
                       exc.__context__.__context__.__context__.__context__)

    def test_exit_exception_with_existing_context(self):
        # Addresses a lack of test coverage discovered after checking in a
        # fix for issue 20317 that still contained debugging code.
        def raise_nested(inner_exc, outer_exc):
            try:
                raise inner_exc
            finally:
                raise outer_exc
        exc1 = Exception(1)
        exc2 = Exception(2)
        exc3 = Exception(3)
        exc4 = Exception(4)
        exc5 = Exception(5)
        try:
            with self.exit_stack() as stack:
                stack.callback(raise_nested, exc4, exc5)
                stack.callback(raise_nested, exc2, exc3)
                raise exc1
        except Exception as exc:
            self.assertIs(exc, exc5)
            self.assertIs(exc.__context__, exc4)
            self.assertIs(exc.__context__.__context__, exc3)
            self.assertIs(exc.__context__.__context__.__context__, exc2)
            self.assertIs(
                 exc.__context__.__context__.__context__.__context__, exc1)
            self.assertIsNone(
                exc.__context__.__context__.__context__.__context__.__context__)

    def test_body_exception_suppress(self):
        def suppress_exc(*exc_details):
            return True
        try:
            with self.exit_stack() as stack:
                stack.push(suppress_exc)
                1/0
        except IndexError as exc:
            self.fail("Expected no exception, got IndexError")

    def test_exit_exception_chaining_suppress(self):
        with self.exit_stack() as stack:
            stack.push(lambda *exc: True)
            stack.push(lambda *exc: 1/0)
            stack.push(lambda *exc: {}[1])

    def test_excessive_nesting(self):
        # The original implementation would die with RecursionError here
        with self.exit_stack() as stack:
            for i in range(10000):
                stack.callback(int)

    def test_instance_bypass(self):
        class Example(object): pass
        cm = Example()
        cm.__exit__ = object()
        stack = self.exit_stack()
        self.assertRaises(AttributeError, stack.enter_context, cm)
        stack.push(cm)
        self.assertIs(stack._exit_callbacks[-1][1], cm)

    def test_dont_reraise_RuntimeError(self):
        # https://bugs.python.org/issue27122
        class UniqueException(Exception): pass
        class UniqueRuntimeError(RuntimeError): pass

        @contextmanager
        def second():
            try:
                yield 1
            except Exception as exc:
                raise UniqueException("new exception") from exc

        @contextmanager
        def first():
            try:
                yield 1
            except Exception as exc:
                raise exc

        # The UniqueRuntimeError should be caught by second()'s exception
        # handler which chain raised a new UniqueException.
        with self.assertRaises(UniqueException) as err_ctx:
            with self.exit_stack() as es_ctx:
                es_ctx.enter_context(second())
                es_ctx.enter_context(first())
                raise UniqueRuntimeError("please no infinite loop.")

        exc = err_ctx.exception
        self.assertIsInstance(exc, UniqueException)
        self.assertIsInstance(exc.__context__, UniqueRuntimeError)
        self.assertIsNone(exc.__context__.__context__)
        self.assertIsNone(exc.__context__.__cause__)
        self.assertIs(exc.__cause__, exc.__context__)


class TestAsyncExitStack(_TestBaseExitStack, unittest.TestCase):
    class SyncAsyncExitStack(AsyncExitStack):
        @staticmethod
        def run_coroutine(coro):
            loop = asyncio.get_event_loop()

            f = asyncio.ensure_future(coro)
            f.add_done_callback(lambda f: loop.stop())
            loop.run_forever()

            exc = f.exception()

            if not exc:
                return f.result()
            else:
                context = exc.__context__

                try:
                    raise exc
                except:
                    exc.__context__ = context
                    raise exc

        def close(self):
            return self.run_coroutine(self.aclose())

        def __enter__(self):
            return self.run_coroutine(self.__aenter__())

        def __exit__(self, *exc_details):
            return self.run_coroutine(self.__aexit__(*exc_details))

    exit_stack = SyncAsyncExitStack

    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.addCleanup(self.loop.close)

    @_async_test
    async def test_async_callback(self):
        expected = [
            ((), {}),
            ((1,), {}),
            ((1,2), {}),
            ((), dict(example=1)),
            ((1,), dict(example=1)),
            ((1,2), dict(example=1)),
        ]
        result = []
        async def _exit(*args, **kwds):
            """Test metadata propagation"""
            result.append((args, kwds))

        async with AsyncExitStack() as stack:
            for args, kwds in reversed(expected):
                if args and kwds:
                    f = stack.push_async_callback(_exit, *args, **kwds)
                elif args:
                    f = stack.push_async_callback(_exit, *args)
                elif kwds:
                    f = stack.push_async_callback(_exit, **kwds)
                else:
                    f = stack.push_async_callback(_exit)
                self.assertIs(f, _exit)
            for wrapper in stack._exit_callbacks:
                self.assertIs(wrapper[1].__wrapped__, _exit)
                self.assertNotEqual(wrapper[1].__name__, _exit.__name__)
                self.assertIsNone(wrapper[1].__doc__, _exit.__doc__)

        self.assertEqual(result, expected)

    @_async_test
    async def test_async_push(self):
        exc_raised = ZeroDivisionError
        async def _expect_exc(exc_type, exc, exc_tb):
            self.assertIs(exc_type, exc_raised)
        async def _suppress_exc(*exc_details):
            return True
        async def _expect_ok(exc_type, exc, exc_tb):
            self.assertIsNone(exc_type)
            self.assertIsNone(exc)
            self.assertIsNone(exc_tb)
        class ExitCM(object):
            def __init__(self, check_exc):
                self.check_exc = check_exc
            async def __aenter__(self):
                self.fail("Should not be called!")
            async def __aexit__(self, *exc_details):
                await self.check_exc(*exc_details)

        async with self.exit_stack() as stack:
            stack.push_async_exit(_expect_ok)
            self.assertIs(stack._exit_callbacks[-1][1], _expect_ok)
            cm = ExitCM(_expect_ok)
            stack.push_async_exit(cm)
            self.assertIs(stack._exit_callbacks[-1][1].__self__, cm)
            stack.push_async_exit(_suppress_exc)
            self.assertIs(stack._exit_callbacks[-1][1], _suppress_exc)
            cm = ExitCM(_expect_exc)
            stack.push_async_exit(cm)
            self.assertIs(stack._exit_callbacks[-1][1].__self__, cm)
            stack.push_async_exit(_expect_exc)
            self.assertIs(stack._exit_callbacks[-1][1], _expect_exc)
            stack.push_async_exit(_expect_exc)
            self.assertIs(stack._exit_callbacks[-1][1], _expect_exc)
            1/0

    @_async_test
    async def test_async_enter_context(self):
        class TestCM(object):
            async def __aenter__(self):
                result.append(1)
            async def __aexit__(self, *exc_details):
                result.append(3)

        result = []
        cm = TestCM()

        async with AsyncExitStack() as stack:
            @stack.push_async_callback  # Registered first => cleaned up last
            async def _exit():
                result.append(4)
            self.assertIsNotNone(_exit)
            await stack.enter_async_context(cm)
            self.assertIs(stack._exit_callbacks[-1][1].__self__, cm)
            result.append(2)

        self.assertEqual(result, [1, 2, 3, 4])

    @_async_test
    async def test_async_exit_exception_chaining(self):
        # Ensure exception chaining matches the reference behaviour
        async def raise_exc(exc):
            raise exc

        saved_details = None
        async def suppress_exc(*exc_details):
            nonlocal saved_details
            saved_details = exc_details
            return True

        try:
            async with self.exit_stack() as stack:
                stack.push_async_callback(raise_exc, IndexError)
                stack.push_async_callback(raise_exc, KeyError)
                stack.push_async_callback(raise_exc, AttributeError)
                stack.push_async_exit(suppress_exc)
                stack.push_async_callback(raise_exc, ValueError)
                1 / 0
        except IndexError as exc:
            self.assertIsInstance(exc.__context__, KeyError)
            self.assertIsInstance(exc.__context__.__context__, AttributeError)
            # Inner exceptions were suppressed
            self.assertIsNone(exc.__context__.__context__.__context__)
        else:
            self.fail("Expected IndexError, but no exception was raised")
        # Check the inner exceptions
        inner_exc = saved_details[1]
        self.assertIsInstance(inner_exc, ValueError)
        self.assertIsInstance(inner_exc.__context__, ZeroDivisionError)


if __name__ == '__main__':
    unittest.main()
