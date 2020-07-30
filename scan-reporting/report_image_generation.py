#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Functions for reading in a scan and generating a multislice plot for
sticking in reports

"""

import subprocess

def dcm2nii(dcm, out_folder):
    
    path_to_dcm2nii = '/Users/manusdonahue/Documents/Sky/mricron/dcm2nii'
    conversion_command = f'{path_to_dcm2nii} -o {out_folder} -a n -i n -d n -p n -e n -f y -v n {dcm}'
    subprocess.run(conversion_command, check=True, shell=True)
