# -*- coding: utf-8 -*-
import ocelot_support_functions as osf
import time
from copy import copy, deepcopy
import pandas as pd
import numpy as np
import re
import scipy as sp
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
def findAllocationFactors(quantitative, masterData):
    allocationFactors = quantitative[quantitative['propertyId'
        ] == '38f94dd1-d5aa-41b8-b182-c0c42985d9dc']
    allocationFactors = allocationFactors[allocationFactors['group'].isin(
        ['ByProduct', 'ReferenceProduct'])]
    allocationFactors = allocationFactors.rename(columns = {'amount': 'price'})
    allocationFactors = allocationFactors[['exchangeId', 'price']].set_index('exchangeId')
    allocationFactors = allocationFactors.join(
        masterData['intermediateExchange'][['classification']])
    allocationFactors = allocationFactors[allocationFactors[
        'classification'] == 'allocatable product']
    sel = quantitative[quantitative['valueType'] == 'Exchange']
    sel = sel[sel['group'].isin(['ByProduct', 'ReferenceProduct'])]
    allocationFactors = allocationFactors.join(sel.set_index('exchangeId')[['amount']])
    allocationFactors['revenu'] = abs(allocationFactors['price'
        ] * allocationFactors['amount'])
    allocationFactors['allocation factor'] = allocationFactors['revenu'
        ] / allocationFactors['revenu'].sum()
    allocationFactors = allocationFactors[allocationFactors['allocation factor'] != 0.]
    return allocationFactors
def economicAllocation(meta, quantitative, masterData, ie_index, ee_index, B, 
        validateAgainstMatrixSwitch, cuteName, logs, resultFolder, writeToExcelSwitch):
    allocationFactors = findAllocationFactors(quantitative, masterData)
    allocatedDatasets = {}
    #extract once exchanges and exchanges to technosphere indexes for convenience
    exchanges = quantitative[quantitative['valueType'] == 'Exchange']
    exchangesToTechnosphere = exchanges[exchanges['group'].isin(
        ['ReferenceProduct', 'ByProduct'])]
    for chosenByProductExchangeId in list(allocationFactors.index):
        allocatedQuantitative = quantitative.copy()
        allocatedMeta = meta.copy()
        #find new reference product
        chosenByProductIndex = exchangesToTechnosphere[
            exchangesToTechnosphere['exchangeId'] == chosenByProductExchangeId].index[0]
        #add new reference product to meta
        allocatedMeta.loc['mainReferenceProductId', 'value'] = copy(chosenByProductExchangeId)
        allocatedMeta.loc['mainReferenceProductIndex', 'value'] = copy(chosenByProductIndex)
        allocatedMeta.loc['mainReferenceProductName', 'value'] = masterData['intermediateExchange'
            ].loc[chosenByProductExchangeId, 'name']
        #put to zero the amount of the other coproducts
        indexes = list(exchangesToTechnosphere.index)
        indexes.remove(chosenByProductIndex)
        allocatedQuantitative.loc[indexes, 'amount'] = 0.
        #make the selected coproduct the reference product
        indexes = allocatedQuantitative[allocatedQuantitative['exchangeId'
            ] == chosenByProductExchangeId]
        indexes = indexes[indexes['group'
            ].isin(['ReferenceProduct', 'ByProduct'])]
        indexes = list(indexes.index)
        allocatedQuantitative.loc[indexes, 'group'] = 'ReferenceProduct'
        #multiply all exchange amounts by allocation factor, except ReferenceProduct
        indexes = list(exchanges.index)
        indexes.remove(chosenByProductIndex)
        allocatedQuantitative.loc[indexes, 'amount'
            ] = allocatedQuantitative.loc[indexes, 'amount'
            ] * allocationFactors.loc[chosenByProductExchangeId, 'allocation factor']
        message = 'successful economic allocation'
        logs = osf.writeInLogs(logs, 'info', economicAllocation, allocatedMeta, 
            allocatedQuantitative, message)
        allocatedDatasets[chosenByProductExchangeId] = {
            'meta': allocatedMeta.copy(), 'quantitative': allocatedQuantitative.copy()}
    return allocatedDatasets, logs
def combinedProduction(quantitative, validateAgainstMatrixSwitch, writeToExcelSwitch, logs, 
        masterData, cuteName, meta, resultFolder):
    referenceProductIndexes = quantitative[quantitative['group'] == 'ReferenceProduct']
    referenceProductIndexes = referenceProductIndexes[
        referenceProductIndexes['valueType'] == 'Exchange']
    referenceProductIndexes = list(referenceProductIndexes.index)
    graph, quantitative = buildGraph(quantitative, combined = True)
    quantitative = calculationOrder(quantitative, graph)
    allocatedDatasets = {}
    for chosenReferenceProductIndex in referenceProductIndexes:
        #update meta
        allocatedMeta = meta.copy()
        allocatedMeta.loc['mainReferenceProductId', 'value'] = quantitative.loc[
            chosenReferenceProductIndex, 'exchangeId']
        allocatedMeta.loc['mainReferenceProductIndex', 'value'] = copy(chosenReferenceProductIndex)
        allocatedMeta.loc['mainReferenceProductName', 'value'] = masterData['intermediateExchange'
            ].loc[allocatedMeta.loc['mainReferenceProductId', 'value'], 'name']
        allocatedQuantitative = quantitative.copy()
        #put to zero the amount of the exchange and PV of the other reference products
        otherReferenceProductIndexes = copy(referenceProductIndexes)
        otherReferenceProductIndexes.remove(chosenReferenceProductIndex)
        otherReferenceProductIds = set(quantitative.loc[otherReferenceProductIndexes, 'exchangeId'])
        toSetToZeroIndexes = quantitative[quantitative['exchangeId'].isin(otherReferenceProductIds)]
        toSetToZeroIndexes = toSetToZeroIndexes[toSetToZeroIndexes['valueType'].isin(
            ['Exchange', 'ProductionVolume'])]
        toSetToZeroIndexes = list(toSetToZeroIndexes.index)
        allocatedQuantitative.loc[toSetToZeroIndexes, 'amount'] = 0.
        #recalculate
        allocatedQuantitative = recalculate(allocatedQuantitative)
        allocatedQuantitative = osf.recalculateUncertainty(allocatedQuantitative)
        allocatedQuantitative['amount'] = allocatedQuantitative['calculated amount'
            ] / abs(quantitative.loc[chosenReferenceProductIndex, 'amount'])
        if validateAgainstMatrixSwitch:
            logs = osf.validateAgainstMatrix(ie_index, allocatedQuantitative, 
                ee_index, B, allocatedMeta, masterData, logs)
        if writeToExcelSwitch:
            osf.writeDatasetToExcel(allocatedMeta.copy(), resultFolder, allocatedQuantitative, 
                masterData, activityOverview, cuteName = cuteName)
        allocatedDatasets[allocatedMeta.loc['mainReferenceProductId', 'value']] = {
            'meta': allocatedMeta.copy(), 'quantitative': allocatedQuantitative.copy()}
    #if 'WithByProduct' in meta.loc['allocationType', 'value']:
    #    1/0
    return allocatedDatasets, logs
logFolder = r'C:\ocelot\logs'
DBFolder = r'C:\ocelot\databases'
DBName = 'ecoinvent32_internal.pkl'
resultFolder = r'C:\ocelot\excel\datasets'
datasets, masterData, activityOverview, activityLinks = osf.openDB(DBFolder, DBName)
matrixFolder = r'C:\python\DB_versions\3.2\cut-off\python variables'
validateAgainstMatrixSwitch = True
writeToExcelSwitch = False
cuteName = True
logs = osf.initializeLogs(logFolder, 'allocation')
(A, B, C, ee_index, ee_list, ie_index, 
            ie_list, LCIA_index, LCIA_list, units, A_confidential_hidden, 
            B_confidential_hidden) = osf.load_matrices(matrixFolder)
start = time.time()
counter = 0
#for dataset in datasets:
for dataset in ['7ad19c9d-644d-497d-bbab-08da582ca3ec_b89dadb0-75e9-44fd-8d41-1ec8dcce23b6']:
    meta = datasets[dataset]['meta']
    print meta.loc['activityName', 'value'], meta.loc['geography', 'value']
    print meta.loc['allocationType', 'value']
    quantitative = datasets[dataset]['quantitative']
    if meta.loc['nonAllocatableByProduct', 'value']:
        quantitative, logs = osf.nonAllocatableByProductFlip(quantitative, masterData, logs)
    if meta.loc['allocationType', 'value'] == 'noAllocation':
        allocatedDatasets = {meta.loc['mainReferenceProductExchangeId', 'value']: 
                datasets[dataset]}
    elif 'combined' in meta.loc['allocationType', 'value']:
        allocatedDatasets, logs = combinedProduction(quantitative, validateAgainstMatrixSwitch, 
            writeToExcelSwitch, logs, masterData, cuteName, meta, resultFolder)
    elif meta.loc['allocationType', 'value'] == 'economicAllocation':
        if 0: #not meta.loc['treatmentActivity', 'value']:
            counter += 1
            print counter
            print meta.loc['activityName', 'value'], meta.loc['geography', 'value']
            allocatedDatasets, logs = economicAllocation(meta, quantitative, 
                masterData, ie_index, ee_index, B, validateAgainstMatrixSwitch, 
                cuteName, logs, resultFolder, writeToExcelSwitch)
    elif meta.loc['allocationType', 'value'] == 'trueValueAllocation':
        pass
    elif meta.loc['allocationType', 'value'] == 'allocatableFromWasteTreatment':
        pass
    elif meta.loc['allocationType', 'value'] == 'constrainedMarket':
        pass
    else:
        raise NotImplementedError('"%s" is not a recognized allocationType')
    for exchangeId in allocatedDatasets:
        allocatedDatasets[exchangeId] = osf.scaleDataset(allocatedDatasets[exchangeId])
    if writeToExcelSwitch:
        osf.writeDatasetToExcel(allocatedMeta.copy(), resultFolder, allocatedQuantitative, 
            masterData, activityOverview, cuteName = cuteName)
    if validateAgainstMatrixSwitch:
        logs = osf.validateAgainstMatrix(ie_index, allocatedQuantitative, 
            ee_index, B, allocatedMeta, masterData, logs)
allocatedDatasetsBeforeMerge = {}
writeToExcelSwitch = False
for exchangeId in allocatedDatasets:
    meta = allocatedDatasets[exchangeId]['meta']
    quantitative = allocatedDatasets[exchangeId]['quantitative']
    allocatedDatasetsBeforeMerge_, logs = economicAllocation(meta, quantitative, masterData, ie_index, 
        ee_index, B, validateAgainstMatrixSwitch, cuteName, logs, resultFolder, writeToExcelSwitch)
    for exchangeId_ in allocatedDatasetsBeforeMerge_:
        if exchangeId_ not in allocatedDatasetsBeforeMerge:
            allocatedDatasetsBeforeMerge[exchangeId_] = {}
        allocatedDatasetsBeforeMerge[exchangeId_][exchangeId
            ] = allocatedDatasetsBeforeMerge_[exchangeId_]
allocatedDatasetsAfterMerge = {}
for exchangeId_ in allocatedDatasetsBeforeMerge:
    if len(allocatedDatasetsBeforeMerge[exchangeId_]) == 1:
        exchangeId = allocatedDatasetsBeforeMerge[exchangeId_].keys()[0]
        allocatedDatasetsAfterMerge[exchangeId_] = deepcopy(allocatedDatasetsBeforeMerge[
            exchangeId_][exchangeId])
    else:
        1/0
        
    
print time.time() - start, 'seconds'
osf.closeLogs(logs)