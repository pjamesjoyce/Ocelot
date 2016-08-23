# -*- coding: utf-8 -*-
import logging

def drop_rp_activity_links(data):
    """Delete hard (activity) links from reference product exchanges.

    These links have no meaning in the cutoff system model."""
    for ds in data:
        filtered_exchanges = (exc
                              for exc in ds['exchanges']
                              if exc['type'] == 'reference product'
                              and exc.get('activity link'))
        for exc in filtered_exchanges:
            logging.info({
                'type': 'table element',
                'data': (ds['name'], exc['name'])
            })
            del exc['activity link']
    return data

drop_rp_activity_links.__table__ = {
    'title': 'Drop hard (activity) links from reference product exchanges',
    'columns': ["Activity", "Reference product"]
}


def has_consequential_property(exchange):
    """Return list of consequential properties from an exchange"""
    return [prop
            for prop in exchange.get('properties', [])
            if prop['name'] == 'consequential'
            and prop['amount'] == 1]


def remove_consequential_exchanges(data):
    """Remove exchanges with have a ``consequential`` property with a value of 1.

    These exchanges are not used in the cutoff system model."""
    for ds in data:
        for exc in ds['exchanges']:
            if has_consequential_property(exc):
                logging.info({
                    'type': 'table element',
                    'data': (ds['name'], exc['name'], exc['amount'])
                })
        ds['exchanges'] = [exc
                           for exc in ds['exchanges']
                           if not has_consequential_property(exc)]
    return data

remove_consequential_exchanges.__table__ = {
    'title': 'Remove consequential exchanges not used in cutoff',
    'columns': ["Activity name", "Flow", "Amount"]
}
