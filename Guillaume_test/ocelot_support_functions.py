# -*- coding: utf-8 -*-
from copy import deepcopy, copy
import numpy as np
import scipy as sp
import pandas as pd
import os
from cPickle import load
import time
import io
tag_prefix = '{http://www.EcoInvent.org/EcoSpold02}'
technologyLevels = {0: 'Undefined', 
                    1: 'New', 
                    2: 'Modern', 
                    3: 'Current', 
                    4: 'Old', 
                    5: 'Outdated'}
specialActivityTypes = {0: 'ordinary transforming activity', 
                        1: 'market activity', 
                        10: 'market group'}
accessRestrictedTos = {0: 'Public', 
                    1: 'Licensee', 
                    2: 'Results', 
                    3: 'Restricted', 
                    None: ''}
def ie_name_chop(ie):
    #input is a simapro format name
    #example: electricity, high voltage//[GR] electricity, high voltage, production mix
    #output: product, activityName, country
    product, country_activityName = ie.split('//')
    transient = country_activityName.split(']')
    if len(transient) == 2:
        activityName = transient[1][1:]
    elif len(transient) == 3:
        activityName = transient[1][1:] + ']' + transient[2]
    country = transient[0][1:]
    return str(product), str(activityName), str(country)
def ie_name_merge(activityName, geography, product):
    #input is activityName, country and product
    #output is a simapro format intermediate exchange name
    return '%s//[%s] %s' % (product, geography, activityName)
def load_variables(all_info):
    #all_info = [[path, variable_name], [path, variable_name], ...]
    variables = []
    for path, variable_name in all_info:
        filename = os.path.join(path, variable_name + '.pkl')
        variables.append(load(open(filename, 'rb')))
    return variables
def load_matrices(path):
    #(A, B, C, ee_index, ee_list, ie_index, 
        #ie_list, LCIA_index, LCIA_list, units, A_confidential_hidden, 
        #B_confidential_hidden) = mmf.load_matrices(folder)
    matrix_names = ['A', 'B', 'C', 'ee_index', 'ee_list', 'ie_index', 'ie_list', 'LCIA_index', 
        'LCIA_list', 'units', 'A_confidential_hidden', 'B_confidential_hidden']
    all_info = zip([path]*len(matrix_names), matrix_names)
    all_variables = load_variables(all_info)
    return all_variables
def Z_from_A(A):
    rows = [i for i in range(A.shape[0])]
    columns = rows
    coefficients = [1. for i in range(A.shape[0])]
    ij = np.vstack((rows, columns))
    I = sp.sparse.coo_matrix((coefficients,ij), 
                        shape = A.shape).tocsc()
    Z = I - A
    return Z
def build_file_list(dirpath, extension = None):
    pre_list = os.listdir(dirpath)
    if extension == None:
        filelist = [filename for filename in pre_list 
            if os.path.isfile(os.path.join(dirpath, filename)) and '~' not in filename]
    elif type(extension) == list:
        filelist = [filename for filename in pre_list 
            if os.path.isfile(os.path.join(dirpath, filename))
            and filename.split('.')[-1].lower() in extension and '~' not in filename]
    else:
        filelist = [filename for filename in pre_list 
            if os.path.isfile(os.path.join(dirpath, filename))
            and filename.split('.')[-1].lower() == extension and '~' not in filename]
    return filelist
def openDB(DBFolder, DBName):
    f = open(os.path.join(DBFolder, DBName), 'rb')
    DB = load(f)
    f.close()
    return DB['datasets'], DB['masterData'], DB['activityOverview'], DB['activityLinks']
def findReferenceProduct(quantitative, masterData):
    df = quantitative[quantitative['valueType'] == 'Exchange']
    df = df[df['group'] == 'ReferenceProduct'].sort('amount', ascending = False)
    name = masterData['intermediateExchange'].loc[df.iloc[0]['exchangeId'], 'name']
    index = df.iloc[0].name
    return name, index
def prepareWriter(dataset, resultFolder, overwriteName, cuteName):
    meta = dataset['meta']
    if overwriteName != '':
        filename = overwriteName
    elif cuteName:
        filename = '%s - %s - %s.xlsx' % tuple(
            meta.loc[['activityName', 'geography', 'mainReferenceProductName'], 
            'value'])
        filename = filename.replace('/', '_')
    else:
        filename = meta.loc['filename', 'value'].replace('.spold', '.xlsx')
    writer = pd.ExcelWriter(os.path.join(resultFolder, filename))
    return writer
def prepareMeta(dataset, writer):
    meta = dataset['meta']
    try:
        meta.loc['technologyLevel', 'value'] = technologyLevels[
            meta.loc['technologyLevel', 'value']]
    except KeyError:
        pass
    try:
        meta.loc['specialActivityType', 'value'] = specialActivityTypes[
            meta.loc['specialActivityType', 'value']]
    except KeyError:
        pass
    try:
        meta.loc['accessRestrictedTo', 'value'] = accessRestrictedTos[
            meta.loc['accessRestrictedTo', 'value']]
    except KeyError:
        pass
    meta = meta.loc[['filename', 'activityName', 'geography', 'mainReferenceProductName', 
                     'startDate', 'endDate', 
      'specialActivityType', 'technologyLevel', 'accessRestrictedTo', 'allocationType', 
      'hasNonAllocatableByProduct', 'lastOperationPerformed']]
    meta.reset_index().rename(columns = {'index': 'field'}
        ).to_excel(writer, 'meta', cols = ['field', 'value'], 
        merge_cells = False, index = False)
    return writer
def prepareQuantitative(dataset, activityOverview, masterData, writer):
    quantitative = dataset['quantitative']
    properties = quantitative[quantitative['valueType'] == 'Property']
    indexes = set(quantitative.index).difference(set(properties.index))
    quantitative = quantitative.loc[indexes]
    if len(properties) > 0:
        properties = properties.set_index('propertyId')
        properties = properties.join(masterData['properties']).reset_index()
    ee = quantitative[quantitative['group'].isin(['FromEnvironment', 'ToEnvironment'])]
    ie = quantitative[quantitative['group'].isin(['ReferenceProduct', 'ByProduct', 'FromTechnosphere'])]
    parameters = quantitative[quantitative['valueType'] == 'Parameter']
    if len(parameters) > 0:
        parameters = parameters.set_index('parameterId')
        parameters = parameters.join(masterData['parameters']).reset_index()
    if len(ee) > 0:
        ee = ee.set_index(['exchangeId', 'subcompartmentId'])
        ee = ee.join(masterData['elementaryExchange'][['name', 'compartment', 
                     'subcompartment', 'unit']]).reset_index()
        for col in ['activityLinkId']:
            del ee[col]
    ie = ie.set_index('exchangeId')
    ie = ie.join(masterData['intermediateExchange'][['name', 'unit']]).reset_index()
    ie = ie.set_index('activityLinkId', 'name')
    ie = ie.join(activityOverview[['activityName', 'geography']]).reset_index()
    ie = ie.rename(columns = {'activityName': 'activityLink activityName', 
                              'geography': 'activityLink geography'})
    for col in ['level_0', 'index']:
        del ie[col]
    quantitative = pd.concat([ie, ee])
    cols = ['valueType', 'Ref', 'group', 'name', 'compartment', 'subcompartment', 'classification', 
            'activityLink activityName', 'activityLink geography', 'propertyName', 
            'parameterName', 'amount', 'unit', 'variableName', 'mathematicalRelation', 
            'uncertaintyType', 'meanValue', 'minValue', 'mostLikelyValue', 
            'maxValue', 'variance', 'pedigreeMatrix', 'standardDeviation95', 
            'varianceWithPedigreeUncertainty', 'mu', 'sigma']
    quantitative = quantitative.sort(['group', 'name', 'valueType'])
    quantitative = pd.concat([quantitative, parameters, properties])
    for col in cols:
        if col not in quantitative.columns:
            quantitative[col] = ''
    quantitative['pedigreeMatrix'] = quantitative['pedigreeMatrix'].astype(str)
    exchanges = quantitative[quantitative['valueType'] == 'Exchange']
    ReferenceProduct = exchanges[exchanges['group'] == 'ReferenceProduct']
    ByProduct = exchanges[exchanges['group'] == 'ByProduct']
    FromTechnosphere = exchanges[exchanges['group'] == 'FromTechnosphere']
    ToEnvironment = exchanges[exchanges['group'] == 'ToEnvironment']
    ToEnvironment = ToEnvironment.sort('name')
    FromEnvironment = exchanges[exchanges['group'] == 'FromEnvironment']
    others = quantitative[quantitative['valueType'] != 'Exchange']
    quantitative = pd.concat([ReferenceProduct, ByProduct, 
        FromTechnosphere, ToEnvironment, FromEnvironment, others])
    quantitative.to_excel(writer, 'quantitative', cols = cols, 
        merge_cells = False, index = False)
    return writer
def estimate_time(start, counter, max_counter):
    per_iteration = (time.time() - start) / float(counter)
    t = (max_counter - counter) * per_iteration
    print '%s of %s' % (counter, max_counter)
    if t < 60.:
        print t, 'seconds remaining'
    elif t < 3600.:
        print t/60., 'minutes remaining'
    else:
        h = np.floor(t/3600)
        m = (t - 3600.*h) / 60.
        print h, 'hours and', m, 'minutes remaining'
    print per_iteration, 'seconds per iteration, average'
    return t
def removeUnnecessaryPV(dataset):
    quantitative = dataset['quantitative']
    conditions = ~((quantitative['valueType'] == 'ProductionVolume') & (quantitative['group'] == 'FromTechnosphere'))
    quantitative = quantitative[conditions]
    dataset['quantitative'] = quantitative.copy()
    return dataset
def nonAllocatableByProductFlip(dataset, masterData, logs):
    #joining with masterData to get the classification
    quantitative = dataset['quantitative']
    #all waste in byproduct should be labeled FromTechnosphere
    toFlip = quantitative[quantitative['group'] == 'ByProduct']
    toFlip = toFlip[toFlip['classification'].isin(['Waste', 'Recyclable'])]
    toFlipIndexes = list(toFlip.index)
    quantitative.loc[toFlipIndexes, 'group'] = 'FromTechnosphere'
    #only the exchange amounts should have their sign changed
    toFlip = toFlip[toFlip['valueType'] == 'Exchange']
    toFlipIndexes = list(toFlip.index)
    quantitative.loc[toFlipIndexes, 'amount'] = -quantitative.loc[toFlipIndexes, 'amount']
    #do something with logs
    dataset['quantitative'] = quantitative
    return dataset, logs
def recalculateUncertainty(quantitative):
    #write me!
    return quantitative
def validateAgainstMatrix(ie_index, dataset, ee_index, B, masterData, 
        logs, referenceIndex = False):
    quantitative = dataset['quantitative']
    meta = dataset['meta']
    if referenceIndex == False:
        name, referenceIndex = findReferenceProduct(quantitative, masterData)
    else:
        name = masterData['intermediateExchange'].loc[
            quantitative.loc[referenceIndex, 'exchangeId'], 'name']
    ie = ie_name_merge(meta.loc['activityName', 'value'], 
                       meta.loc['geography', 'value'], name)
    if ie not in ie_index:
        ie = ie_name_merge(meta.loc['activityName', 'value'], 'RoW', name)
    if ie in ie_index:
        for i in range(len(quantitative)):
            sel = quantitative.iloc[i]
            if sel['valueType'] == 'Exchange' and sel['amount'] != 0.:
                if 'Environment' in sel['group']:
                    sel2 = masterData['elementaryExchange'].loc[
                        tuple(sel[['exchangeId', 'subcompartmentId']])]
                    ee = tuple(sel2[['name', 'compartment', 'subcompartment']])
                    severity = 'error'
                    message = ''
                    matrixAmount = B[ee_index[ee], ie_index[ie]]
                    if matrixAmount != 0.:
                        test = abs(sel['amount'] / matrixAmount)
                        if test > 1.005 or test < .995:
                            message = 'matrix amount = %s, calculated amount = %s, ratio = %s' % (
                            matrixAmount, sel['amount'], test)
                    elif abs(sel['amount']) > 1.0e-15:
                        message = 'matrix amount = %s, calculated amount = %s' % (
                            matrixAmount, sel['amount'])
                    if message != '':
                        logs = writeInLogs(logs, severity, validateAgainstMatrix, meta, 
                            quantitative, message)
    else:
        severity = 'warning'
        message = 'dataset not found in matrix'
        logs = writeInLogs(logs, severity, validateAgainstMatrix, meta, 
            quantitative, message)
    return logs
def writeDatasetToExcel(dataset, resultFolder, masterData, activityOverview, cuteName = False, 
                        overwriteName = ''):
    writer = prepareWriter(dataset, resultFolder, overwriteName, cuteName)
    writer = prepareMeta(dataset, writer)
    writer = prepareQuantitative(dataset, activityOverview, masterData, writer)
    writer.save()
    writer.close()
def initializeLogs(logFolder, step):
    logs = {}
    header = 'time;function;activityName;geography;reference product;Ref;message\n'
    for severity in ['error', 'warning', 'info']:
        filename = os.path.join(logFolder, '%s_log_%s.txt' % (step, severity))
        logs[severity] = io.open(filename, 'wb')
        #scan the file until a certain line
        logs[severity].write(header)
    return logs
def writeInLogs(logs, severity, function, meta, quantitative, message):
    line = '%s;%s;%s;%s;%s;%s;%s\n' % (
        time.strftime("%a, %d %b %Y %H:%M:%S", time.localtime()), 
        str(function).split('function ')[1].split(' ')[0], 
        meta.loc['activityName', 'value'], 
        meta.loc['geography', 'value'], 
        meta.loc['mainReferenceProductName', 'value'], 
        quantitative.loc[meta.loc['mainReferenceProductIndex', 'value'], 'Ref'], 
        message)
    logs[severity].write(line)
    return logs
def closeLogs(logs):
    for t in logs:
        logs[t].close()
def scaleDataset(dataset):
    scalingExchangeIndex = dataset['meta'].loc['mainReferenceProductIndex', 'value']
    quantitative = dataset['quantitative'].copy()
    indexes = list(quantitative[quantitative['valueType'] == 'Exchange'].index)
    quantitative.loc[indexes, 'amount'] = quantitative.loc[indexes, 'amount'
        ] / abs(quantitative.loc[scalingExchangeIndex, 'amount'])
    quantitative = recalculateUncertainty(quantitative)
    dataset['quantitative'] = quantitative.copy()
    return dataset
def selectExchangesToTechnosphere(quantitative):
    sel = quantitative[quantitative['valueType'] == 'Exchange']
    sel = sel[sel['group'].isin(['ByProduct', 'ReferenceProduct'])]
    return sel
def joinClassification(dataset, masterData):
    if 'classification' not in dataset['quantitative'].columns:
        dataset['quantitative']['original index'] = list(dataset['quantitative'].index)
        dataset['quantitative'] = dataset['quantitative'].set_index('exchangeId')
        dataset['quantitative'] = dataset['quantitative'].join(masterData['intermediateExchange'
            ][['classification']]).reset_index()
        dataset['quantitative'].index = list(dataset['quantitative']['original index'])
        del dataset['quantitative']['original index']
        dataset['quantitative'] = dataset['quantitative'].rename(columns = {'index': 'exchangeId'})
    return dataset