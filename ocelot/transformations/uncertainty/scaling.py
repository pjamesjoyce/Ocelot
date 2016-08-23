# -*- coding: utf-8 -*-
from ...errors import UnsupportedDistribution
import math


# TODO: Dummy function for now
# Will be new pull request
recalculate_pedigree_matrix = lambda x: None

uncertainty_type = lambda x: x.get('uncertainty', {}).get('type')


def scale_fields(exchange, fields, factor):
    for field in fields:
        exchange['uncertainty'][field] *= factor
    return exchange


def scale_lognormal(exchange, factor):
    if factor < 1:
        # TODO
        return exchange
    elif exchange['uncertainty']['mean'] <= 0:
        if exchange['amount'] > 0:
            exchange['uncertainty']['mean'] = exchange['mean']
        else:
            # TODO
            return exchange

    exchange['uncertainty']['mean'] *= factor
    exchange['uncertainty']['mu'] = math.log(exchange['uncertainty']['mean'])
    return exchange


def scale_normal(exchange, factor):
    exchange = scale_fields(exchange, ('mean', 'variance'), factor)
    recalculate_pedigree_matrix(exchange)
    return exchange


def scale_triangular(exchange, factor):
    return scale_fields(exchange, ('minimum', 'maximum', 'mode'), factor)


def scale_uniform(exchange, factor):
    return scale_fields(exchange, ('minimum', 'maximum'), factor)


def scale_undefined(exchange, factor):
    # 'standard deviation 95%' is not modified, as this value
    # has ambiguous meaning and is always 0 in ecoinvent 3.2
    return scale_fields(exchange, ('minimum', 'maximum'), factor)


function_mapping = {
    'lognormal': scale_lognormal,
    'normal': scale_normal,
    'triangular': scale_triangular,
    'uniform': scale_uniform,
    'undefined': scale_undefined,
    None: lambda x, y: x
}


def scale_exchange(exchange, factor):
    """Scale an ``exchange`` and its uncertainty by a constant ``factor``.

    Modifies the exchange in place. Returns the modified exchange."""
    if factor == 1:
        return exchange
    try:
        exchange = function_mapping[uncertainty_type(exchange)](exchange, factor)
        exchange['amount'] *= factor
    except KeyError:
        raise UnsupportedDistribution
    return exchange