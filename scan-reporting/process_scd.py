#!/usr/bin/env python3

# -*- coding: utf-8 -*-
"""
This script takes raw scan data for SCD scans and processes it completely.
This involves:
    1) deidentifying the scans
    2) Running TRUST and generating derived images
    
    
input:
    -i / --infolder : the path to the folder of pt data. of form /Users/manusdonahue/Desktop/Projects/SCD/Data/[PTSTEN_ID]
        this folder should have one subfolder, acquired, which contains the raw scans
    -n / --name : the name of the patient to deidentify. Only required if running step 1
    -s / --steps : the steps to actually calculate, passed as a string of numbers
        if 0, all steps will be carried out. Otherwise, only the steps that appear
        in the string will be carried out. For example, 2 will cause the script
        to only go through step 2. Because there are only steps, multistep specification isn't really needed,
            but you can explicitly specify steps 1 and 2 by passing -s 12
    -h / --hct : the hematocrit as a float between 0 and 1. Required for step 2
    -f / --flip : optional. 1 to invert TRUST, 0 to leave as is (default=0)
    -p / --pttype : the type of patient. 0 for SCA, 1 for control. Required for step 2
"""

import os
import sys
import getopt
import subprocess
import time
import datetime

from helpers import get_terminal, str_time_elapsed

bash_input = sys.argv[1:]
options, remainder = getopt.getopt(bash_input, "i:n:s:h:f:p:", ["infolder=","name=",'steps=','hct=', 'flip=', 'pttype='])


flip = 0

for opt, arg in options:
    if opt in ('-i', '--infile'):
        in_folder = arg
    elif opt in ('-n', '--name'):
        deidentify_name = arg
    elif opt in ('-s', '--steps'):
        steps = arg
    elif opt in ('-h', '--hct'):
        hematocrit = float(arg)
    elif opt in ('-f', '--flip'):
        flip = int(arg)
    elif opt in ('-p', '--pttype'):
        pt_type = int(arg)

try:
    if steps == '0':
        steps = '12'
except NameError:
    print('-s not specified. running all steps')
    steps = '12'
        
try:
    assert os.path.isdir(in_folder)
except AssertionError:
    raise AssertionError('input folder does not exist')


start_stamp = time.time()
now = datetime.datetime.now()
pretty_now = now.strftime("%Y-%m-%d %H:%M:%S")

print(f'\nBegin processing: {pretty_now}')


original_wd = os.getcwd()
pt_id = replacement = get_terminal(in_folder) # if the input folder is named correctly, it is the ID that will replace the pt name

if '1' in steps:
    ##### step 1 : deidentification
    
    try:
        assert type(deidentify_name) == str
    except AssertionError:
        raise AssertionError('patient name must be a string')
        
    files_of_interest = os.listdir(os.path.join(in_folder, 'acquired'))
    has_deid_name = any([deidentify_name in f for f in files_of_interest])
    if not has_deid_name:
        has_ans = False
        while not has_ans:
            ans = input(f'\nName "{deidentify_name}" not found in acquired folder. Would you like to proceed anyway? [y/n]\n')
            if ans in ('y','n'):
                has_ans = True
                if ans == 'n':
                    raise Exception('Aborting processing')
            else:
                print('Answer must be "y" or "n"')
        
    print(f'\nStep 1: deidentification. {deidentify_name} will be replaced with {replacement}')
        
    # build the call to the deidentify script
    deid_scripts_loc = r'/Users/manusdonahue/Desktop/Projects/SCD/Processing/deidentifySLW/'
    
    strip_filename_input = f'deidentifyFileNames.sh {in_folder} {deidentify_name} {replacement}'
    strip_header_input = f'deidentifyPARfiles.sh {in_folder}'
    
    deid_commands = [os.path.join(deid_scripts_loc, c) for c in (strip_filename_input, strip_header_input)]
    
    for com in deid_commands:
        subprocess.run([com], check=True, shell=True)
        
    print(f'\nDeidentification complete. Elapsed time: {str_time_elapsed(start_stamp)} minutes')

if '2' in steps:    
    ##### step 2 : main processing
    
    print(f'Step 2: begin main processing sequence\n')
    
    
    processing_scripts_loc = r'/Users/manusdonahue/Desktop/Projects/SCD/Processing/Pipeline/'
    os.chdir(processing_scripts_loc)
    processing_input = f'''/Applications/MATLAB_R2016b.app/bin/matlab -nodesktop -nosplash -r "Master_v2('{pt_id}',{hematocrit},{pt_type},{flip})"'''
    
    # print(processing_input)
    
    subprocess.run(processing_input, check=True, shell=True)
    # subprocess.run('quit force', check=True, shell=True)
    
    os.chdir(original_wd)
    
    print(f'\nMain processing complete. Elapsed time: {str_time_elapsed(start_stamp)} minutes')
    
    
print(f'\nProcessing complete. Elapsed time: {str_time_elapsed(start_stamp)} minutes\n')