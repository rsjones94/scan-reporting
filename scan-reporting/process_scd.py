#!/usr/bin/env python3

# -*- coding: utf-8 -*-
help_info = """
This script takes raw scan data for SCD scans and processes it completely.
This involves:
    1) deidentifying the scans
    2) running TRUST and generating derived images
    3) pushing the results to REDCap
    
    
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
        you can also pass redcap as an argument, and the script will look for the hct value in REDCap and use that
    -f / --flip : optional. 1 to invert TRUST, 0 to leave as is (default=0).
        Note that the program will attempt to automatically invert the TRUST
        if needed, so only pass 1 if the results are still wrong
    -p / --pttype : the type of patient. 'sca', 'anemia' or 'control'. Required for step 2
        note that 'sca' and 'anemia' trigger the same processing protocol
        you can also pass redcap as an argument, and the script will look for the pt type value in REDCap and use that
    -e / --exclude: subprocessing steps to exclude. The subprocessing steps are
    TRUST (trust), volumetrics (vol) and ASL (asl). To exclude a step, or steps,
    enter the steps to exclude separated by a comma, e.g., -e vol,trust
    -g / --help : brings up this helpful information. does not take an argument
"""

import os
import sys
import getopt
import subprocess
import time
import datetime
import glob
import shutil
import requests

import redcap
import pandas as pd

from helpers import get_terminal, str_time_elapsed
import helpers as hp

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
options, remainder = getopt.getopt(bash_input, "i:n:s:h:f:p:e:g", ["infolder=", "name=", 'steps=', 'hct=', 'flip=', 'pttype=', 'excl=', 'help'])



flip = 0
asl_tr = 4

do_run = {'trust':1,
          'vol':1,
          'asl':1
          }

for opt, arg in options:
    if opt in ('-i', '--infile'):
        in_folder = arg
    elif opt in ('-n', '--name'):
        deidentify_name = arg
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
        elif pt_type == 'sca' or pt_type == 'anemia':
            pt_type_num = 1
        elif pt_type == 'redcap':
            pt_type_num = pt_type
        else:
            raise Exception('Patient type must be "sca" or "control"')
    elif opt in ('-e', '--excl'):
        parsed_excl = arg.split(',')
        for p in parsed_excl:
            if p not in do_run:
                raise ValueError('Input for -e/--excl must contain only the processes to exclude (trust, vol or asl) separated by a comma with no spaces\ne.g., vol,trust')
            do_run[p] = 0
    elif opt in ('-g', '--help'):
        print(help_info)
        sys.exit()

try:
    if steps == '0':
        steps = '12'
except NameError:
    print('-s not specified. running all steps')
    steps = '123'
        
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
        ans = input(f'Input files seem to be NiFTI. ASL processing of NiFTIs is in an UNSTABLE BETA state.\nRESULTS MUST BE MANUALLY INSPECTED FOR CORRECTNESS. Please acknowledge this or cancel processing. [acknowledge/cancel]\n')
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
            print(f"MR ID {pt_id} appears to correspond to scan number {which_scan.index(True)+1} for this patient")
            print(f'(the mr_id was found in column {mri_cols[which_scan.index(True)]})')
            ans = input(f'Please confirm that this is correct, especially if you intend to push processing results to REDCap or are using the database values for hct/pt type. [y/n]\n')
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
                    
                    if hematocrit == 'redcap':
                        try:
                            hematocrit = float(cands.iloc[0][f'blood_draw_hct{scan_index+1}'])/100
                        except ValueError:
                            raise Exception(f'There is no hct value in blood_draw_hct{scan_index+1} in REDCap')
                        print(f'The study hematocrit I found is {hematocrit}')
                        
                    if pt_type_num == 'redcap':
                        the_num = cands.iloc[0]['case_control']
                        if the_num == '0':
                            pt_type_num = 0
                            descrip = 'control'
                        elif the_num == '1':
                            pt_type_num = 1
                            descrip = 'scd'
                        elif the_num == '2':
                            pt_type_num = 1
                            descrip = 'anemia'
                        print(f'The patient type I found is {the_num} ({descrip})')
                    print(f'The study id is {study_id}')
                    
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
    
    
    globber_pld = os.path.join(acquired_folder,'*PLD*')
    globber_ld = os.path.join(acquired_folder,'*LD*')
    
    names_with_pld = glob.glob(globber_pld)
    names_with_ld = glob.glob(globber_ld)
    

    if len(names_with_pld) == 0 or len(names_with_ld) == 0:
        print('No PLD/LD signature detected, implying a lack of ASL data. If you intend to run ASL processing this will be an issue.')

        has_ans = False
        while not has_ans:
            ans = input(f'\nWould you like to proceed anyway? [y/n]\n')
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
        ans = input(f'\nFound asl_pld: {pld}\nFound asl_ld: {ld}\nFound asl_tr: {tr}\nIs this okay? (y/n/show)\n')
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
                ans = input(f'\nI can try to fix the filenames for you, or you can exit processing and do it yourself. [fix/exit/info]\n')
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
    processing_input = f'''/Applications/MATLAB_R2016b.app/bin/matlab -nodesktop -nosplash -r "Master_v2('{pt_id}',{hematocrit},{pt_type_num},{flip},{asl_tr},{asl_pld},{asl_ld},{do_run['trust']},{do_run['vol']},{do_run['asl']})"'''
    
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
        ans = input(f'\nPush to database? Note that these results will not be correct if processing (asl+vol+TRUST) is not complete. [y/n]\n')
        if ans in ('y','n'):
            has_ans = True
            if ans == 'n':
                print('Data will not be pushed')
            elif ans == 'y':
                print('Pushing to database - this takes about a minute')
                for key, val in new_data.items():
                    studyid_index_data.loc[study_id][key] = val
                np = project.import_records(studyid_index_data)
                print(f'REDCap data import message: {np}')
                    
                print(f'\nData import complete. Elapsed time: {str_time_elapsed(start_stamp)} minutes')
        else:
            print('Answer must be "y" or "n"')
    
elif '3' in steps and not name_in_redcap:
    print(f"\nSkipping Step 3: can't push to REDCap as either the mr_id is not in the database or the database could not be contacted")
    

    

    
    
print(f'\nProcessing complete. Elapsed time: {str_time_elapsed(start_stamp)} minutes\n')





