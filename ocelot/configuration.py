# -*- coding: utf-8 -*-
from .transformations import (
    drop_zero_pv_row_datasets,
    fix_ecoinvent_parameters,
    relabel_global_to_row,
    variable_names_are_unique,
)


class Configuration(object):
    """This is a dummy class, to be filled in with code that can parse various ways for defining a system model in a list of Python functions, including currying, etc."""
    def __init__(self):
        self.functions = []

    def __iter__(self):
        return iter(self.functions)


# Default config for now is cutoff
default_configuration = [
    variable_names_are_unique,
    fix_ecoinvent_parameters,
    relabel_global_to_row,
    drop_zero_pv_row_datasets,
]
