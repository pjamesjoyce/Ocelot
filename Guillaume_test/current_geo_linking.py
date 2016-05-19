# -*- coding: utf-8 -*-
import general_file_functions as gff
reload(gff)
import spold2_light as spold2
reload(spold2)
from scipy.sparse import find
from pandas import DataFrame, concat, read_excel
from time import localtime, strftime
from copy import deepcopy
import matrix_manipulation_functions as mmp
reload(mmp)
import time
import pandas
import numpy as np
import os
import csv
from uuid import uuid4
import re
import io
import shutil
import datetime
specialActivityTypes = {'0': 'ordinary transforming activity', 
                        '1': 'market activity', 
                        '2': 'IO activity', 
                        '3': 'Residual activity', 
                        '4': 'production mix', 
                        '5': 'import activity', 
                        '6': 'supply mix', 
                        '7': 'export activity', 
                        '8': 're-export activity', 
                        '9': 'correction activity', 
                        '10': 'market group'}
folder = r'C:\python\DB_versions\3.2\undefined\excel and csv'
filename = 'activityLink_overview_3.2.xlsx'
tabname = 'Sheet2'
AL_overview = read_excel(os.path.join(folder, filename), tabname)
AL_overview = AL_overview.set_index(['activityName', 'geography', 
    'name', 'activityLink activityName', 'activityLink geography']).sortlevel(level=0)
AL_overview = set(AL_overview.index)
folder = r'C:\python\DB_versions\3.2\cut-off\python variables'
ao = gff.load_variables([[folder, 'ao']])[0]
ao_for_AL = ao.set_index(['Activity UUID', 'Product']).sortlevel(level=0)
ao = ao.set_index('activityName')
folder = r'C:\python\DB_versions\3.2\cut-off\datasets'
filelist = gff.build_file_list(folder)
results = {}
counter = 0
for filename in filelist:
    counter += 1
    print counter
    f = spold2.Dataset(folder, filename, ao = ao_for_AL)
    b = f.baseline()
    for exc in f.get('FromTechnosphere'):
        baseline = exc.baseline()
        geo1 = f.geography
        if geo1 == 'RoW':
            geo1 = 'GLO'
        geo2 = exc.activityLink_geography
        if geo2 == 'RoW':
            geo2 = 'GLO'
        if not gff.isempty(exc.activityLink_activityName):
            index = (f.activityName, geo1, exc.name, exc.activityLink_activityName, geo2)
            if index not in AL_overview: #manual activity links are taken out of the analysis
                clientSpecialActivityType = specialActivityTypes[f.specialActivityType]
                sel = ao.loc[exc.activityLink_activityName]
                if type(sel) == pandas.core.series.Series:
                    sel = DataFrame(sel).transpose()
                supplierSpecialActivityType = sel.iloc[0]['specialActivityType']
                index = (geo1, geo2, clientSpecialActivityType, supplierSpecialActivityType)
                if index not in results:
                    results[index] = 0
                results[index] += 1
df = DataFrame()
for index in results:
    to_add = {'demanding geo': index[0], 
              'supplying geo': index[1], 
                'demanding specialActivityType': index[2], 
                'supplying specialActivityType': index[3], 
                'frequency': results[index]}
    df = gff.update_df(df, to_add)
cols = ['demanding geo', 'supplying geo', 'demanding specialActivityType', 
        'supplying specialActivityType', 'frequency']
filename = 'current_geo_linking.xlsx'
folder = r'C:\ocelot\output'
df.to_excel(os.path.join(folder, filename), cols = cols, 
            index = False, merge_cells = False)