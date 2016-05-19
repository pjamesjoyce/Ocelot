# -*- coding: utf-8 -*-
import general_file_functions as gff
reload(gff)
import spold2_classes_integral as sc2
reload(sc2)
import os
from pandas import DataFrame, concat, read_excel, pivot_table
import pandas
from copy import deepcopy
from scipy.sparse import find
from time import localtime, strftime, time
import numpy as np
version = '3.2'
system_model = 'undefined'
base = r'C:\python\DB_versions'
ao = {}
for system_model in ['undefined', 'cut-off']:
    basepath = os.path.join(base, version, system_model)
    folder = os.path.join(basepath, 'python variables')
    ao[system_model] = gff.load_variables([[folder, 'ao']])[0]
    ao[system_model] = ao[system_model].set_index(['activityName', 'Geography']).sortlevel(level=0)
    ao[system_model] = ao[system_model][ao[system_model]['Activity Hidden'] == 'FALSE']
    if system_model == 'undefined':
        folder = os.path.join(basepath, 'excel and csv')
        activityLinkOverview = read_excel(os.path.join(folder, 'activityLink_overview_3.2.xlsx'), 
            'Sheet2')
activityLinkOverview = activityLinkOverview.set_index(['name', 
    'activityLink activityName', 'activityLink geography']).sortlevel(level=0)
activityLinkOverview = activityLinkOverview[activityLinkOverview['note'] != 'loss']
results = DataFrame()
keep = ['specialActivityType', 'Product Type', 'Product', 
    'By-product classification', 'Product Amount', 'Product Annual Production Volume', 
    'Price (EURO2005)']
counter = 0
ao['undefined'] = ao['undefined'][keep]
ao['cut-off'] = ao['cut-off'][keep]
ao['undefined']['PV after AL'] = ao['undefined']['Product Annual Production Volume'].copy()
for activityName, geography in set(ao['undefined'].index):
    counter += 1
    print counter, len(results)
    sel = ao['undefined'].loc[(activityName, geography)]
    sel['nbReferenceProduct'] = list(sel['Product Type']).count('ReferenceProduct')
    #sel['nbReferenceProduct'] = list(sel['Product Type']).count('ReferenceProduct')
    sel['effective PV'] = sel['Product Annual Production Volume'].copy()
    sel['conditionalExchange'] = False
    bp = sel[sel['Product Type'] == 'ByProduct']
    if len(bp) > 0:
        sel['nbAllocatableByProducts'] = list(sel['By-product classification']
            ).count('allocatable product')
        sel['nbNonAllocatableByProducts'] = len(bp) - sel['nbAllocatableByProducts']
    else:
        sel['nbAllocatableByProducts'] = 0
        sel['nbNonAllocatableByProducts'] = 0
    sel = sel.set_index(['Product Type', 'Product']).sortlevel(level=0)
    sel['cut-off'] = False
    sel['sumPVregio/GLO > .995'] = False
    sel['sumPVproduced = 0'] = False
    sel3 = {}
    for system_model in ['cut-off']:
        if (activityName, geography) in set(ao[system_model].index):
            sel3[system_model] = ao[system_model].loc[(activityName, geography)]
        elif (activityName, 'RoW') in set(ao[system_model].index):
            sel3[system_model] = ao[system_model].loc[(activityName, 'RoW')]
    for group, product in sel.index:
        sel2 = sel.loc[(group, product)]
        if type(sel2) == pandas.core.frame.DataFrame:
            if len(sel2) > 1:
                s = sel2['Product Amount'].sum()
                sel2 = sel2.iloc[0]
                sel2['Product Amount'] = s
            else:
                sel2 = sel2.iloc[0]
        #calculate PV after AL
        if (product, activityName, geography) in set(activityLinkOverview.index):
            sel_link = activityLinkOverview.loc[(product, activityName, geography)]
            if type(sel_link) != pandas.core.frame.DataFrame:
                1/0
            for i in range(len(sel_link)):
                sel.loc[(group, product), 'PV after AL'] = sel2['PV after AL'
                    ] - sel_link.iloc[0]['consumption']
        if geography == 'GLO':
            sel10 = ao['undefined'].loc[activityName]
            i = list(set(sel10.index))
            i.remove('GLO')
            if len(i) > 0:
                sel10 = sel10.loc[i]
                if type(sel10) != pandas.core.frame.DataFrame:
                    1/0
                if sel2['Product Annual Production Volume'] != 0.:
                    ratio = sel10['Product Annual Production Volume'].sum()/sel2['Product Annual Production Volume']
                else:
                    ratio = 0.
                if ratio > .995:
                    sel.loc[(group, product), 'sumPVregio/GLO > .995'] = True
        sel10 = ao['undefined'][ao['undefined']['Product'] == product]
        sel.loc[(group, product), 'sumPVproduced = 0'] = sel10[
            'Product Annual Production Volume'].sum() == 0.
        if sel2['Product Amount'] < 0. and sel2['specialActivityType'
                ] == 'market activity' and group == 'ByProduct':
            sel.loc[(group, product), 'conditionalExchange'] = True
        for system_model in sel3:
            if product in list(sel3[system_model]['Product']):
                sel.loc[(group, product), system_model] = True
    sel['activityName'] = activityName
    sel['geography'] = geography
    results = gff.update_df(results, sel.reset_index())
results = results.reset_index()
indexes = list(results[results['PV after AL'] <= 0.].index)
results.loc[indexes, 'PV after AL'] = 0.
folder = r'C:\ocelot\output'
filename = 'allocationUntangle.xlsx'
cols = ['activityName', 'geography']
cols.extend(keep)
cols.extend(['conditionalExchange', 'PV after AL', 'sumPVproduced = 0', 
    'sumPVregio/GLO > .995', 'cut-off'])
results.to_excel(os.path.join(folder, filename), cols = cols, 
         index = False, merge_cells = False)