# -*- coding: utf-8 -*-
from copy import deepcopy, copy
import numpy as np
import scipy as sp
import pandas as pd
import os
from cPickle import load
import re
import ocelot_support_functions as osf
reload(osf)
def fixMathematicalRelation(m):
    for before, after in [('ABS(', 'abs('), 
            ('%', 'e-2'), ('^', '**')]:
        m = m.replace(before, after)
    #also, need to replace division by int by division by float
    return m
def fixIntegerDivision(searchHere, replaceHere):
    #problem: 123/232 will round down, because of division by integer.  
    #solution: find all division followed by a sequence of digits not followed by
    #a decimal point or another division sign (to avoid removing the next / from the
    #regular expression) and replace it by the same number followed by a decimal point.
    #ouf!
    #This is done after removing variable names, in case of for example "/234_variableName"
    int_division = re.compile('/\d+[.]?')
    matches = set(int_division.findall(searchHere))
    for match in matches:
        if match[-1] != '.':
            before = copy(replaceHere)
            replaceHere = replaceHere.replace(match, match+'.')
            if len(replaceHere) != before:
                pass
                #print before, match, replaceHere
                #1/0
    return replaceHere
def buildGraph(df, combined = True):
    #Problem: if a mathematicalRelation1 = variable11*2, and the variableName variable1 exists, 
    #and we do "variable1 in mathematicalRelation1", we will get a false dependency of 
    #mathematicalRelation1 on variable1.  
    #Solution: check for the longest variableName first, and once found, remove
    #them from the mathematicalRelation.  
    df['length'] = df['variableName'].apply(len)
    df['mathematicalRelation'] = df['mathematicalRelation'].apply(fixMathematicalRelation)
    for index in list(df[df['variableName'] == ''].index):
        df.loc[index, 'variableName'] = 'dummyVariableName%s' % index
    order = list(df.sort('length', ascending = False).index)
    if combined:
        #in the context of combined production, PVs and amounts of reference products 
        #are out of the equation
        indexes = list(df[df['valueType'] == 'ProductionVolume'].index)
        df.loc[indexes, 'mathematicalRelation'] = ''
        indexes = df[df['valueType'] == 'Exchange']
        indexes = list(indexes[indexes['group'] == 'ReferenceProduct'].index)
        df.loc[indexes, 'mathematicalRelation'] = ''
    dfWithFormula = df[df['mathematicalRelation'] != '']
    mathematicalRelations = dict(zip(list(dfWithFormula.index), 
        list(dfWithFormula['mathematicalRelation'])))
    rows = []
    columns = []
    for i in mathematicalRelations:
        for j in order:
            for field in ['Ref', 'variableName']:
                #for a given mathematicalRelation, it is tested if both
                #variableName and Ref of a quantitative element is present.
                #if so, an entry is created in the graph matrix
                v = df.loc[j, field]
                found = False
                if v in mathematicalRelations[i]:
                    if j == 0 and i == 0:
                        1/0
                    mathematicalRelations[i] = mathematicalRelations[i].replace(v, '')
                    if field == 'Ref':
                        #'Ref("something")' is not a valid variable name in python, 
                        #the Ref is replaced by the variableName
                        df.loc[i, 'mathematicalRelation'] = df.loc[i, 'mathematicalRelation'
                            ].replace(v, df.loc[j, 'variableName'])
                    found = True
                if found:
                    rows.append(j)
                    columns.append(i)
        df.loc[i, 'mathematicalRelation'] = fixIntegerDivision(
            mathematicalRelations[i], df.loc[i, 'mathematicalRelation'])
    c = [1 for i in range(len(rows))]
    ij = np.vstack((rows, columns))
    graph = sp.sparse.csr_matrix((c,ij), shape = (len(df), len(df)))
    #graph contains a "1" in position (i,j) if the mathematicalRelation of amount j 
    #depends on the variableName of Ref of amount i
    return graph, df
def calculationOrder(df, graph):
    #for a given amount, find all the paths between it and the other amounts
    #the calculation order is based on the longest path: amounts with longest 
    #maximum length path are calculated last.  
    longestPath = {}
    for index in range(len(df)): #for each amount
        paths = [[index]] #the path starts with itself
        longest = 0
        while True:#iterate until there is no more path to find
            paths_to_check = []
            for i in range(len(paths)):
                path = copy(paths[i])
                rows, columns, c = sp.sparse.find(graph.getcol(path[-1]))
                if len(rows) == 0: #if the last amount of the path has no dependant
                    longest = max(longest, len(path))
                    #keep track of the longest path so far
                else:
                    for row in rows:
                        if row in path:
                            #if the amount to add in the path is already there, 
                            #it means there is a circular reference
                            raise NotImplementedError('circular reference')
                        #accumulate path at the end of the list of path
                        new_path = deepcopy(path)
                        new_path.append(row)
                        paths_to_check.append(new_path)
            if len(paths_to_check) == 0:
                #no more path to check, out of the loop!
                break
            else:
                paths = deepcopy(paths_to_check)
        longestPath[index] = copy(longest)
    df['calculation order'] = pd.Series(longestPath)
    df = df.sort('calculation order')
    return df
def find_all_paths(graph, start):
    paths = [[start]]
    terminated_paths = []
    longest = 0
    while True:
        paths_to_check = []
        for i in range(len(paths)):
            path = paths[i]
            rows, columns, c = sp.sparse.find(graph.getcol(path[-1]))
            if len(rows) == 0:
                terminated_paths.append(path)
                if len(path) > longest:
                    longest = len(path)
            else:
                for row in rows:
                    if row in path:
                        NotImplementedError('circular reference')
                    new_path = deepcopy(path)
                    new_path.append(row)
                    paths_to_check.append(new_path)
        if len(paths_to_check) == 0:
            break
        else:
            paths = deepcopy(paths_to_check)
    return longest
def recalculate(df):
    minOrder = df['calculation order'].min()
    sel = df[df['calculation order'] == minOrder]
    calculatedAmount = dict(zip(list(sel['variableName']), list(sel['amount'])))
    values = dict(zip(list(sel.index), list(sel['amount'])))
    for index in list(df[df['calculation order'] != minOrder].index):
        m = df.loc[index, 'mathematicalRelation']
        v = df.loc[index, 'variableName']
        if m == '':
            calculatedAmount[v] = copy(df.loc[index, 'amount'])
        else:
            try:
                calculatedAmount[v] = eval(m, calculatedAmount)
            except:
                1/0
        values[index] = copy(calculatedAmount[df.loc[index, 'variableName']])
    df['calculated amount'] = pd.Series(values)
    return df
def validate(ie, ie_index, df_transient, ee_index, B):
    if ie in ie_index:
        for i in range(len(df_transient)):
            sel = df_transient.iloc[i]
            if sel['valueType'] == 'Exchange' and sel['amount'] != 0.:
                if 'Environment' in sel['group']:
                    ee = tuple(sel[['name', 'compartment', 'subcompartment']])
                    test = sel['amount'] / B[ee_index[ee], ie_index[ie]]
                    if test > 1.01 or test < .99:
                        1/0
DBFolder = r'C:\ocelot\databases'
DBName = 'ecoinvent32_internal.pkl'
resultFolder = r'C:\ocelot\excel\datasets'
datasets, masterData, activityOverview, activityLinks = osf.openDB(DBFolder, DBName)
folder = r'C:\python\DB_versions\3.2\cut-off\python variables'
(A, B, C, ee_index, ee_list, ie_index, 
        ie_list, LCIA_index, LCIA_list, units, A_confidential_hidden, 
        B_confidential_hidden) = osf.load_matrices(folder)
Z = osf.Z_from_A(A)
folder = r'C:\ocelot\excel\datasets'
#for dataset in datasets:
for dataset in ['1bb210b5-ed27-4d8f-9d16-63e1455d6c6d_c4ea317c-5719-4f10-9e04-7da3e328a0c4']:
    meta = datasets[dataset]['meta']
    print meta.loc['activityName', 'value'], meta.loc['geography', 'value']
    quantitative = datasets[dataset]['quantitative']
    if meta.loc['wasteOutput', 'value']:
        quantitative = osf.wasteByProductFlip(quantitative, masterData)
    if meta.loc['treatmentActivity', 'value']:
        pass#not sure what to do here
    datasets = {}
    