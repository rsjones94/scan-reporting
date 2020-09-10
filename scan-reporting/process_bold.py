#!/usr/bin/env python3

# -*- coding: utf-8 -*-
"""
This script takes raw scan data for BOLD scans and processes it completely.
This involves:
    1) deidentifying the scans
    2) generating derived images - CBF, CVR, CVR_Max, and CVR_Delay images in native space, T1 space, and 4 mm MNI space.
    3) generating the CVR movie
    4) metrics calculation
    5) reporting image generation
    6) creating patient scan report as a powerpoint (not yet implemented)
    
    
input:
    -i / --infolder : the path to the folder of pt data. of form /Users/manusdonahue/Desktop/Projects/BOLD/Data/[PTSTEN_ID]
        this folder should have one subfolder, acquired, which contains the raw scans
    -n / --name : the name of the patient to deidentify. Only required if running step 1
    -s / --steps : the steps to actually calculate, passed as a string of numbers
        if 0, all steps will be carried out. Otherwise, only the steps that appear
        in the string will be carried out. For example, 134 will cause the script
        to only go through steps 1, 3 and 4
    -d / --dob : the date of birth as YYYY.mm.dd, or their age as a float
        Only used in step 6. If -d is a date, the dob, age and metric plotting
        is completed in the template for you (age is calculated as differnce between
        scan date in PAR files and DOB). If -d is an age, only the age and metric
        plotting is completed. If -d is not supplied, then neither the dob or age is completed,
        and plotting is carried out using age=0.
"""

import os
import sys
import getopt
import subprocess
import time
import datetime
import glob
import shutil
import datetime

from pptx import Presentation
import matplotlib
import matplotlib.pyplot as plt
import pandas as pd
import nibabel as nib

from helpers import get_terminal, str_time_elapsed, any_in_str, replace_in_ppt, analyze_ppt, add_ppt_image, add_ppt_image_ph, plot_dot
from report_image_generation import par2nii, nii_image

inp = sys.argv
bash_input = inp[1:]
options, remainder = getopt.getopt(bash_input, "i:n:s:d:", ["infolder=","name=",'steps=','dob='])

for opt, arg in options:
    if opt in ('-i', '--infile'):
        in_folder = arg
    elif opt in ('-n', '--name'):
        deidentify_name = arg
    elif opt in ('-s', '--steps'):
        steps = arg
    elif opt in ('-d', '--dob'):
        dobage = arg

try:
    if steps == '0':
        steps = '123456'
except NameError:
    print('-s not specified. running all steps')
    steps = '123456'
        
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
    deid_scripts_loc = r'/Users/manusdonahue/Desktop/Projects/BOLD/Scripts/deidentifySLW'
    
    strip_filename_input = f'deidentifyFileNames.sh {in_folder} {deidentify_name} {replacement}'
    strip_header_input = f'deidentifyPARfiles.sh {in_folder}'
    
    deid_commands = [os.path.join(deid_scripts_loc, c) for c in (strip_filename_input, strip_header_input)]
    
    for com in deid_commands:
        subprocess.run([com], check=True, shell=True)
        
    print(f'\nDeidentification complete. Elapsed time: {str_time_elapsed(start_stamp)} minutes')

if '2' in steps:    
    ##### step 2 : main processing
    
    print(f'Step 2: begin main processing sequence\n')
    
    asltype = 'Baseline'
    dynamics = 360
    

    has_ans = False
    while not has_ans:
        ans = input('What is the ASL type? [PASL / pCASL]\n')
        if ans in ('pCASL', 'PASL'):
            has_ans = True
            confirm = input(f'Please confirm that ASL type is {ans} by entering the ASL type again\n')
            if ans != confirm:
                has_ans = False
                print(f'\nConfirmation failed ({ans} != {confirm})\n')
            else:
                print('\nEntry confirmed\n')
        else:
            print('Answer must be PASL or pCASL')
            
    if ans == 'pCASL':
        pcaslBool = 1
    elif ans == 'PASL':
        pcaslBool = 0
    
    
    processing_scripts_loc = r'/Users/manusdonahue/Desktop/Projects/BOLD/Scripts/'
    os.chdir(processing_scripts_loc)
    processing_input = f'''/Applications/MATLAB_R2016b.app/bin/matlab -nojvm -nodesktop -nosplash -r "Master('{pt_id}','{asltype}',{dynamics},{pcaslBool})"'''
    
    # print(processing_input)
    
    subprocess.run(processing_input, check=True, shell=True)
    # subprocess.run('quit force', check=True, shell=True)
    
    os.chdir(original_wd)
    
    print(f'\nMain processing complete. Elapsed time: {str_time_elapsed(start_stamp)} minutes')
    
if '3' in steps:
    ##### step 3 : generate cvr movie
    
    print(f'\nStep 3: generating CVR movie')
    
    movie_scripts_loc = r'/Users/manusdonahue/Desktop/Projects/BOLD/Scripts/zstatMov'
    os.chdir(movie_scripts_loc)
    
    pt1 = f'./mkZstatMov_part1_v2.sh /Users/manusdonahue/Desktop/Projects/BOLD/Data/{pt_id}'
    subprocess.run(pt1, check=True, shell=True)
    
    mov_filepath = f'/Users/manusdonahue/Desktop/Projects/BOLD/Data/{pt_id}/{pt_id}_zstatMovie.nii.gz'
    
    pt2 = f'''/Applications/MATLAB_R2016b.app/bin/matlab -nodesktop -nosplash -r "mkZstatMov_part2_v4('{mov_filepath}')"'''
    subprocess.run(pt2, check=True, shell=True)
    # subprocess.run('quit force', check=True, shell=True)
    
    os.chdir(original_wd)
    
    print(f'\nCVR movie generation complete. Elapsed time: {str_time_elapsed(start_stamp)} minutes')
    

if '4' in steps:
    ##### step 4 : metrics calculation
    
    print(f'\nStep 4: calculating metrics')
    
    processing_scripts_loc = r'/Users/manusdonahue/Desktop/Projects/BOLD/Scripts/'
    os.chdir(processing_scripts_loc)
    
    cmd = f'''/Applications/MATLAB_R2016b.app/bin/matlab -nodesktop -nosplash -r "Calculate_Metrics('{pt_id}', 1)"'''
    subprocess.run(cmd, check=True, shell=True)
    
    os.chdir(original_wd)
    
    print(f'\nMetrics calculation complete. Elapsed time: {str_time_elapsed(start_stamp)} minutes')
    

signature_relationships = {('FLAIR_AX', 'T2W_FLAIR'):
                               {'basename': 'axFLAIR', 'excl':['cor','COR','coronal','CORONAL'], 'isin':'acquired', 'ext':'PAR', 'cmap':matplotlib.cm.gray, 'dims':(4,6)},
                           ('CBF_MNI',):
                               {'basename': 'CBF', 'excl':[], 'isin':'processed', 'ext':'nii.gz', 'cmap':matplotlib.cm.jet, 'dims':(3,10)},
                           ('ZSTAT1_MNI_normalized',):
                               {'basename': 'CVR', 'excl':[], 'isin':'processed', 'ext':'nii.gz', 'cmap':matplotlib.cm.jet, 'dims':(3,10)},
                           ('ZMAX2STANDARD_normalized',):
                               {'basename': 'CVRmax', 'excl':[], 'isin':'processed', 'ext':'nii.gz', 'cmap':matplotlib.cm.jet, 'dims':(3,10)},
                           ('TMAX2STANDARD',):
                               {'basename': 'CVRdelay', 'excl':[], 'isin':'processed', 'ext':'nii.gz', 'cmap':matplotlib.cm.jet, 'dims':(3,10)},
                          }
    
reporting_folder = os.path.join(in_folder, 'reporting_images')
conversion_folder = os.path.join(reporting_folder, 'gathered')
if '5' in steps:
    ##### step 5 : reporting image generation
    ## FLAIR, CBF, CVR, CVRmax, CVRdelay
    # EtCO2 and OEF?
    
    print(f'\nStep 5: generating reporting images')
    
    thresh_names = []
    thresh_vals = []
    
    thresh_file = os.path.join(in_folder, 'thresh_vals.csv')
    
    has_thresh_file = 0
    try:
        thresh_data = pd.read_csv(thresh_file, header=None, index_col=0)
        has_thresh_file = 1
    except FileNotFoundError:
        pass

    if os.path.exists(reporting_folder):
        shutil.rmtree(reporting_folder)
    os.mkdir(reporting_folder)
    os.mkdir(conversion_folder)

    for signature, subdict in signature_relationships.items():
        
        if has_thresh_file:
            cmax = float(thresh_data.loc[subdict['basename']])
        else:
            cmax = None
            
        
        candidates = []
        # note that the signature matching includes the full path. probably not a great idea
        for subsig in signature:
            where_glob = os.path.join(in_folder, subdict['isin'], "**", f'*{subsig}*.{subdict["ext"]}')
            potential = glob.glob(where_glob, recursive=True)
            potential = [f for f in potential if not any_in_str(f, subdict['excl'])]
            candidates.extend(potential)
            
        if candidates:
            foi = candidates[-1] # pick the last in list. file of interest
        else:
            continue
        
        new_stem = f'{subdict["basename"]}.nii.gz'
        new_name = os.path.join(conversion_folder, new_stem)
        
        if subdict['ext'] == 'PAR':
            moved_name = par2nii(foi, conversion_folder)
            os.rename(moved_name, new_name)
        else:
            shutil.copy(foi, new_name)
            
        im_name = os.path.join(reporting_folder, f'{subdict["basename"]}_report_image.png')
        thresh_vals.append(nii_image(new_name, subdict['dims'], im_name, cmap=subdict['cmap'], cmax=cmax))
        thresh_names.append(subdict["basename"])
            
    
    thresh_dict = {key:val for key,val in zip(thresh_names, thresh_vals)}
    thresh_ser = pd.Series(thresh_dict)
    thresh_ser.to_csv(thresh_file, header=False)
    
    
    print(f'\nReporting images generated. Elapsed time: {str_time_elapsed(start_stamp)} minutes')
    
if '6' in steps:
    ##### step 6: make the powerpoint
    
    print(f'\nStep 6: generating powerpoint')
    
    # get pt info if available
    has_age = 0
    has_dob = 0
    has_scan_date = 0
    try:
        if '.' in dobage:
            dob = dobage
            format_str = '%Y.%m.%d' # The format
            dob_dt_obj = datetime.datetime.strptime(dob, format_str)
            has_dob = 1
        else:
            pt_age = int(dobage)
            has_age = 1
    except NameError:
        pt_age = 0
    
    
    where_glob = os.path.join(in_folder, 'acquired', "**", f'*.PAR') # just looking for any PAR
    potential = glob.glob(where_glob, recursive=True)
    read_this_one = potential[-1]
    fob = open(read_this_one)
    info = nib.parrec.parse_PAR_header(fob)
    info_dict = info[0]
    if 'exam_date' in info_dict:
        try:
            raw_scan_date = info_dict['exam_date']
            sd = raw_scan_date.split(' / ')[0]
            format_str = '%Y.%m.%d' # The format
            scan_dt_obj = datetime.datetime.strptime(sd, format_str)
            has_scan_date = 1
        except:
            print('Something went wrong with extracting the scan date, though the PAR file does seem to have a scan date')
        
    if has_scan_date and has_dob:
        pt_age = scan_dt_obj - dob_dt_obj
        pt_age = int(pt_age.days/365.25)
        has_age = 1
        
    
    
    # make the etco2 trace
    try:
        etco2_file = os.path.join(in_folder, 'etco2.csv')
        etco2_fig = os.path.join(reporting_folder, 'etco2.png')
        
        etco2_data = pd.read_csv(etco2_file)
        dynamics = etco2_data.iloc[:, 0]
        co2 = etco2_data.iloc[:, 1]
        
        plt.figure(figsize=((12,8)))
        plt.plot(dynamics, co2, lw=1)
        plt.scatter(dynamics, co2, color='black')
        plt.ylabel('EtCO2 (mmHg)')
        plt.xlabel('Dynamic Scan')
        plt.tight_layout()
        plt.savefig(etco2_fig)
        plt.close()
    except FileNotFoundError:
        print(f'EtCO2 trace not found. The graph will not be generated and added to report.')
        
    
    template_loc = r'/Users/manusdonahue/Documents/Sky/repositories/scan-reporting/bin/TEMPLATE_BOLD_PLACEHOLDERS.pptx'
    template_out = os.path.join(in_folder, f'{pt_id}_report.pptx')
    
    shutil.copyfile(template_loc, template_out)
    
    replace_in_ppt('PTSTEN_###_##', pt_id, template_out)
    if has_dob:
        replace_in_ppt('dobYYYYmmdd', dob, template_out)
        print(f'DOB is {dob}')
    if has_age:
        replace_in_ppt('age##', pt_age, template_out)
        print(f'Age is {pt_age}')
    if has_scan_date:
        replace_in_ppt('scan_dateYYYYmmdd', sd, template_out)
        print(f'Scan date is {sd}')
        
    # replace_in_ppt('IMAGING', 'it worked!', template_out)
    
    #markup = os.path.join(in_folder, f'{pt_id}_report_MARKUP.pptx')
    #analyze_ppt(template_out, markup)
    
    """
    Slide 3: FLAIR
    Slide 4: CBF
    Slide 6: CVR
    Sldie 7: CVRmax
    Slide 8: CVRdelay
    Slide 10: CVR video
    Slide 11: EtCO2
    """
    
    pres = Presentation(template_out)
    
    im_names = [os.path.join(reporting_folder, f"{val['basename']}_report_image.png") for key,val in signature_relationships.items()]
    slides = [2, 3, 5, 6, 7]

    """
    movie = os.path.join(in_folder, f'{pt_id}_zstatMovie.mp4')
    movie_slide = 9
    add_ppt_image(pres.slides[movie_slide], movie, insert_type='mov', poster=im_names[0])
    """
    
    etco2_slide = 10
    
    slides.append(etco2_slide)
    im_names.append(etco2_fig)
    
    
    for slide, name in zip(slides, im_names):
        #add_ppt_image_ph(pres.slides[slide], 10, name) # don't ask why idx is 10. it for all the placeholders in this template
        try:
            add_ppt_image(pres.slides[slide], name)
        except FileNotFoundError:
            print(f'\n!!!!!\nWARNING: image {name} not found and could not be added to report\n!!!!!\n')
    
    # metrics are written as CSVs in the PSTEN_ID folder called TMAX_metrics and CBF_metrics
    # the values within are ordered as lACA, rACA, lMCA, rMCA, lPCA, rPCA
    # but the origins are MCA, ACA, PCA

    
    # plotting values by converting units to positions on a powerpoint slide
    # father forgive me for I must sin

    plot_indices = {'MCA':0, 'ACA':1, 'PCA':2}
    
    metric_names = 'lACA, rACA, lMCA, rMCA, lPCA, rPCA'.split(', ')
    plot_on = [i[1:] for i in metric_names]
    lr = [i[0] for i in metric_names]
    
    dot_sides = ['left_dot.png', 'right_dot.png']
    dot_keys = ['l', 'r']
    dot_dict = {key:os.path.join(r'/Users/manusdonahue/Documents/Sky/repositories/scan-reporting/bin', val) for key,val in zip(dot_keys, dot_sides)}
    
    file_names = ['CBF_metrics.csv', 'TMAX_metrics.csv']
    metrics_files = [os.path.join(in_folder, fn) for fn in file_names]
    slides = [4, 8]
    
    x_units_per_inch = 60 / (3.41 - 0.98) # years per inch
    y_units_per_inch_cbv = 100 / (5.5 - 2.88)
    y_units_per_inch_cvrdelay = 50 / (5.5 - 2.88)
    yupis = [y_units_per_inch_cbv, y_units_per_inch_cvrdelay]
    
    origins_cbv = [[1.03,5.51], [4.56,5.51], [8.10,5.51]] # false origins at (20yrs, 0y_units). must be adjusted
    origins_cvrd = [[0.98,5.51], [4.51,5.51], [8.05,5.51]] # false origins at (20yrs, 0y_units). must be adjusted
    adjustment = 20 / x_units_per_inch
    origins = [origins_cbv, origins_cvrd]
    for i in origins:
        for j in i:
            j[0] -= adjustment
    
    for fi, slide, yupi, origins in zip(file_names, slides, yupis, origins):
        # print(f'On slide {slide}')
        mets = pd.read_csv(os.path.join(in_folder, fi), index_col=False, header=0)
        mets = [float(i) for i in mets.columns]
        for met, plottype, side in zip(mets, plot_on, lr):
            origin = origins[plot_indices[plottype]]
            image = dot_dict[side]
            
            ad_x = pt_age / x_units_per_inch
            ad_y = met / yupi
            
            plot_dot(pres.slides[slide], image, pt_age, met,
                     origin, x_units_per_inch, yupi, size=0.11)
            
    pres.save(template_out)
    print(f'\nPowerpoint generated. Elapsed time: {str_time_elapsed(start_stamp)} minutes')
    
print(f'\nProcessing complete. Elapsed time: {str_time_elapsed(start_stamp)} minutes\n')