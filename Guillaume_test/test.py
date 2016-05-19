# -*- coding: utf-8 -*-
import re
m = '414/1072/11/1.39'
int_division = re.compile('/\d+[^./]')
#int_division = re.compile('/\d+')
matches = int_division.findall(m)
for match in matches:
    m = m.replace(match, match+'.')
print m
