# -*- coding: utf-8 -*-
from ..errors import InvalidMultioutputDataset, ZeroProduction
from .uncertainty import scale_exchange, remove_exchange_uncertainty
from copy import deepcopy
from pprint import pformat
import hashlib
import pandas as pd
import wrapt


### Activity identifiers

def activity_hash(dataset):
    """Return the hash string that uniquely identifies an activity.

    Uses the following fields, in order:
        * name
        * reference product
        * unit
        * location
        * start date
        * end date

    An empty string is used if a field isn't present. All fields are cast to lower case.

    """
    fields = (
        "name",
        "reference product",
        "unit",
        "location",
        "start date",
        "end date",
    )
    string = "".join(dataset.get(field, '').lower() for field in fields)
    return hashlib.md5(string.encode('utf-8')).hexdigest()


### Exchange iterators and accessors

def allocatable_production(dataset):
    """Return generator of production exchanges for a dataset.

    Production exchanges either:

    * Have type ``reference product``, or
    * Have type ``byproduct`` and ``classification`` is ``allocatable product``

    Note that all types of reference products are returned: ``allocatable product``, ``waste``, and ``recyclable``!

    """
    for exc in dataset['exchanges']:
        if exc['type'] =='reference product':
            yield exc
        elif (exc['type'] == 'byproduct' and
              exc['byproduct classification'] == 'allocatable product'):
            yield exc


def nonproduction_exchanges(dataset):
    """Return generator of non-production exchanges for a dataset.

    Non-production exchanges must meet both criteria:

    * Not have type ``reference product``, or
    * Not have type ``byproduct`` and ``classification`` ``allocatable product``

    """
    for exc in dataset['exchanges']:
        if exc['type'] =='reference product':
            continue
        elif (exc['type'] == 'byproduct' and
              exc['byproduct classification'] == 'allocatable product'):
            continue
        yield exc


def get_single_reference_product(dataset):
    """Return reference product exchange for dataset ``dataset``.

    Raises ``InvalidMultioutputDataset`` if multiple reference products were found, ``ValueError`` if no reference product was found."""
    products = [exc for exc in dataset['exchanges']
                if exc['type'] == 'reference product']
    if len(products) > 1:
        message = "Found multiple reference products in dataset:\n{}"
        raise InvalidMultioutputDataset(message.format(dataset['filepath']))
    elif not products:
        message = "Found no reference products in dataset:\n{}"
        raise ValueError(message.format(dataset['filepath']))
    return products[0]


def iterate_all_parameters(dataset):
    """Generator that returns all parameterized objects in a dataset."""
    for exc in dataset['exchanges']:
        if "variable" in exc or "formula" in exc:
            yield exc
        pv = exc.get("production volume", {})
        if "variable" in pv or "formula" in pv:
            yield pv
        for prop in exc.get('properties', []):
            if "variable" in prop or "formula" in prop:
                yield prop
    for parameter in dataset.get('parameters', []):
        if "variable" in parameter or "formula" in parameter:
            yield parameter


def iterate_all_uncertainties(dataset):
    """Generator that returns all objects with an uncertainty distribution."""
    for exc in dataset['exchanges']:
        if "uncertainty" in exc:
            yield exc
        pv = exc.get("production volume", {})
        if "uncertainty" in pv:
            yield pv
        for prop in exc.get('properties', []):
            if "uncertainty" in prop:
                yield prop
    for parameter in dataset.get('parameters', []):
        if "uncertainty" in parameter:
            yield parameter


def get_biggest_pv_to_exchange_ratio(dataset):
    """Return the largest ration of production volume to exchange amount.

    Considers only reference product exchanges with the ``allocatable product`` classification.

    In theory, this ratio should always be the same in a multioutput dataset. However, this is quite often not the case, and when calculating production volume for other exchanges (byproducts, activity links) we need one number for the dataset.

    So, we look for the biggest absolute value. This may not be perfect, but it is consistent.

    Returns a float."""
    production_volumes = sorted([
        exc['production volume']['amount'] / exc['amount']
        for exc in dataset['exchanges']
        if exc['type'] == 'reference product'
        and exc['amount']
    ], reverse=True, key=lambda x: abs(x))
    if not production_volumes:
        message = "No suitable reference product exchanges in {}"
        raise ZeroProduction(message.format(dataset['name']))
    return production_volumes[0]


### Exchange groupers

def extract_products_as_tuple(dataset):
    """Return names of all products as a sorted tuple.

    Products are chosen using ``allocatable_production``."""
    return tuple(sorted([exc['name'] for exc in allocatable_production(dataset)]))


def activity_grouper(dataset):
    """Return tuple of dataset name and products.

    Products are chosen using ``extract_products_as_tuple``."""
    return (dataset['name'], extract_products_as_tuple(dataset))


### Property accessors

def get_property_by_name(exchange, name):
    """Get property object with name ``name`` from exchange ``exchange``.

    Returns an empty dictionary if the property named ``name`` is not found."""
    for prop in exchange.get("properties", []):
        if prop['name'] == name:
            return prop
    return {}


def get_numerical_property(exchange, name):
    """Get ``amount`` value for property ``property_name`` in exchange ``exchange``.

    Returns a float or ``None``."""
    return get_property_by_name(exchange, name).get('amount')


### Data extractors

def allocatable_production_as_dataframe(dataset):
    """Return an pandas dataframe which describes the exchanges in dataset ``dataset``.

    The dataframe has the following columns:

    * ``name``: str, name of exchange flow
    * ``amount``: float, amount of exchange
    * ``type``: str, type of exchange
    * ``price``: float, amount of property named ``price``. Default is 0 if property ``price`` is not provided.
    * ``has true value``: bool, whether a property names ``true value relation`` is present in this exchange.
    * ``true value``: float, amount of property named ``true value relation``. Default is 0 if property ``true value relation`` is not provided.
    * ``revenue``: float, price * amount.

    """
    data = []
    for exc in allocatable_production(dataset):
        data.append({
            'name': exc['name'],
            'amount': exc['amount'],
            'type': exc['type'],
            'price': get_property_by_name(exc, 'price').get('amount', 0),
            'has true value': bool(get_property_by_name(exc, 'true value relation')),
            'true value': get_property_by_name(exc, 'true value relation').get(
                'amount', 0),
        })
    df = pd.DataFrame(data)
    df['revenue'] = df['price'] * df['amount']
    return df


### Exchange modifiers

def normalize_reference_production_amount(dataset):
    """Scale the exchange amounts so the reference product exchange has an amount of 1 or -1"""
    product = get_single_reference_product(dataset)
    if not product['amount']:
        message = "Zero production amount for dataset:\n{}"
        raise ZeroProduction(message.format(dataset['filepath']))
    factor = 1 / abs(product['amount'])
    # TODO: Skip if very close to one?
    if factor != 1:
        for exchange in dataset['exchanges']:
            scale_exchange(exchange, factor)
    return dataset


def label_reference_product(data):
    """Add field ``reference product`` to all datasets.

    The field ``reference product`` has the name of the reference product exchange.

    Raises ``InvalidMultioutputDataset`` if multiple reference products are present, or ``ValueError`` if no reference products are present."""
    for dataset in data:
        dataset['reference product'] = get_single_reference_product(dataset)['name']
    return data


def nonreference_product(exchange):
    """Mark exchange as a unselected production exchange.

    * ``amount`` is set to zero
    * ``type`` is changed to ``dropped product``.
    * ``formula`` is deleted if present (amount can't change on recalculation).
    * ``production volume`` is deleted if present.

    """
    exchange['type'] = 'dropped product'
    exchange['amount'] = 0.
    if 'formula' in exchange:
        del exchange['formula']
    if 'production volume' in exchange:
        del exchange['production volume']
    return remove_exchange_uncertainty(exchange)


def choose_reference_product_exchange(dataset, exchange, allocation_factor=1):
    """Return a copy of ``dataset`` where ``exchange`` is the reference product.

    ``exchange`` can be any allocatable product exchange. It is normally in ``dataset``, but does not have to be.

    All other exchanges are re-scaled by ``allocation_factor``. The allocation factors for a multioutput process should sum to one. We no longer have the ability to allocate groups of exchanges separately. Then, all exchanges are normalized so that the reference product exchange value is one.

    The chosen product exchange is modified:

    * Uncertainty is set to ``undefined`` and made perfectly certain. Production exchanges by definition cannot have uncertainty.
    * ``classification`` is deleted if present
    * ``type`` is set to ``reference product``

    Non-chosen product exchanges are also modified:

    * ``amount`` is set to zero
    * ``type`` is changed to ``dropped product``.
    * ``production volume`` is deleted if present.

    """
    obj = deepcopy(dataset)
    if not exchange['amount']:
        message = "Zero production amount for new reference product exchange:\n{}\nIn dataset:\n{}"
        raise ZeroProduction(message.format(pformat(exchange), dataset['filepath']))
    rp = remove_exchange_uncertainty(deepcopy(exchange))
    rp['type'] = 'reference product'
    if 'byproduct classification' in rp:
        del rp['byproduct classification']
    obj['exchanges'] = [rp] + [
        nonreference_product(deepcopy(exc))
        for exc in allocatable_production(dataset)
        if exc != exchange
    ] + [
        scale_exchange(deepcopy(exc), allocation_factor)
        for exc in nonproduction_exchanges(dataset)
    ]
    return normalize_reference_production_amount(obj)


### Function helpers

@wrapt.decorator
def single_input(wrapped, instance, args, kwargs):
    """Decorator to allow a transformation to transformation function to take a single dataset input."""
    data = kwargs.get('data') or args[0]
    return [ds for elem in data for ds in wrapped(elem)]
