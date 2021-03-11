#!/usr/bin/env python3

# -*- coding: utf-8 -*-
help_info = """
This script takes raw scan data for SCD scans and processes it completely.
This involves:
    1) deidentifying the scans
    2) running TRUST and generating derived images
    3) pushing the results to REDCap
    4) generate a pdf report
    
Requires T1, ASL and TRUST scans to fully run
    
    
input:
    -i / --infolder : the path to the folder of pt data. of form /Users/manusdonahue/Desktop/Projects/SCD/Data/[PTSTEN_ID]
        this folder should have one subfolder called Acquired which contains the raw scans
    -n / --name : the name of the patient to deidentify. Only required if running step 1
    -s / --steps : the steps to actually calculate, passed as a string of numbers
        if 0, all steps will be carried out. Otherwise, only the steps that appear
        in the string will be carried out. For example, 2 will cause the script
        to only go through step 2. Because there are only steps, multistep specification isn't really needed,
            but you can explicitly specify steps 1 and 2 by passing -s 12
    -h / --hct : the hematocrit as a float between 0 and 1. Required for step 2
        you can also pass redcap as an argument, and the script will look for the hct value in REDCap and use that. default: redcap
    -f / --flip : optional. 1 to invert TRUST, 0 to leave as is (default=0).
        Note that the program will attempt to automatically invert the TRUST
        if needed, so only pass 1 if the results are still wrong
    -p / --pttype : the type of patient. 'sca', 'anemia' or 'control'. Required for step 2
        note that 'sca' and 'anemia' trigger the same processing protocol. default: redcap
        you can also pass redcap as an argument, and the script will look for the pt type value in REDCap and use that
    -e / --exclude: subprocessing steps to exclude. The subprocessing steps are
        TRUST (trust), volumetrics (vol) and ASL (asl). To exclude a step, or steps,
        enter the steps to exclude separated by a comma, e.g., -e vol,trust
    -a / --artox: the arterial oxygen saturation from the pulse oximeter, reported as a number between 0 and 1. Only required if generating the report (step 4)
        Fetch from REDCap by passing redcap. default: redcap
    -y / --auto: if 1, will skip some manual prompts and quality checks. 0 by default. Does not skip critical checks or unusual flags. Intended mostly
        to allow DIPbot to run this program
    -r / --redcap: if 1, will contact REDCap. if 0, will not. 1 by default
        Obviously if you specify 0 for this but also specify things that require a REDCap connection (such as pulling parameters from REDCap
        or pulling parameters from it) this will cause an error. This option is mostly here so data from outside the Donahue lab can
        be procssed
    -b / --dob: date of birth as YYYY.mm.dd. If redcap is contacted, the redcap value takes precedence
    -u / -gender: any string, but typically male or female. If redcap is contacted, the redcap value takes precedence
    -t / --scandate: the date of the scan as YYYY.mm.dd. If redcap is contacted, the redcap value takes precedence
    -x / --studyid: the study ID for the scan (eg., Jordan_1934848). If redcap is contacted, the redcap value takes precedence
    -g / --help : brings up this helpful information. does not take an argument
"""
#     -m / --mrid: the MR ID for the scan (e.g., PTSTEN_180)

import os
import sys
import getopt
import subprocess
import time
import datetime
import glob
import shutil
import requests
import re

import redcap
import pandas as pd
from pylab import title, figure, xlabel, ylabel, xticks, bar, legend, axis, savefig
import matplotlib
from fpdf import FPDF
import numpy as np
import matplotlib.pyplot as plt

from helpers import get_terminal, str_time_elapsed
import helpers as hp
from report_image_generation import par2nii, nii_image, compare_nii_images

#sys.exit()
wizard = """                
                  ....
                                .'' .'''
.                             .'   :
\\                          .:    :
 \\                        _:    :       ..----.._
  \\                    .:::.....:::.. .'         ''.
   \\                 .'  #-. .-######'     #        '.
    \\                 '.##'/ ' ################       :
     \\                  #####################         :
      \\               ..##.-.#### .''''###'.._        :
       \\             :--:########:            '.    .' :
        \\..__...--.. :--:#######.'   '.         '.     :
        :     :  : : '':'-:'':'::        .         '.  .'
        '---'''..: :    ':    '..'''.      '.        :'
           \\  :: : :     '      ''''''.     '.      .:
            \\ ::  : :     '            '.      '      :
             \\::   : :           ....' ..:       '     '.
              \\::  : :    .....####\\ .~~.:.             :
               \\':.:.:.:'#########.===. ~ |.'-.   . '''.. :
                \\    .'  ########## \ \ _.' '. '-.       '''.
                :\\  :     ########   \ \      '.  '-.        :
               :  \\'    '   #### :    \ \      :.    '-.      :
              :  .'\\   :'  :     :     \ \       :      '-.    :
             : .'  .\\  '  :      :     :\ \       :        '.   :
             ::   :  \\'  :.      :     : \ \      :          '. :
             ::. :    \\  : :      :    ;  \ \     :           '.:
              : ':    '\\ :  :     :     :  \:\     :        ..'
                 :    ' \\ :        :     ;  \|      :   .'''
                 '.   '  \\:                         :.''
                  .:..... \\:       :            ..''
                 '._____|'.\\......'''''''.:..'''
                            \\
                                """

inp = sys.argv
bash_input = inp[1:]
options, remainder = getopt.getopt(bash_input, "i:n:s:h:f:p:e:a:y:r:b:u:t:x:g",
                                   ["infolder=", "name=", 'steps=', 'hct=', 'flip=', 'pttype=', 'excl=', 'artox=', 'auto=', 'redcap=',
                                    'dob=', 'gender=', 'scandate=', 'studyid=', 'help'])



flip = 0
asl_tr = 4
auto = 0
contact_redcap = 1

art_ox_sat = 'redcap'
hematocrit = 'redcap'
pt_type_num = 'redcap'
pt_type = 'redcap'

scan_date = None
birth_date = None
gender = None

mrid = None
study_id = None


do_run = {'trust':1,
          'vol':1,
          'asl':1
          }

for opt, arg in options:
    if opt in ('-i', '--infolder'):
        in_folder = arg
    elif opt in ('-n', '--name'):
        deidentify_name = arg
    elif opt in ('-r', '--redcap'):
        contact_redcap = int(arg)
    elif opt in ('-y', '--auto'):
        auto = int(arg)
    elif opt in ('-s', '--steps'):
        steps = arg
    elif opt in ('-h', '--hct'):
        if arg != 'redcap':
            hematocrit = float(arg)
            if hematocrit > 1 or hematocrit < 0:
                raise Exception('Hematocrit must be between 0 and 1')
        else:
            hematocrit = arg
    elif opt in ('-f', '--flip'):
        flip = int(arg)
    elif opt in ('-p', '--pttype'):
        pt_type = arg
        if pt_type == 'control':
            pt_type_num = 0
            the_num = '0'
            descrip = 'non-anemic'
        elif pt_type == 'sca':
            pt_type_num = 1
            the_num = '1'
            descrip = 'SCD'
        elif pt_type == 'anemia':
            pt_type_num = 1
            the_num = '2'
            descrip = 'anemia'
        elif pt_type == 'redcap':
            pt_type_num = pt_type
        else:
            raise Exception('Patient type must be "sca", "control" or "anemia"')
    elif opt in ('-e', '--excl'):
        parsed_excl = arg.split(',')
        for p in parsed_excl:
            if p not in do_run:
                raise ValueError('Input for -e/--excl must contain only the processes to exclude (trust, vol or asl) separated by a comma with no spaces\ne.g., vol,trust')
            do_run[p] = 0
    elif opt in ('-g', '--help'):
        print(help_info)
        sys.exit()
    elif opt in ('-a', '--artox'):
        if arg != 'redcap':
            art_ox_sat = float(arg)
            if art_ox_sat > 1 or art_ox_sat < 0:
                raise Exception('Arterial oxygenation fraction must be between 0 and 1')
        else:
            art_ox_sat = arg

    elif opt in ('-b', '--dob'):
        birth_date = arg
    elif opt in ('-u', '--gender'):
        gender = arg
    elif opt in ('-t', '--scandate'):
        scan_date = arg
    elif opt in ('-x', '--studyid'):
        study_id = arg
    """
    elif opt in ('-m', '--mrid'):
        steps = arg
    """

try:
    if steps == '0':
        steps = '1234'
except NameError:
    print('-s not specified. running all steps')
    steps = '1234'
        
try:
    assert os.path.isdir(in_folder)
except AssertionError:
    raise AssertionError('input folder does not exist')

start_stamp = time.time()
now = datetime.datetime.now()
pretty_now = now.strftime("%Y-%m-%d %H:%M:%S")

inp_copy = inp.copy()
for i, s in enumerate(inp_copy):
    if s == '-n' or s== '--name':
        inp_copy[i+1] = '[REDACTED]'

thecommand = ' '.join(inp_copy)
meta_file_name = os.path.join(in_folder, 'meta.txt')
meta_file = open(meta_file_name, 'w')
meta_file.write(f'Processing started {pretty_now}')
meta_file.write('\n\n')
meta_file.write(thecommand)
meta_file.close()

print(f'\nBegin processing: {pretty_now}')


acq_folder = os.path.join(in_folder, 'Acquired')
orig_files = [os.path.join(acq_folder, f) for f in os.listdir(acq_folder) if os.path.isfile(os.path.join(acq_folder, f))]
extensions = [f.split('.')[-1] for f in orig_files]
guess_ext = hp.most_common(extensions)

orig_data_copy_folder = os.path.join(in_folder, 'rawdata')
    
dcm_exts = ['dcm', 'DCM']
parrec_exts = ['PAR', 'REC', 'V41', 'XML']
nii_exts = ['nii', 'gz']

if guess_ext in parrec_exts:
    print('Input files seem to be PARREC - proceeding as normal')
elif guess_ext in dcm_exts:
    print('Input files seem to be DICOM - converting to PARREC before continuing (original DICOMs will be retained)')
    shutil.copytree(acq_folder, orig_data_copy_folder)
    shutil.rmtree(acq_folder)
    os.mkdir(acq_folder)
    
    moved_files = [os.path.join(orig_data_copy_folder, f) for f in os.listdir(orig_data_copy_folder) if os.path.isfile(os.path.join(orig_data_copy_folder, f))]
    moved_extensions = [f.split('.')[-1] for f in orig_files]
    for fi, ext in zip(moved_files, moved_extensions):
        if ext in dcm_exts:
            #print(f'\n\n\nCONVERTING: {fi}')
            hp.dicom_to_parrec(fi, acq_folder)      
elif guess_ext in nii_exts:
    has_ans = False
    while not has_ans:
        if not auto:
            ans = input(f'Input files seem to be NiFTI. ASL processing of NiFTIs is in an UNSTABLE BETA state.\nRESULTS MUST BE MANUALLY INSPECTED FOR CORRECTNESS.\nAlso note that volumetric calculations may be differ slightly from those obtained from the PARREC pipeline.\nPlease acknowledge this or cancel processing. [acknowledge/cancel]\n')
        else:
            ans = 'acknowledge'
            print(f'Auto response: {ans}')
        if ans in ('acknowledge', 'cancel'):
            has_ans = True
            if ans == 'cancel':
                raise Exception('Aborting processing')
            elif ans == 'acknowledge':
                print('Continuing with beta processing of NiFTIs')
                #raise Exception('SORRY! NiFTI processing not yet fully implemented in the process_scd.py pipeline')
        else:
            print('Answer must be "acknowledge" or "cancel"')
else:
    raise Exception(f'Filetype ({guess_ext}) does not seem to be supported')


original_wd = os.getcwd()
pt_id = replacement = get_terminal(in_folder) # if the input folder is named correctly, it is the ID that will replace the pt name

name_in_redcap = False
if contact_redcap:
    # check the redcap database to make sure the folder name is (pt_id) is in the redcap database
    
    print('\nContacting the REDCap database...')
    
    name_in_redcap = True
    
    try:
        api_url = 'https://redcap.vanderbilt.edu/api/'
        token_loc = '/Users/manusdonahue/Desktop/Projects/redcaptoken_scd_real.txt'
        token = open(token_loc).read()
        
        project = redcap.Project(api_url, token)
        project_data_raw = project.export_records()
        project_data = pd.DataFrame(project_data_raw)
        
        mri_cols = ['mr1_mr_id',
                    'mr2_mr_id',
                    'mr3_mr_id',
                    'mr4_mr_id',
                    'mr5_mr_id',
                    'mr6_mr_id'
                    ]
    
        
        which_scan = [pt_id in list(project_data[i]) for i in mri_cols]
        
        if not any(which_scan):
            has_ans = False
            while not has_ans:
                print(f'The mr_id ({pt_id}) was not found in the REDCap database')
                print("You can still process this data, but you won't be able to push the results to REDCap automatically, and I won't be able to find the patient's hct.")
                ans = input('Is this okay? [y/n]\n')
                if ans in ('y','n'):
                    has_ans = True
                    if ans == 'n':
                        raise Exception('Aborting processing')
                    elif ans == 'y':
                        print(f'Continuing with processing. Remember to fix the discrepancy between the local and REDCap mr_id values.')
                        if 'redcap' in [hematocrit, pt_type_num]:
                            raise Exception('Cannot use pull hct or pt type from REDCap without a database connection')
                        time.sleep(3)
                        name_in_redcap = False
                else:
                    print('Answer must be "y" or "n"')
        else:
            if sum(which_scan) > 1:
                raise Exception(f'The patient id ({pt_id}) appears in more than one mr_id column in the REDCap database\n{[(i,j) for i,j in zip(mri_cols, which_scan)]}\nPlease correct the database')
            
            has_ans = False
            while not has_ans:
                print(f"MR ID {pt_id} appears to correspond to MR scan column {which_scan.index(True)+1} for this patient.")
                print(f'(the mr_id was found in column {mri_cols[which_scan.index(True)]})')
                if not auto:
                    ans = input(f'Please confirm that this is correct, especially if you intend to push processing results to REDCap or are using the database values for hct/pt type. [y/n]\n')
                else:
                    ans = 'y'
                    print(f'Auto response: {ans}')
                if ans in ('y','n'):
                    has_ans = True
                    if ans == 'n':
                        raise Exception('Aborting processing')
                    elif ans == 'y':
                        scan_index = which_scan.index(True)
                        scan_mr_col = mri_cols[scan_index]
                        studyid_index_data = project_data.set_index('study_id')
                        
                        inds = studyid_index_data[scan_mr_col] == pt_id
                        cands = studyid_index_data[inds]
                        
                        if len(cands) != 1:
                            raise Exception(f'There are {len(cands)} mr_id candidates in the database. There must be exactly one')
                        
                        study_id = cands.index[0]
                        
                        try:
                            if hematocrit == 'redcap':
                                try:
                                    hematocrit = float(cands.iloc[0][f'blood_draw_hct{scan_index+1}'])/100
                                except ValueError:
                                    raise Exception(f'There is no hct value in blood_draw_hct{scan_index+1} in REDCap')
                                print(f'The study hematocrit I found is {hematocrit}')
                        except NameError:
                            pass
                          
                        try:
                            if pt_type_num == 'redcap':
                                the_num = cands.iloc[0]['case_control']
                                if the_num == '0':
                                    pt_type_num = 0
                                    descrip = 'non-anemic'
                                elif the_num == '1':
                                    pt_type_num = 1
                                    descrip = 'SCD'
                                elif the_num == '2':
                                    pt_type_num = 1
                                    descrip = 'anemia'
                                print(f'The patient type I found is {the_num} ({descrip})')
                            print(f'The study id is {study_id}')
                        except NameError:
                            pass
                        
                        try:
                            if art_ox_sat == 'redcap':
                                try:
                                    art_ox_sat = float(cands.iloc[0][f'mr{scan_index+1}_pulse_ox_result'])/100
                                except ValueError:
                                    raise Exception(f'There is no pulse ox (arterial ox sat) value in mr{scan_index+1}_pulse_ox_result in REDCap')
                                print(f'The study pulse ox (arterial ox sat) I found is {art_ox_sat}')
                        except NameError:
                            pass
                        
                        time.sleep(3)
                        
                else:
                    print('Answer must be "y" or "n"')
    except requests.exceptions.RequestException:
        print(f"Could not make contact with the REDCap database. You won't be able to push data to REDCap automatically")
        print("This is usually due to lack of internet connection or REDCap being down")
        name_in_redcap = False
        time.sleep(3)

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
            ans = input(f'\nName "{deidentify_name}" not found in acquired folder. Would you like to proceed anyway? [y/n/change]\n')
            if ans in ('y','n', 'change'):
                has_ans = True
                if ans == 'n':
                    raise Exception('Aborting processing')
                elif ans == 'change':
                    deidentify_name = input(f'Enter a new deidentification string to replace {deidentify_name}:\n')
            else:
                print('Answer must be "y", "n" or "change')
        
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
    
    acquired_folder = os.path.join(in_folder, 'Acquired')
    
    
    globber_pld = os.path.join(acquired_folder,'*_PLD*')
    globber_ld = os.path.join(acquired_folder,'*_LD*')
    
    names_with_pld = glob.glob(globber_pld)
    names_with_ld = glob.glob(globber_ld)
    

    if len(names_with_pld) == 0 or len(names_with_ld) == 0:
        print('No PLD/LD signature detected, implying a lack of ASL data. If you intend to run ASL processing this will be an issue.')

        has_ans = False
        while not has_ans:
            if not auto:
                ans = input(f'\nWould you like to proceed anyway? [y/n]\n')
            else:
                ans = 'y'
                print(f'Auto response: {ans}')
            if ans in ('y','n'):
                has_ans = True
                if ans == 'n':
                    raise Exception('Aborting processing')
                else:
                    print('Continuing. TR, PLD and PL will be set to 0 but can be manually adjusted.')
            else:
                print('Answer must be "y" or "n"')
                
        pld_name = 'NOT FOUND'
        candidate_line = 'NOT FOUND'
        tr = pld = ld = 0
        
    else:
        pld_name = names_with_pld[0]
        ld_name = names_with_ld[0]
        
        if pld_name != ld_name:
            raise Exception(f'\n{pld_name} != {ld_name}\nPLD and LD parameters not found in same file. Please configure filenames so PLD and LD are specified in the pCASL source file')
            
        if 'PAR' in pld_name or 'REC' in pld_name:
            pcasl_meta = open(pld_name)
            pcasl_lines = pcasl_meta.read().split('\n')
            candidate_lines = [i for i in pcasl_lines if 'Repetition time' in i]
            candidate_line = candidate_lines[0]
            candidate_broken = candidate_line.split(' ')
        
            tr = None
            for c in candidate_broken:
                try:
                    tr = float(c) / 1000 # value is given in ms, need s
                    break
                except ValueError:
                    pass
        else:
            tr = 4
            candidate_line = 'There is no candidate line for tr for non-PARREC files'
            print("Just so you know, I can't extract the repetition time (tr) from non-PARREC files")
            print("tr is generally 4 seconds, so I've set it for you. You can still change it though.")
        
        pld_split = pld_name.split('_')
        ld_split = ld_name.split('_')
        
        
        plds = [i for i in pld_split if 'PLD' in i]
        lds = [i for i in ld_split if ('LD' in i and 'PLD' not in i)]
        
        pld = plds[0][3:]
        ld = lds[0][2:]
        
    has_ans = False
    while not has_ans:
        print(f'\nFound asl_pld: {pld}\nFound asl_ld: {ld}\nFound asl_tr: {tr}\nIs this okay? (y/n/show)\n')
        if not auto:
            ans = input()
        else:
            ans = 'y'
            print(f'Auto response: {ans}')
        if ans == 'y':
            has_ans = True
            asl_pld = pld
            asl_ld = ld
            asl_tr = tr
        elif ans == 'n':
            asl_pld_hold = input('What should asl_pld be?\n')
            asl_ld_hold = input('What should asl_ld be?\n')
            asl_tr_hold = input('What should asl_tr be (in seconds)?\n')
            
            try:
                asl_pld = int(asl_pld_hold)
                asl_ld = int(asl_ld_hold)
                asl_tr = float(asl_tr_hold)
                has_ans = True
            except ValueError:
                print('ERROR: you must enter integer values for both asl_pld and asl_ld, and an int or float for asl_tr')
        elif ans == 'show':
            print(f'\nFile with PLD/LD specification: {pld_name}')
            print(f'TR line: {candidate_line}')
        else:
            print('Answer must be y, n or show')
            
    
    if None in [asl_tr, asl_pld, asl_ld]:
        raise Exception('TR, PLD and LD all must be defined (cannot be None)')
        
        
    if do_run['trust']:
        # if we're running trust, make sure the trust source image has TRUST_VEIN in the filename.
        # otherwise the MATLAB script will break
        
        globber_trustsource = os.path.join(acquired_folder,'*SOURCE*TRUST*')
        names_with_trustsource = glob.glob(globber_trustsource)
        
        try:
            trustsource = names_with_trustsource[0]
        except IndexError:
            raise Exception('\nIt appears you do not have a source file for TRUST (pattern: *SOURCE*TRUST*)\nEither add this file to the folder, or exclude TRUST processing')
        
        tv = 'TRUST_VEIN'
        if tv in trustsource:
            print(f'\nTRUST source\n----- {trustsource} -----\nis formatted correctly')
        else:
            print(f'\nWARNING: TRUST source\n----- {trustsource} -----\nis NOT formatted correctly')
            has_ans = False
            while not has_ans:
                if not auto:
                    ans = input(f'\nI can try to fix the filenames for you, or you can exit processing and do it yourself. [fix/exit/info]\n')
                else:
                    ans = 'fix'
                    print(f'Auto response: {ans}')
                if ans in ('fix','exit','info'):
                    if ans == 'exit':
                        has_ans = True
                        raise Exception('Aborting processing')
                    elif ans == 'fix':
                        print('Okay. Renaming the files for you.')
                        
                        base = os.path.basename(trustsource)
                        base = base.split('.')[0]
                        globber_base = os.path.join(acquired_folder,f'{base}.*')
                        names_with_base = glob.glob(globber_base)
                        
                        for path in names_with_base:
                            
                            path_break = path.split('TRUST')
                            new_path = 'TRUST_VEIN'.join(path_break)
                            
                            print(f'\n{path}\nto\n{new_path}\n')
                            os.rename(path, new_path)
                        
                        for line in wizard.splitlines():
                            print(line)
                            time.sleep(0.05)
                        print('magically fixed, free of charge\n')
                        time.sleep(0.5)
                        has_ans = True
                    else:
                        print(f'The TRUST source file must contain TRUST_VEIN somewhere in the filename')
                        print(f'If you select "fix" the TRUST source file(s) will be modified to conform to this by adding _VEIN after wherever TRUST appears')
                        
                else:
                    print('Answer must be "fix", "exit" or "info"')
    
    
    processing_scripts_loc = r'/Users/manusdonahue/Desktop/Projects/SCD/Processing/Pipeline/'
    os.chdir(processing_scripts_loc)
    
    if '4' in steps and do_run['trust']:
        assert art_ox_sat != 'redcap'
        
    if do_run['trust']:
        assert hematocrit != 'redcap'
    elif hematocrit == 'redcap':
        hematocrit = 0 #fine to pass junk in for hct if not running TRUST
        
    assert pt_type_num != 'redcap'
    
    processing_input = f'''/Applications/MATLAB_R2016b.app/bin/matlab -nodesktop -nosplash -r "Master_v2('{pt_id}',{hematocrit},{pt_type_num},{flip},{asl_tr},{asl_pld},{asl_ld},{do_run['trust']},{do_run['vol']},{do_run['asl']},{auto})"'''
    
    print(f'Call to MATLAB: {processing_input}')
    
    subprocess.run(processing_input, check=True, shell=True)
    # subprocess.run('quit force', check=True, shell=True)
    
    os.chdir(original_wd)
    
    print(f'\nMain processing complete. Elapsed time: {str_time_elapsed(start_stamp)} minutes')
    
if '3' in steps and name_in_redcap:    
    ##### step 3 : main processing
    print(f'\nStep 3: pushing results to REDCap\n')
    
    fields_of_interest_raw = [
                            'mrINDEX_lparietal_gm_cbf',
                            'mrINDEX_rparietal_gm_cbf',
                            'mrINDEX_lfrontal_gm_cbf',
                            'mrINDEX_rfrontal_gm_cbf',
                            'mrINDEX_loccipital_gm_cbf',
                            'mrINDEX_roccipital_gm_cbf',
                            'mrINDEX_ltemporal_gm_cbf',
                            'mrINDEX_rtemporal_gm_cbf',
                            'mrINDEX_lcerebellum_gm_cbf',
                            'mrINDEX_rcerebellum_gm_cbf',
                            'mrINDEX_recalc_gm_cbf',
                            'mrINDEX_recalc_wm_cbf',
                            'mrINDEX_white_cbv',
                            'mrINDEX_grey_cbv',
                            'mrINDEX_csf_cbv',
                            'mrINDEX_relaxation_rate1',
                            'mrINDEX_relaxation_rate2',
                            'mrINDEX_venous_oxygen_sat1', #bovine
                            'mrINDEX_venous_oxygen_sat2', #bovine
                            'mrINDEX_aa_model_venous_oxygen_sat1',
                            'mrINDEX_aa_model_venous_oxygen_sat2',
                            'mrINDEX_ss_model_venous_oxygen_sat1',
                            'mrINDEX_ss_model_venous_oxygen_sat2',
                            'mrINDEX_f_model_venous_oxygen_sat1',
                            'mrINDEX_f_model_venous_oxygen_sat2'
                         ]
    
    fields_of_interest = [i.replace('INDEX', str(scan_index+1)) for i in fields_of_interest_raw]
    processed_csv = os.path.join(in_folder, f'{pt_id}_PROCESSINGresults.csv')
    
    data_row = studyid_index_data.loc[study_id]
    old_data = {i:data_row[i] for i in fields_of_interest}
    new_data = hp.parse_scd_csv(processed_csv, scan_index)
    
    print(f'\nThe following changes will be made to study ID {study_id} ({scan_mr_col}):')
    for key in old_data:
        time.sleep(0.1)
        oldy = old_data[key]
        if oldy == '':
            oldy = 'NOTHING'
        newy = new_data[key]
        print(f'\t{key} : {oldy} ---> {newy}')
        
    has_ans = False
    while not has_ans:
        ans = input(f'\nPush to database? Note that a nan will not overwrite the database entry. This behavior may or may not be desired. [y/n/wipe (DO NOT USE WIPE)]\n')
        if ans in ('y','n','wipe'):
            has_ans = True
            if ans == 'n':
                print('Data will not be pushed')
            elif ans == 'y':
                print('Pushing to database - this takes about a minute')
                
                project = redcap.Project(api_url, token) # we need to pull a fresh copy of the database in case someone else had been modifying it during processing
                project_data_raw = project.export_records()
                project_data = pd.DataFrame(project_data_raw)
                studyid_index_data = project_data.set_index('study_id')
                
                for key, val in new_data.items():
                    studyid_index_data.loc[study_id][key] = val
                np_out = project.import_records(studyid_index_data)
                print(f'REDCap data import message: {np_out}')
                    
                print(f'\nData import complete. Elapsed time: {str_time_elapsed(start_stamp)} minutes')
            elif ans =='wipe':
                print('BRO I SAID DO NOT')
                sys.exit()
                print('Wiping REDCap entries for this scan - this takes about a minute')
                project = redcap.Project(api_url, token) # we need to pull a fresh copy of the database in case someone else had been modifying it during processing
                project_data_raw = project.export_records()
                project_data = pd.DataFrame(project_data_raw)
                studyid_index_data = project_data.set_index('study_id')
                
                for key, val in new_data.items():
                    studyid_index_data.loc[study_id][key] = ''
                np_out = project.import_records(studyid_index_data)
                print(f'REDCap data import message: {np_out}')
        else:
            print('Answer must be "y", "n" or "wipe" (which will clear the displayed fields for this scan)')
    
elif '3' in steps and not name_in_redcap:
    print(f"\nSkipping Step 3: can't push to REDCap as either the mr_id is not in the database or the database could not be contacted")
    
    
if '4' in steps:
    
    print('\nStep 4: Generating PDF report\n')
    
    if hematocrit == 'redcap':
        hematocrit = None
    
    
    now = datetime.datetime.now()
    nowstr = now.strftime("%Y-%m-%d %H:%M")
    
    reporting_folder = os.path.join(in_folder, 'reporting')
    
    if os.path.exists(reporting_folder):
        shutil.rmtree(reporting_folder)
    
    os.mkdir(reporting_folder)
    
    print('Pulling data from CSV')
    
    processed_csv = os.path.join(in_folder, f'{pt_id}_PROCESSINGresults.csv')
    raw = open(processed_csv).readlines()
    the_ln = raw[1].split(', ')
    
    non_decimal = re.compile(r'[^\d.]+')
    
    filtered = [non_decimal.sub('', a) for a in the_ln]
    #non_decimal.sub(the_ln, '12.34fe4e')
    
    #filtered = ["".join(filter(str.isdigit, a)) for a in the_ln]
    
    pld = filtered[1]
    ld = filtered[2]
    tr = filtered[3]
    
    
    new_data = hp.parse_scd_csv(processed_csv, -1)
    new_data = {key:float(val) for key,val in new_data.items()}
    
    new_data_std = hp.parse_scd_csv(processed_csv, -1, std=True)
    new_data_std = {key:float(val) for key,val in new_data_std.items()}
    
    mean_R2 = (new_data['mr0_relaxation_rate1'] + new_data['mr0_relaxation_rate2']) / 2
    mean_T2 = (1/new_data['mr0_relaxation_rate1'] + 1/new_data['mr0_relaxation_rate2']) / 2
    Ya = art_ox_sat
    
    bovine_Yv = (new_data['mr0_venous_oxygen_sat1'] + new_data['mr0_venous_oxygen_sat2']) / 2 / 100
    aa_Yv = (new_data['mr0_aa_model_venous_oxygen_sat1'] + new_data['mr0_aa_model_venous_oxygen_sat2']) / 2 / 100
    ss_Yv = (new_data['mr0_ss_model_venous_oxygen_sat1'] + new_data['mr0_ss_model_venous_oxygen_sat2']) / 2 / 100
    f_Yv = (new_data['mr0_f_model_venous_oxygen_sat1'] + new_data['mr0_f_model_venous_oxygen_sat2']) / 2 / 100
    
    df_ox = pd.DataFrame()
    df_ox['Model'] = ['Hb-Bovine', 'Hb-AA', 'Hb-SS', 'Hb-F']
    df_ox['Yv'] = [bovine_Yv, aa_Yv, ss_Yv, f_Yv]
    
    if do_run['trust']:
        df_ox['OEF'] = [(Ya-Yv)/Ya for Yv in df_ox['Yv']]
    else:
        df_ox['OEF'] = [np.nan for Yv in df_ox['Yv']]
    
    
    
    
    
    
    print('Assembling PDF')
    pdf = FPDF()
    ##### TITLE PAGE
    pdf.add_page()
    pdf.set_xy(0, 0)
    pdf.set_font('arial', 'B', 16)
    
    donahue_logo = '/Users/manusdonahue/Documents/Sky/repositories/scan-reporting/bin/Donahue_Lab_v1.png'
    #donahue_logo = '/Users/manusdonahue/Documents/Sky/repositories/scan-reporting/bin/Donahue_Lab_v1_vec.svg'
    vumc_logo = '/Users/manusdonahue/Documents/Sky/repositories/scan-reporting/bin/vumc_logo_clear.png'
    
    
    pdf.cell(210, 5, f"", 0, 2, 'C')
    pdf.cell(210, 10, f"Scan report", 0, 2, 'C')
    pdf.set_font('arial', 'B', 14)
    
    if do_run['asl'] and do_run['vol']:
        header_text = 'Arterial Spin Labeling (ASL)'    
    if do_run['trust']:
        header_text = 'T2-Relaxation-Under-Spin-Tagging (TRUST)'    
    if do_run['asl'] and do_run['vol'] and do_run['trust']:
        header_text = 'T2-Relaxation-Under-Spin-Tagging (TRUST) and Arterial Spin Labeling (ASL)'
    
    pdf.cell(210, 8, header_text, 0, 2, 'C')    
    pdf.set_font('arial', '', 7)
    pdf.cell(210, 6, f"Contact Dr. Manus Donahue (m.donahue@vumc.org) or Sky Jones (sky.jones@vumc.org) for questions regarding the generation of this report", 0, 2, 'C') 
    pdf.ln()
    pdf.ln()
    #pdf.image(vd_logo, x = None, y = None, w = 205, h = 0, type = '', link = '')
    
    pdf.image(vumc_logo, x = None, y = None, w = 191, h = 0, type = '', link = '')
    
    pdf.ln()
    pdf.ln()
    
    pdf.cell(20, 5, f"", 0, 0, 'C')
    pdf.image(donahue_logo, x = None, y = None, w = 151, h = 0, type = '', link = '')
    
    pdf.ln()
    pdf.ln()
    
    
    pdf.cell(-10, 0, '', 0, 0, 'C')
    
    if contact_redcap:
        study_id = cands.iloc[0][f'mr{scan_index+1}_scan_id']
        scan_date = cands.iloc[0][f'mr{scan_index+1}_dt']
        gender = cands.iloc[0][f'gender']
        birth_date = cands.iloc[0][f'dob']
        
    if gender == '1':
        gender_str = 'male'
    elif gender == '0':
        gender_str = 'female'
    else:
        gender_str = gender
        
    if contact_redcap:
        format_str_scan = '%Y-%m-%d %H:%M'
        format_str_birth = '%Y-%m-%d'
    else:
        format_str_scan = '%Y.%m.%d'
        format_str_birth = '%Y.%m.%d'
    
    try:
        scan_dt_obj = datetime.datetime.strptime(scan_date, format_str_scan)
        scan_date_printer = scan_dt_obj.strftime('%Y-%m-%d')
    except TypeError:
        scan_date_printer = None
    try:
        dob_dt_obj = datetime.datetime.strptime(birth_date, format_str_birth)
    except TypeError:
        pass
    
    try:
        pt_age = scan_dt_obj - dob_dt_obj
        pt_age = round(pt_age.days/365.25, 1)
    except NameError:
        pt_age = None
    
    
   
    
    # note that the_num indicates disease state
    pdf.set_fill_color(130, 161, 255)
    
    ctrl_bold = scd_bold = anem_bold = ''
    ctrl_fill = scd_fill = anem_fill = False
    

    if the_num == '0':
        ctrl_bold = 'B'
        ctrl_fill = True
    elif the_num == '1':
        scd_bold = 'B'
        scd_fill = True
    if the_num == '2':
        anem_bold = 'B'
        anem_fill = True
        
    pdf.set_font('arial', 'B', 24)
    pdf.cell(210/8, 10, f"", 0, 0, 'C') 
        
    use_pt_id = pt_id
    bot_append = 'PROCESSING_BOT_'
    use_pt_id = use_pt_id.replace(bot_append,'')
    
    pdf.set_font('arial', ctrl_bold, 22)
    pdf.cell(210/4, 10, f"Non-anemic", 1, 0, 'C', fill=ctrl_fill)        
    pdf.set_font('arial', scd_bold, 22)
    pdf.cell(210/4, 10, f"SCD", 1, 0, 'C', fill=scd_fill)        
    pdf.set_font('arial', anem_bold, 22)
    pdf.cell(210/4, 10, f"Anemia", 1, 0, 'C', fill=anem_fill)   
    
    pdf.cell(210/8, 10, f"", 0, 2, 'C')  
    
    pdf.cell(-(210/8)*7, 10, f"", 0, 0, 'C')
    
    pdf.set_font('arial', 'B', 20)
    pdf.cell(210, 8, f"", 0, 2, 'C')
    pdf.cell(210, 8, f"MR ID: {use_pt_id}", 0, 2, 'C')
    pdf.cell(210, 8, f"Study ID: {study_id}", 0, 2, 'C')
    #pdf.cell(210, 10, f"Status: {descrip}", 0, 2, 'C')
    pdf.cell(210, 5, f"", 0, 2, 'C')
    pdf.cell(210, 8, f"Age at scan: {pt_age}", 0, 2, 'C')
    pdf.cell(210, 8, f"Gender: {gender_str}", 0, 2, 'C')
    pdf.cell(210, 8, f"Hematocrit: {hematocrit}", 0, 2, 'C')
    pdf.cell(210, 5, f"", 0, 2, 'C')
    pdf.cell(210, 8, f"Acquisition date: {scan_date_printer}", 0, 2, 'C')
    pdf.cell(210, 8, f"Report generated: {nowstr}", 0, 2, 'C')
    pdf.cell(210, 8, f"", 0, 2, 'C')
    
    
    pdf.set_font('arial', 'B', 10)
    
    trust_adder = asl_adder = ' (not run)'
    asl_res = trust_res = asl_specs = trust_echoes = '---'
    if do_run['trust']:
        trust_adder = ''
        trust_res = 'Spatial resolution: 2.875 x 2.875 x 5.0mm'
        trust_echoes = 'Echo time range: [0, 40, 80, 160] ms'
    if do_run['vol'] and do_run['asl']:
        asl_adder = ''
        asl_res = 'Spatial resolution: 3.0 x 3.0 x 8.0mm'
        asl_specs = f'PLD, LD, TR: {pld}ms, {ld}ms, {tr}s'
    
    
    pdf.cell(210/2, 6, f"TRUST Parameters{trust_adder}", 0, 0, 'C')
    pdf.cell(210/2, 6, f"ASL Parameters{asl_adder}", 0, 2, 'C')
    pdf.cell(-(210/2), 6, f"", 0, 0, 'C')
    
    
    pdf.set_font('arial', '', 8)
    pdf.set_text_color(133, 133, 133)
    pdf.cell(210/2, 4, f"{trust_res}", 0, 0, 'C')
    pdf.cell(210/2, 4, f"{asl_res}", 0, 2, 'C')
    pdf.cell(-(210/2), 4, f"", 0, 0, 'C')
    
    pdf.cell(210/2, 4, f"{trust_echoes}", 0, 0, 'C')
    pdf.cell(210/2, 4, f"{asl_specs}", 0, 2, 'C') 
    
    pdf.cell(210/2, 4, f"", 0, 0, 'C')
    pdf.cell(210/2, 4, f"Labeling type: pCASL", 0, 2, 'C')
    pdf.cell(-(210), 4, f"", 0, 0, 'C')
    
    #pdf.cell(0, 55, f"", 0, 2, 'C')

    
    
    pdf.set_text_color(133, 133, 133)
    pdf.set_text_color(0, 0, 0)
    
    if do_run['trust']:
    
        print('Generating decay plot')
        
        decay_csv = os.path.join(in_folder, f'decay_params.csv')
        decay_df = pd.read_csv(decay_csv, header=None)
        
        trust_ete = decay_df.iloc[0]
        
        trust_meansagsinus = decay_df.iloc[1]
        
        trust_meansagsinus_MAX = decay_df.iloc[2]
        trust_meansagsinus_MIN = decay_df.iloc[3]
        
        trust_meansagsinus_one = decay_df.iloc[4][0]
        trust_meanT2 = decay_df.iloc[4][1]
        trust_meanT2_max = decay_df.iloc[4][3]
        trust_meanT2_min = decay_df.iloc[4][2]
        
        #decay_ci_csv = os.path.join(in_folder, f'fit_ci_params.csv')
        #decay_ci_df= pd.read_csv(decay_ci_csv, header=None)
        
        
        exes = np.arange(min(trust_ete),max(trust_ete),0.01)
        exp_whys = trust_meansagsinus_one*np.exp(-(exes/1000)/trust_meanT2)
        
        exp_upper = trust_meansagsinus_MAX[0]*np.exp(-(exes/1000)/trust_meanT2_min)
        exp_lower = trust_meansagsinus_MIN[0]*np.exp(-(exes/1000)/trust_meanT2_max)
        
    
        fig, ax = plt.subplots(1, 1, figsize=(5, 5))
        decay_plot_path = os.path.join(reporting_folder, f'decay_plot.png')
        
        ax.plot(exes, exp_whys, color='black') # fit
        ax.plot(exes, exp_upper, color='gray', linestyle='dashed') # upper 95
        ax.plot(exes, exp_lower, color='gray', linestyle='dashed')# lower 95
        
        error_mins = trust_meansagsinus - trust_meansagsinus_MIN
        error_maxes = trust_meansagsinus_MAX - trust_meansagsinus
        error_bar_vals = np.array([error_mins, error_maxes])
        ax.errorbar(trust_ete, trust_meansagsinus, yerr=error_bar_vals, fmt='ow', mec='black', ms=5, mew=1, ecolor='red', capsize=2)
        
        ax.set_title('TRUST fit')
        ax.set_xlabel('Effective echo time (ms)')
        ax.set_ylabel('Signal (a.u.)')
        
        plt.tight_layout()
        plt.savefig(decay_plot_path, dpi=200)
        
        ##### TRUST PAGE
        pdf.add_page()
        pdf.set_xy(0, 0)
        pdf.set_font('arial', 'B', 12)    
        pdf.set_text_color(133, 133, 133)
        
        pdf.cell(10)
        pdf.cell(75, 5, f"", 0, 2, 'L')
        pdf.cell(75, 5, f"MR ID: {use_pt_id}", 0, 2, 'L')
        pdf.cell(75, 5, f"Status: {descrip}", 0, 2, 'L')
        pdf.cell(75, 5, f"Acquisition date: {scan_date_printer}", 0, 2, 'L')
        pdf.cell(75, 5, f"TRUST metrics", 0, 2, 'L')
        pdf.cell(-10)
        pdf.set_text_color(0, 0, 0)
        
        pdf.cell(60)
        pdf.cell(90, 10, " ", 0, 2, 'C')
        pdf.cell(-50)
        pdf.set_font('arial', 'I', 12)
        pdf.cell(50, 10, 'Mean T2 (s)', 1, 0, 'C')
        pdf.set_font('arial', '', 12)
        pdf.cell(50, 10, f'{round(mean_T2,3)}', 1, 2, 'C')
        pdf.cell(-50)
        pdf.set_font('arial', 'I', 12)
        pdf.cell(50, 10, 'Mean R2 (1/s)', 1, 0, 'C')
        pdf.set_font('arial', '', 12)
        pdf.cell(50, 10, f'{np.round(mean_R2,decimals=2)}', 1, 2, 'C')
        
        pdf.cell(0, 5, '', 0, 1, 'C')
        
        pdf.set_font('arial', 'I', 12)
        pdf.set_fill_color(255, 172, 166)
        pdf.cell(170*Ya, 10, '', 0, 0, 'C', fill=True)
        pdf.cell(-170*Ya, 10, '', 0, 0, 'C', fill=True)
        pdf.cell(170, 10, f'Oxygenation modeling: arterial O2 saturation (Ya) = {round(Ya,2)}', 1, 2, 'C')
        #pdf.cell(-100)
        pdf.cell(50, 10, 'Model', 1, 0, 'C')
        pdf.cell(60, 10, 'Venous O2 saturation (Yv)', 1, 0, 'C')
        pdf.cell(60, 10, 'O2 extraction fraction (OEF)', 1, 2, 'C')
        pdf.cell(-110)
        pdf.set_font('arial', '', 12)
        for i in range(0, len(df_ox)):
            
            Yv = df_ox['Yv'].iloc[i]
            oef = df_ox['OEF'].iloc[i]
            
            pdf.cell(50, 10, '%s' % (df_ox['Model'].iloc[i]), 1, 0, 'C')
            
            pdf.set_fill_color(218, 212, 255)
            pdf.cell(60*Yv, 10, ' ', 0, 0, 'L', fill=True)
            pdf.cell(-60*Yv, 10, ' ', 0, 0, 'L', fill=False)
            pdf.cell(60, 10, '%s' % (str(round(Yv,3))), 1, 0, 'C')
            
            pdf.set_fill_color(255, 240, 184)
            pdf.cell(60*oef, 10, ' ', 0, 0, 'L', fill=True)
            pdf.cell(-60*oef, 10, ' ', 0, 0, 'L', fill=False)
            pdf.cell(60, 10, '%s' % (str(round(oef,3))), 1, 2, 'C')
            
            pdf.cell(-110)
            
        pdf.cell(0, 5, '', 0, 2, 'C')
        pdf.cell(15)
        pdf.image(decay_plot_path, x = None, y = None, w = 140, h = 0, type = '', link = '')
    
    if do_run['asl'] and do_run['vol']:
        print('Generating and processing CBF images')
    
        mni_folder = os.path.join(in_folder, 'Processed', 'CBF2mm')
        cbf_nii = os.path.join(mni_folder, f'{pt_id}_CBF_MNI_2mm.nii.gz')
        t1_nii = os.path.join(in_folder, 'Processed', f'{pt_id}_3D_MNI_nonBET.nii.gz')
        
        cbf_im = os.path.join(reporting_folder, 'cbf.png')
        
        #nii_image(cbf_nii, (3,3), cbf_im, cmap=matplotlib.cm.inferno, cmax=100, save=True, specified_frames=list(np.arange(12,72,7)), ax_font_size=16)
        compare_nii_images(niis=[t1_nii, cbf_nii], cmaxes=[None,100], out_name=cbf_im, save=True, frames=list(np.arange(17,77,10)))
        ##### CBF PAGE
        pdf.add_page()
        pdf.set_xy(0, 0)
        pdf.set_font('arial', 'B', 12)      
        pdf.set_text_color(133, 133, 133)
        pdf.cell(10)
        pdf.cell(75, 5, f"", 0, 2, 'L')
        pdf.cell(75, 5, f"MR ID: {use_pt_id}", 0, 2, 'L')
        pdf.cell(75, 5, f"Status: {descrip}", 0, 2, 'L')
        pdf.cell(75, 5, f"Acquisition date: {scan_date_printer}", 0, 2, 'L')
        pdf.cell(75, 5, f"ASL metrics", 0, 2, 'L')    
        pdf.cell(-10)
        pdf.set_text_color(0, 0, 0)
            
        pdf.cell(60)
        pdf.cell(90, 5, " ", 0, 2, 'C')
        pdf.cell(-20)
        pdf.image(cbf_im, x = None, y = None, w = 130, h = 0, type = '', link = '')
        pdf.set_font('arial', 'I', 12)
        #pdf.cell(160, 10, 'Cerebral blood flow (ml/100g/min)', 0, 0, 'C')
        
        
        pdf.cell(0, 5, '', 0, 1, 'C')
        
        
        lobe_names = []
        lobe_vals = []
        lobe_stds = []
        i = 0
        for key,val in new_data.items():
            i += 1
            name = ''
            split = key.split('_')
            if split[1][0] == 'l':
                name = name+'Left'
            elif split[1][0] == 'r':
                name = name+'Right'
                
            name = name+' '+split[1][1:]
            name = name+' '+split[2].upper()
            
            lobe_names.append(name)
            lobe_vals.append(val)
            lobe_stds.append(new_data_std[key])
            
            if i > 9:
                break
        
    
        table_height = 6
        pdf.cell(10)
        pdf.cell(50, table_height, 'Lobe', 1, 0, 'C')
        pdf.cell(60, table_height, 'CBF (ml/100g/min)', 1, 0, 'C')
        pdf.cell(60, table_height, 'Standard deviation', 1, 2, 'C')
        pdf.cell(-110)
        pdf.set_font('arial', '', 12)
        for i, (name,val,std) in enumerate(zip(lobe_names, lobe_vals, lobe_stds)):
            
            pdf.cell(50, table_height, '%s' % (name), 1, 0, 'C')
            
            gofrac = val / max(lobe_vals)
            gofrac_std = std / max(lobe_stds)
            
            pdf.set_fill_color(184, 255, 208)
            pdf.cell(60*gofrac, table_height, ' ', 0, 0, 'L', fill=True)
            pdf.cell(-60*gofrac, table_height, ' ', 0, 0, 'L', fill=False)
            pdf.cell(60, table_height, '%s' % (str(round(val,1))), 1, 0, 'C')
            
            
            pdf.set_fill_color(255, 206, 133)
            pdf.cell(60*gofrac_std, table_height, ' ', 0, 0, 'L', fill=True)
            pdf.cell(-60*gofrac_std, table_height, ' ', 0, 0, 'L', fill=False)
            pdf.cell(60, table_height, '%s' % (str(round(std,1))), 1, 2, 'C')
            
            pdf.cell(-110)
    
    
    print('Writing PDF')
    
    pdf_out = os.path.join(reporting_folder, f'{use_pt_id}_report.pdf')
    pdf.output(pdf_out, 'F')
    
    
    

    
    
print(f'\nProcessing complete. Elapsed time: {str_time_elapsed(start_stamp)} minutes\n')





