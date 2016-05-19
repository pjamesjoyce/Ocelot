# -*- coding: utf-8 -*-
import os
import pandas as pd
import time
from cPickle import load
import numpy as np
import ocelot_support_functions as osf
reload(osf)
#import cProfile
#import general_file_functions as gff
#reload(gff)
DBFolder = r'C:\ocelot\databases'
DBName = 'ecoinvent32_internal.pkl'
resultFolder = r'C:\ocelot\excel\datasets'
datasets, masterData, activityOverview, activityLinks = osf.openDB(DBFolder, DBName)
counter = 0
start = time.time()
for datasetFilename in DB:
#for dataset in ['e6f6d6ef-bd24-447b-9181-7e79143ffb74_20fe03e6-8f7e-4f52-9f59-5040fa62e516']:
    counter += 1
    osf.estimate_time(start, counter, len(datasets))
    osf.writeDatasetToExcel(datasets[dataset]['meta'], 
        resultFolder, datasets[datasetFilename]['quantitative'], masterData, 
        activityOverview, cuteName = False)
print time.time() - start
#pr.disable()
#folder = r'C:\ocelot\output'
#gff.profiler_to_excel(pr, folder)