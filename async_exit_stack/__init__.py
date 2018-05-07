# -*- coding: utf-8 -*-

"""Top-level package for AsyncExitStack backport."""

__author__ = """Davide Rizzo"""
__email__ = 'sorcio@gmail.com'
__version__ = '1.0.1'


try:
    from contextlib import AsyncExitStack
except ImportError:
    from ._async_exit_stack import AsyncExitStack


__all__ = ['AsyncExitStack']
