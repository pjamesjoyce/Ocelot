# -*- coding: utf-8 -*-
import general_file_functions as gff
reload(gff)
import spold2
reload(spold2)
import scipy as sp
from pandas import DataFrame, concat, read_excel
from time import localtime, strftime
from copy import deepcopy
import time
import pandas
import numpy as np
import os
base = r'C:\python\DB_versions'
version = '3.2'
system_model = 'undefined'
basepath = os.path.join(base, version, system_model)
folder = os.path.join(basepath, 'python variables')
ao = gff.load_variables([[folder, 'ao']])[0]
ao = ao[ao['Activity Hidden'] == 'FALSE']
ao_for_AL = ao.set_index(['Activity UUID', 'Product']).sortlevel(level=0)
folder = os.path.join(basepath, 'datasets')
filename = '9ade60c1-95f8-41ec-bc6f-f702107cafd1_1fb2e33c-efb6-42f9-99e0-f9024ace9fcc.spold'
f = spold2.Dataset(folder, filename)
f.prepare_recalculate()
#identify all elements that could be used as amount, or calculated
#exchange amount
all_values = DataFrame()
#exchange property
#PV
#parameters
#build a graph matrix
#find order for calculation
#calculate