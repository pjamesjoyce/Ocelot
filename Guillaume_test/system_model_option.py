# -*- coding: utf-8 -*-
import os
import pandas
def readSystemModelOptions(folder, filename, sheetname = 'Sheet1'):
    df = pandas.read_excel(os.path.join(folder, filename), sheetname)
    df = df.set_index('option')
    df['allowed values'] = df['allowed values'].astype(str)
    for index in set(df.index):
        df.loc[index, 'allowed values'] = df.loc[index, 'allowed values'].split('\n')
        if df.loc[index, 'value'] not in df.loc[index, 'allowed values']:
            raise NotImplementedError('''In the file "%s", "%s" is not a valid choice for option "%s".  
                Please select from %s.''' % (filename, df.loc[index, 'value'], 
                index, str(df.loc[index, 'allowed values'])))
    return df
folder = r'C:\ocelot\inputs'
filename = 'system_model_option_definition.xlsx'
systemModelOptions = readSystemModelOptions(folder, filename, sheetname = 'Sheet1')