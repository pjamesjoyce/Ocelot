# -*- coding: utf-8 -*-
import os
import numpy as np
from lxml import objectify
from copy import copy, deepcopy
import pandas as pd
import time
from cPickle import dump
import ocelot_support_functions as osf
reload(osf)
#import cProfile
#import general_file_functions as gff
#reload(gff)
def knownIssues(meta, quantitative):
    #fixing issues in mathematicalRelations
    if meta['activityName'] == 'clinker production':
        for index in quantitative:
            if 'clinker_PV' in quantitative[index]['mathematicalRelation']:
                quantitative[index]['mathematicalRelation'] = quantitative[index]['mathematicalRelation'
                    ].replace('clinker_PV', 'clinker_pv')
            elif quantitative[index]['variableName'] == 'clinker_PV':
                quantitative[index]['variableName'] = 'clinker_pv'
    elif meta['activityName'] == 'cement production, alternative constituents 6-20%':
        for index in quantitative:
            if 'ggbfs' in quantitative[index]['mathematicalRelation']:
                quantitative[index]['mathematicalRelation'
                    ] = quantitative[index]['mathematicalRelation'].replace('ggbfs', 'GGBFS')
            elif quantitative[index]['variableName'] == 'ggbfs':
                quantitative[index]['variableName'] = 'GGBFS'
    elif meta['activityName'] == 'ethylene glycol production':
        for index in quantitative:
            if quantitative[index]['variableName'] == 'yield':
                quantitative[index]['variableName'] = 'YIELD'
            elif 'yield' in quantitative[index]['mathematicalRelation']:
                quantitative[index]['mathematicalRelation'
                    ] = quantitative[index]['mathematicalRelation'].replace('yield', 'YIELD')
    elif meta['activityName'] == 'petroleum and gas production, off-shore':
        for index in quantitative:
            if 'petroleum_APV' in quantitative[index]['mathematicalRelation']:
                quantitative[index]['mathematicalRelation'
                    ] = quantitative[index]['mathematicalRelation'].replace(
                    'petroleum_APV', 'petroleum_apv')
            elif '\r\n' in quantitative[index]['mathematicalRelation']:
                quantitative[index]['mathematicalRelation'
                    ] = quantitative[index]['mathematicalRelation'].replace('\r\n', '')
    elif meta['activityName'] == 'benzene chlorination':
        for index in quantitative:
            if 'avoirdupois' in quantitative[index]['mathematicalRelation']:
                quantitative[index]['mathematicalRelation'] = quantitative[index]['mathematicalRelation'
                    ].replace("UnitConversion(152000000, 'pound avoirdupois', 'kg')", 
                    '68949040.24')
    return quantitative
def createEmptyLine(meta):
    to_add = {'valueType': '', 'Ref': '', 'pedigreeMatrix': '', 'exchangeId': '', 
        'mostLikelyValue': '', 'maxValue': '', 'minValue': '', 'variance': '', 
        'standardDeviation95': '', 'meanValue': '', 'group': '', 'activityLinkId': '', 
        'mu': '', 'amount': '', 'uncertaintyType': '', 'subcompartmentId': '', 
        'sigma': '', 'mathematicalRelation': '', 'variableName': '', 
        'parameterId': '', 'propertyId': ''}
    return to_add
def readMeta(folder, filename):
    #stores the stem for future reading for quantitative information
    #stores meta information in a dictionary
    meta = {}
    meta['filename'] = filename
    f = open(os.path.join(folder, filename))
    root = objectify.parse(f).getroot()
    f.close()
    if hasattr(root, 'activityDataset'):#
        stem = root.activityDataset
    else:
        stem = root.childActivityDataset
    meta['activityName'] = stem.activityDescription.activity.activityName.text
    meta['specialActivityType'] = stem.activityDescription.activity.get('specialActivityType')
    meta['geography'] = stem.activityDescription.geography.shortname.text
    meta['technologyLevel'] = stem.activityDescription.technology.get('technologyLevel')
    if meta['technologyLevel'] == 'None':#sometimes not there, should be undefined
        meta['technologyLevel'] = '0'
    meta['startDate'] = stem.activityDescription.timePeriod.get('startDate')
    meta['endDate'] = stem.activityDescription.timePeriod.get('endDate')
    meta['id'] = stem.activityDescription.activity.get('id')
    meta['accessRestrictedTo'
        ] = stem.administrativeInformation.dataGeneratorAndPublication.get(
        'accessRestrictedTo')
    return meta, stem
def readUncertainty(to_add, e):
    #adds uncertainty fields to a quantitative information
    #works for exchange, PV, parameters and properties
    unc = False
    if hasattr(e, 'uncertainty') and e.uncertainty != None:
        unc = e.uncertainty
    elif hasattr(e, 'productionVolumeUncertainty') and e.productionVolumeUncertainty != None:
        unc = e.productionVolumeUncertainty
    if unc != False:
        m = []
        for c in unc.iterchildren():
            tag = c.tag.split('}')[1]
            if tag == 'pedigreeMatrix':
                for criteria in unc.pedigreeMatrix.keys():
                    m.append(int(unc.pedigreeMatrix.get(criteria)))
                to_add['pedigreeMatrix'] = copy(m)
            elif tag != 'comment':
                to_add['uncertaintyType'] = copy(tag)
                unc_ = getattr(unc, tag)
                for attribute in unc_.keys():
                    to_add.update({attribute: float(unc_.get(attribute))})
    return to_add
def readExchangeAmount(to_add, quantitative, exc, meta, forActivityLinks):
    #prepares the line to store for an exchange amount
    to_add['valueType'] = 'Exchange'
    #finds the group
    if hasattr(exc, 'inputGroup'):
        group = exc.inputGroup.text
        if group == '5':
            to_add['group'] = 'FromTechnosphere'
        elif group == '4':
            to_add['group'] = 'FromEnvironment'
        elif group == '1':
            to_add['group'] = 'FromTechnosphere'#'Materials/Fuels'
        elif group == '2':
            to_add['group'] = 'FromTechnosphere'#'Electricity/Heat'
        elif group == '3':
            to_add['group'] = 'FromTechnosphere'#'Services'
    elif hasattr(exc, 'outputGroup'):
        group = exc.outputGroup.text
        if group == '0':
            to_add['group'] = 'ReferenceProduct'
        elif group == '2':
            to_add['group'] = 'ByProduct'
        elif group == '4':
            to_add['group'] = 'ToEnvironment'
        elif group == '3':
            to_add['group'] = 'MaterialForTreatment'#should not happen now
        elif group == '5':
            to_add['group'] = 'StockAdditions'#should not happen now
    if 'combined' in meta['allocationType']: 
        #will require recalculation, so variableName and 
        #mathematicalRelation are necessary
        for field in ['variableName', 'mathematicalRelation']:
            value = exc.get(field)
            if value != None:
                to_add[field] = copy(value)
    #store exchangeId
    if exc.get('intermediateExchangeId') != None:
        to_add['exchangeId'] = exc.get('intermediateExchangeId')
    else:
        to_add['exchangeId'] = exc.get('elementaryExchangeId')
    #store activityLinkId
    if exc.get('activityLinkId') != None:
        to_add['activityLinkId'] = exc.get('activityLinkId')
    to_add['amount'] = float(exc.get('amount'))
    to_add['Ref'] = "Ref('%s')" % exc.get('id')
    if hasattr(exc, 'compartment'):
        #subcompartmentId is sufficient to identify subcompartment and compartment
        to_add['subcompartmentId'] = exc.compartment.get('subcompartmentId')
    #add uncertainty if any
    to_add = readUncertainty(to_add, exc)
    quantitative[len(quantitative)] = copy(to_add)
    if to_add['activityLinkId'] != '':
        #further treatment necessary if an activityLink is present
        to_add_copy = copy(to_add)
        comments = []
        for c in exc.iterchildren(tag = osf.tag_prefix + 'comment'):
            comments.append(c)
        to_add_copy['comments'] = str(comments)
        forActivityLinks.append(to_add_copy)
    return quantitative, to_add, forActivityLinks
def readProperty(quantitative, to_add, exc, meta, masterData, propertyFilter = []):
    #prepares the line for the property amount
    for p in exc.iterchildren(tag = osf.tag_prefix + 'property'):
        if len(propertyFilter) == 0 or p.name.text in propertyFilter:
            to_add['valueType'] = 'Property'
            to_add['Ref'] = "Ref('%s', '%s')" % (exc.get('id'), p.get('propertyId'))
            to_add['propertyId'] = p.get('propertyId')
            try:
                to_add['amount'] = float(p.get('amount'))
            except: #some properties are there but empty 
                pass
            if 'combined' in meta['allocationType']:
                for field in ['variableName', 'mathematicalRelation']:
                    value = p.get(field)
                    if value != None:
                        to_add[field] = copy(value)
                    else:
                        to_add[field] = ''
            to_add = readUncertainty(to_add, p)
            quantitative[len(quantitative)] = copy(to_add)
            masterData = fillMDProperty(masterData, p)
    return quantitative, masterData
def readProductionVolume(quantitative, to_add, exc, meta):
    #prepares the line for the production volume
    to_add['valueType'] = 'ProductionVolume'
    to_add['Ref'] = "Ref('%s', 'ProductionVolume')" % exc.get('id')
    #Output to technosphere should have a PV.  If not there, zero is forced
    try:
        to_add['amount'] = float(exc.get('productionVolumeAmount'))
    except TypeError:
        to_add['amount'] = 0.
    if 'combined' in meta['allocationType']:
        if exc.get('productionVolumeMathematicalRelation') != None:
            to_add['mathematicalRelation'] = exc.get('productionVolumeMathematicalRelation')
        else:
            to_add['mathematicalRelation'] = ''
        if exc.get('productionVolumeVariableName') != None:
            to_add['variableName'] = exc.get('productionVolumeVariableName')
        else:
            to_add['variableName'] = ''
    to_add = readUncertainty(to_add, exc)
    quantitative[len(quantitative)] = copy(to_add)
    return quantitative
def readParameter(quantitative, p, masterData):
    #prepares the line for a parameter
    to_add = createEmptyLine(meta)
    to_add['valueType'] = 'Parameter'
    to_add['parameterId'] = p.get('parameterId')
    to_add['amount'] = float(p.get('amount'))
    to_add['Ref'] = "Ref('%s')" % p.get('parameterId')
    for field in ['variableName', 'mathematicalRelation']:
        value = p.get(field)
        if value != None:
            to_add[field] = copy(value)
        else:
            to_add[field] = ''
    to_add = readUncertainty(to_add, p)
    quantitative[len(quantitative)] = to_add
    masterData = fillMDParameter(masterData, p)
    return quantitative, masterData
def findAllocationType(meta, stem):
    #depending on the allocation type, more or less information has to be
    #gathered in the readQuantitative function.
    #gather all outputs to technosphere
    toTechnospheres = {} #to be filled for activityOverview
    hasTrueValue = False
    maxAmount = 0.
    meta['nonAllocatableByProduct'] = False
    meta['treatmentActivity'] = False
    nbReferenceProducts = 0
    nbAllocatableByProducts = 0
    nbNonAllocatableByProducts = 0
    hasConditionalExchange = False
    for exc in stem.flowData.iterchildren(tag = osf.tag_prefix + 'intermediateExchange'):
        amount = float(exc.get('amount'))
        if hasattr(exc, 'outputGroup'):
            to_add = {'name': exc.name.text, 
                      'amount': float(exc.get('amount')), 
                        'exchangeId': exc.get('intermediateExchangeId')}
            PV = exc.get('productionVolumeAmount')
            if PV != None: #no PV for markets, but it means zero
                to_add['productionVolumeAmount'] = float(exc.get('productionVolumeAmount'))
            else:
                to_add['productionVolumeAmount'] = 0.
            for c in exc.iterchildren(tag = osf.tag_prefix + 'classification'):
                if c.classificationSystem.text == 'By-product classification':
                    to_add['classification'] = c.classificationValue.text
                    break
            if exc.outputGroup.text == '0':
                to_add['group'] = 'ReferenceProduct'
            else:
                to_add['group'] = 'ByProduct'
            toTechnospheres[len(toTechnospheres)] = copy(to_add)
            if amount != 0.:
                if to_add['group'] == 'ReferenceProduct':
                    nbReferenceProducts += 1
                    if amount < 0. and meta['specialActivityType'] == '0':
                        meta['treatmentActivity'] = True
                    if maxAmount == 0.:
                        maxAmount = copy(amount)
                        mainReferenceProduct = deepcopy(exc)
                    elif amount > maxAmount:
                        maxAmount = copy(amount)
                        mainReferenceProduct = deepcopy(exc)
                else:
                    if to_add['classification'] != 'allocatable product':
                        meta['nonAllocatableByProduct'] = True
                        nbNonAllocatableByProducts += 1
                    else:
                        nbAllocatableByProducts += 1
                    if (exc.get('activityLinkId') != None and 
                            meta['specialActivityType'] == '1' and
                            amount < 0.):
                        hasConditionalExchange = True
                for p in exc.iterchildren(tag = osf.tag_prefix + 'property'):
                    if p.name.text == 'true value relation':
                        hasTrueValue = True
    if meta['specialActivityType'] == '10': #market group
        meta['allocationType'] = 'noAllocation'
    elif meta['specialActivityType'] == '1': #market
        if hasConditionalExchange:
            meta['allocationType'] = 'constrainedMarket'
        else:
            meta['allocationType'] = 'noAllocation'
    else:#ordinary transforming activity
        if nbReferenceProducts + nbAllocatableByProducts == 1:
            meta['allocationType'] = 'noAllocation'
        elif nbReferenceProducts > 1:
            if nbAllocatableByProducts > 0:
                meta['allocationType'] = 'combinedProductionWithByProduct'
            else:
                meta['allocationType'] = 'combinedProductionWithoutByProduct'
            if hasTrueValue:
                raise NotImplementedError('allocationType not recognized')
        elif hasTrueValue:
            meta['allocationType'] = 'trueValueAllocation'
        else:
            if meta['treatmentActivity']:
                meta['allocationType'] = 'allocatableFromWasteTreatment'
            else:
                meta['allocationType'] = 'economicAllocation'
    meta['mainReferenceProductName'] = copy(mainReferenceProduct.name.text)
    meta['mainReferenceProductExchangeId'] = mainReferenceProduct.get('intermediateExchangeId')
    toTechnospheres = pd.DataFrame(toTechnospheres).transpose()
    return meta, toTechnospheres
def readActivityLinks(forActivityLinks, position_ref, activityLinks, meta, 
        quantitative):
    #prepares line in the activityLink overview
    ref_amount = quantitative[position_ref]
    ref_PV = quantitative[position_ref+1]
    for exchange_with_AL in forActivityLinks:
        to_add = {'filename': meta['filename'], 
                   'exchangeId': exchange_with_AL['exchangeId'], 
                    'group': exchange_with_AL['group'], 
                    'activityLinkId': exchange_with_AL['activityLinkId'], 
                    'comments': exchange_with_AL['comments'], 
                    'amount': exchange_with_AL['amount'], 
                    'note': ''}
        if exchange_with_AL['group'] == 'FromTechnosphere':
            to_add['PV consumed'] = abs(exchange_with_AL['amount'] / 
                ref_amount['amount'] * ref_PV['amount'])
            if exchange_with_AL['activityLinkId'] == meta['id']:
                to_add['note'] = 'loss'
        elif exchange_with_AL['group'] == 'ByProduct':
            if to_add['amount'] < 0. and meta['allocationType'] == 'constrainedMarket':
                to_add['note'] = 'conditionalExchange'
        else:
            to_add['note'] = 'wtf!'
        activityLinks[len(activityLinks)] = copy(to_add)
    return activityLinks
def readQuantitative(stem, masterData, meta, activityLinks):
    #compile quantitative info about exchange amount, PV, properties and parameters
    quantitative = {}
    forActivityLinks = []
    for element in stem.flowData.iterchildren():
        if 'Exchange' in element.tag: #excludes parameters
            to_add = createEmptyLine(meta)
            quantitative, to_add, forActivityLinks = readExchangeAmount(to_add, 
                quantitative, element, meta, forActivityLinks)
            masterData = fillMDExchange(meta, to_add, element, masterData)#add info to MD
            if to_add['group'] in ['ReferenceProduct', 'ByProduct']:
                quantitative = readProductionVolume(quantitative, to_add, element, meta)
                if (to_add['group'] == 'ReferenceProduct' and 
                        quantitative[len(quantitative)-2]['amount'] != 0.):
                    position_ref = len(quantitative)-2
            if meta['allocationType'] in ['noAllocation', 'constrainedMarket']:
                #nothing more required
                pass
            elif 'combined' in meta['allocationType']:
                #all properties required
                quantitative, masterData = readProperty(quantitative, to_add, element, 
                    meta, masterData)
            elif meta['allocationType'] in ['economicAllocation', 'allocatableFromWasteTreatment']:
                #only price required
                quantitative, masterData = readProperty(quantitative, to_add, element, 
                    meta, masterData, propertyFilter = ['price'])
            elif meta['allocationType'] == 'trueValueAllocation':
                #only price and true value relation needed
                quantitative, masterData = readProperty(quantitative, to_add, element, 
                    meta, masterData, propertyFilter = ['price', 'true value relation'])
            else:
                raise NotImplementedError('"%s" is not a recognized allocation type' % 
                    meta['allocationType'])
        elif 'combined' in meta['allocationType']:
            #only necessary for combined production
            assert 'parameter' in element.tag
            quantitative, masterData = readParameter(quantitative, element, masterData)
        print len(quantitative), 
        if len(quantitative) != 0:
            print max(quantitative.keys())
        else:
            print 0
        print ''
    #fill info about activityLink overview
    activityLinks = readActivityLinks(forActivityLinks, position_ref, 
        activityLinks, meta, quantitative)
    return quantitative, masterData, meta, activityLinks
def fillMDExchange(meta, to_add, exc, masterData):
    #filling MasterData for exchanges
    if 'Environment' in to_add['group']:
        id = (to_add['exchangeId'], to_add['subcompartmentId'])
        if id not in masterData['elementaryExchange']:
            masterData['elementaryExchange'][id] = {}
            masterData['elementaryExchange'][id]['name'] = exc.name.text
            masterData['elementaryExchange'][id]['unit'] = exc.unitName.text
            masterData['elementaryExchange'][id]['compartment'] = exc.compartment.compartment.text
            masterData['elementaryExchange'][id]['subcompartment'] = exc.compartment.subcompartment.text
            masterData['elementaryExchange'][id]['elementaryExchangeId'] = id[0]
            masterData['elementaryExchange'][id]['subcompartmentId'] = id[1]
    else:
        if to_add['exchangeId'] not in masterData['intermediateExchange']:
            id = to_add['exchangeId']
            masterData['intermediateExchange'][id] = {}
            masterData['intermediateExchange'][id]['name'] = exc.name.text
            masterData['intermediateExchange'][id]['unit'] = exc.unitName.text
            for c in exc.iterchildren(tag = osf.tag_prefix + 'classification'):
                if c.classificationSystem.text == 'By-product classification':
                    masterData['intermediateExchange'][id]['classification'
                        ] = exc.classification.classificationValue.text
                    break
            #This last info might get changed when market read
    return masterData
def fillMDParameter(masterData, p):
    #filling MasterData for parameter
    id = p.get('parameterId')
    if id not in masterData['parameters']:
        masterData['parameters'][id] = {}
        masterData['parameters'][id]['parameterName'] = p.name.text
        if hasattr(p, 'unitName'):
            masterData['parameters'][id]['unit'] = p.unitName.text
        else:
            masterData['parameters'][id]['unit'] = 'dimensionless'
    return masterData
def fillMDProperty(masterData, p):
    #filling MasterData for property
    id = p.get('propertyId')
    if id not in masterData['properties']:
        masterData['properties'][id] = {}
        masterData['properties'][id]['propertyName'] = p.name.text
        if hasattr(p, 'unitName'):
            masterData['properties'][id]['unit'] = p.unitName.text
        else:
            masterData['properties'][id]['unit'] = 'dimensionless'
    return masterData
def writeDatabase(DBFilename, resultFolderDB, datasets, activityOverview, 
                  activityLinks, masterData):
    for key in masterData:
        masterData[key] = pd.DataFrame(masterData[key]).transpose()
        if key == 'elementaryExchange':
            masterData[key] = masterData[key].reset_index()
            masterData[key] = masterData[key].set_index(
                ['elementaryExchangeId', 'subcompartmentId'])
    activityOverview = pd.DataFrame(activityOverview).transpose().reset_index()
    activityLinks = pd.DataFrame(activityLinks).transpose().reset_index()
    DB = {'datasets': datasets, 
          'activityOverview': activityOverview, 
          'activityLinks': activityLinks, 
          'masterData': masterData}
    file = open(os.path.join(resultFolderDB, DBFilename), 'wb')
    dump(DB, file)
    file.close()
    return DB
def writeSupportExcel(resultFolderExcel, DB, DBFilename, resultFolderDB):
    #for user comfort, writes MD, activityOverview and activityLinks in excel
    readme = {'database name': DBFilename, 
              'database location': resultFolderDB}
    readme = pd.DataFrame({'value': readme}).reset_index()
    readme = readme.rename(columns = {'index': 'field'})
    filename = '%s_MasterData.xlsx' % DBFilename.replace('.pkl', '')
    writer = pd.ExcelWriter(os.path.join(resultFolderExcel, filename))
    readme.to_excel(writer, 'readme', 
        cols = ['field', 'value'], index = False, merge_cells = False)
    intermediateExchange = DB['masterData']['intermediateExchange'].reset_index()
    intermediateExchange = intermediateExchange.rename(columns = {'index': 'intermediateExchangeId'})
    cols = ['intermediateExchangeId', 'name', 'unit', 'classification']
    intermediateExchange.to_excel(writer, 'intermediateExchanges', 
        cols = cols, index = False, merge_cells = False)
    df = DB['masterData']['elementaryExchange'].reset_index()
    cols = ['elementaryExchangeId', 'subcompartmentId', 
            'name', 'compartment', 'subcompartment', 'unit']
    df.to_excel(writer, 'elementaryExchanges',  
        cols = cols, index = False, merge_cells = False)
    df = DB['masterData']['parameters'].reset_index()
    df = df.rename(columns = {'index': 'parameterId'})
    cols = ['parameterName', 'parameterId', 'unit']
    df.to_excel(writer, 'parameters',  
        cols = cols, index = False, merge_cells = False)
    df = DB['masterData']['properties'].reset_index()
    df = df.rename(columns = {'index': 'propertyId'})
    cols = ['propertyName', 'propertyId', 'unit']
    df.to_excel(writer, 'properties',  
        cols = cols, index = False, merge_cells = False)
    writer.save()
    writer.close()
    filename = '%s_activityOverview.xlsx' % DBFilename.replace('.pkl', '')
    writer = pd.ExcelWriter(os.path.join(resultFolderExcel, filename))
    readme.to_excel(writer, 'readme', 
        cols = ['field', 'value'], index = False, merge_cells = False)
    activityOverview = DB['activityOverview']
    activityOverview = activityOverview.set_index('exchangeId')
    intermediateExchange = intermediateExchange.set_index('intermediateExchangeId')
    activityOverview = activityOverview.join(
        intermediateExchange[['unit']]).reset_index()
    activityOverview = activityOverview.rename(columns = {'name': 'product'})
    cols = ['filename', 'id', 'activityName', 'geography', 'specialActivityType', 
            'accessRestrictedTo', 'startDate', 
            'endDate', 'group', 'product', 'amount', 'unit', 'productionVolumeAmount', 
            'classification', 'allocationType', 'treatmentActivity', 
            'nonAllocatableByProduct']
    activityOverview = activityOverview.replace(to_replace = {
        'specialActivityType': osf.specialActivityTypes})
    activityOverview = activityOverview.replace(to_replace = {
        'accessRestrictedTo': osf.accessRestrictedTos})
    activityOverview = activityOverview.sort(['activityName', 'geography'])
    activityOverview.to_excel(writer, 'activityOverview', 
        cols = cols, index = False, merge_cells = False)
    writer.save()
    writer.close()
    filename = '%s_activityLinks.xlsx' % DBFilename.replace('.pkl', '')
    writer = pd.ExcelWriter(os.path.join(resultFolderExcel, filename))
    readme.to_excel(writer, 'readme', 
        cols = ['field', 'value'], index = False, merge_cells = False)
    activityLinks = DB['activityLinks']
    activityLinks = activityLinks.set_index('filename')
    activityOverview = activityOverview.set_index('filename')
    activityLinks = activityLinks.join(
        activityOverview[['activityName', 'geography']]
        ).reset_index()
    activityLinks = activityLinks.set_index('exchangeId')
    activityLinks = activityLinks.join(
        intermediateExchange[['name', 'unit']]).reset_index()
    activityLinks = activityLinks.set_index(['activityLinkId', 'name'])
    activityOverview = activityOverview.set_index(['id', 'product'])
    activityLinks = activityLinks.join(
        activityOverview[['activityName', 'geography', 'productionVolumeAmount']], 
        rsuffix = '_')
    del activityLinks['level_0']
    activityLinks = activityLinks.reset_index().rename(columns = {
        'activityName_': 'activityLink activityName', 
        'geography_': 'activityLink geography', 
        'productionVolumeAmount': 'PV available', 
        'level_1': 'name'})
    cols = ['activityName', 'geography', 'group', 'name', 'activityLink activityName', 
            'activityLink geography', 'amount', 'PV consumed', 'PV available', 'comments', 'note']
    activityLinks.drop_duplicates().to_excel(writer, 'activityLinks',  
        cols = cols, index = False, merge_cells = False)
    writer.save()
    writer.close()
def buildActivityOverview(meta, activityOverview, quantitative, 
        toTechnospheres):
    #fill lines in the activity overview based on outputs to technosphere
    for index in range(len(toTechnospheres)):
        to_add = dict(zip(list(toTechnospheres.columns), list(toTechnospheres.iloc[index])))
        to_add.update(meta)
        activityOverview[len(activityOverview)] = copy(to_add)
    return activityOverview
#pr = cProfile.Profile()
#pr.enable()
spolFolder = r'C:\python\DB_versions\3.2\undefined\datasets'#where the spold files are
filelist = osf.build_file_list(spolFolder, 'spold')#list of spolds to iterate
DBFilename = 'ecoinvent32_internal.pkl'#name of the database
#DBFilename = 'economicAllocation.pkl'#name of the database
resultFolderDB = r'C:\ocelot\databases'#where the database will land
resultFolderExcel = r'C:\ocelot\excel\support'#where the support excel will land
#filelist = ['002da2f2-595b-427e-ae3a-3f7dcd769715_6eb408db-980a-4b9e-82a8-b6dca183ec35.spold']
masterData = {}
for field in ['intermediateExchange', 'elementaryExchange', 
              'parameters', 'properties']:
    masterData[field] = {}
activityOverview = {}
activityLinks = {}
datasets = {}
counter = 0
start = time.time()
filelist = ['a6bbe7bb-7b64-4da5-be96-6ba658055690_e6aad2de-0b1b-49c3-a0c4-797ba34d87e5.spold']
for filename in filelist:
    counter += 1
    osf.estimate_time(start, counter, len(filelist))
    #store meta information for each dataset
    meta, stem = readMeta(spolFolder, filename)
    #find the type of allocation
    meta, toTechnospheres = findAllocationType(meta, stem)
    #store quantitative info
    quantitative, masterData, meta, activityLinks = readQuantitative(
        stem, masterData, meta, activityLinks)
    quantitative = knownIssues(meta, quantitative)
    activityOverview = buildActivityOverview(meta, activityOverview, 
        quantitative, toTechnospheres)
    quantitative = pd.DataFrame(quantitative).transpose()
    #add main reference exchange index to meta data
    sel = quantitative[quantitative['exchangeId'] == meta['mainReferenceProductExchangeId']]
    sel = sel[sel['group'] == 'ReferenceProduct']
    meta['mainReferenceProductIndex'] = sel[sel['valueType'] == 'Exchange'].iloc[0].name
    meta = pd.DataFrame({'value': meta})
    if 1: #meta.loc['filename', 'value'] == 'economicAllocation':
        datasets[filename.replace('.spold', '')] = {
            'meta': meta, 'quantitative': quantitative}
DB = writeDatabase(DBFilename, resultFolderDB, datasets, activityOverview, 
                  activityLinks, masterData)
writeSupportExcel(resultFolderExcel, DB, DBFilename, resultFolderDB)
#pr.disable()
print time.time() - start, 'seconds'
#folder = r'C:\ocelot\output'
#gff.profiler_to_excel(pr, folder)