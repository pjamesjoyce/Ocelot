# -*- coding: utf-8 -*-
from collections.abc import Iterable


class Collection(Iterable):
    """A collection of transformation functions is correctly unwrapped by a ``system_model``.

    Useful to quickly specify a list of commonly-grouped functions (e.g. ecospold common data cleanup, economic allocation).

    Instantiate a ``Collection`` with the desired transformation functions: ``Collection(do_something, do_something_else)``.

    """
    def __init__(self, *functions):
        self.functions = functions

    def __iter__(self):
        return iter(self.functions)

    def __len__(self):
        return len(self.functions)

    def __call__(self, data):
        for func in self:
            data = func(data)
        return data


def unwrap_functions(lst):
    """Unwrap a list of functions, some of which could be themselves lists of functions."""
    def unwrapper(functions):
        for func in functions:
            if isinstance(func, Iterable):
                for obj in unwrapper(func):
                    yield obj
            else:
                yield func

    return list(unwrapper(lst))
