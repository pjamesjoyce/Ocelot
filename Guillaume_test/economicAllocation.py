# -*- coding: utf-8 -*-
import ocelot_support_functions as osf
import time
from copy import copy, deepcopy
reload(osf)
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
def economicAllocation(meta, quantitative, masterData, ie_index, 
        ee_index, B, validateAgainstMatrixSwitch, cuteName, logs):
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
        #divide all exchange amounts by abs(amount of the new reference product)
        indexes = allocatedQuantitative[allocatedQuantitative[
            'valueType'] == 'Exchange']
        indexes = list(indexes.index)
        allocatedQuantitative.loc[indexes, 'amount'
            ] = allocatedQuantitative.loc[indexes, 'amount'
            ] / abs(quantitative.loc[chosenByProductIndex, 'amount'])
        allocatedQuantitative = osf.recalculateUncertainty(allocatedQuantitative)
        if writeToExcelSwitch:
            osf.writeDatasetToExcel(allocatedMeta.copy(), resultFolder, allocatedQuantitative, 
                masterData, activityOverview, cuteName = cuteName)
        if validateAgainstMatrixSwitch:
            logs = osf.validateAgainstMatrix(ie_index, allocatedQuantitative, 
                ee_index, B, allocatedMeta, masterData, logs)
        message = 'successful economic allocation'
        logs = osf.writeInLogs(logs, 'info', economicAllocation, allocatedMeta, 
            allocatedQuantitative, message)
        allocatedDatasets[chosenByProductExchangeId] = {
            'meta': allocatedMeta.copy(), 'quantitative': allocatedQuantitative.copy()}
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
for dataset in datasets:
#for dataset in ['c5c1f826-fd6d-4daa-bf80-6c8ee1505074_b2c3a391-3842-4046-8955-8ae53160a676']:
    meta = datasets[dataset]['meta']
    quantitative = datasets[dataset]['quantitative']
    if meta.loc['wasteOutput', 'value']:
        quantitative, logs = osf.wasteByProductFlip(quantitative, masterData, logs)
    if meta.loc['allocationType', 'value'] == 'noAllocation':
        allocatedDatasets = deepcopy(datasets[dataset])
    elif 'combined' in meta.loc['allocationType', 'value']:
        if 0:
            pass
    elif meta.loc['allocationType', 'value'] == 'economicAllocation':
        if not meta.loc['treatmentActivity', 'value']:
            counter += 1
            print counter
            print meta.loc['activityName', 'value'], meta.loc['geography', 'value']
            allocatedDatasets, logs = economicAllocation(meta, quantitative, 
                masterData, ie_index, ee_index, B, validateAgainstMatrixSwitch, 
                cuteName, logs)
    elif meta.loc['allocationType', 'value'] == 'trueValueAllocation':
        pass
    else:
        raise NotImplementedError('"%s" is not a recognized allocationType')
print time.time() - start, 'seconds'
osf.closeLogs(logs)