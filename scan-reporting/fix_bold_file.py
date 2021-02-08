#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""

This script is intended to read in a BOLD NiFTI that has been prematurely cancelled
(due to patient discomfort, technical issues, etc.) and then "reconstruct" the
missing images so the file can be processed as normal

"""



import os
import sys

import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import nibabel as nib

#####

input_filename = '/Users/manusdonahue/Desktop/Projects/BOLD/Data/PTSTEN_187_02/bold_work/bold_work_WIPBOLD_CO2_ACPC2_STROKEWOCONTRAST_19770703150928_2.nii.gz' # this is the messed up one
ref_filename = '/Users/manusdonahue/Desktop/Projects/BOLD/Data/PTSTEN_187_02/bold_work/ref/ref_WIPBOLD_CO2_ACPC2_STROKEWOCONTRAST_19770703150928_3.nii.gz' # this is a proper sample

write_filename = '/Users/manusdonahue/Desktop/Projects/BOLD/Data/PTSTEN_187_02/bold_work/PTSTEN_187_02_WIPBOLD_CO2_ACPC2_STROKEWOCONTRAST_19770703150928_2_FIXED.nii.gz'

#####

img = nib.load(input_filename)
head = img.header
data = img.get_fdata()

ref_img = nib.load(ref_filename)
ref_head = ref_img.header
ref_data = ref_img.get_fdata()


tees = data.shape[3]

exes = np.arange(0,tees,1)
slices = [data[:,:,:,i] for i in exes]
whys = [np.mean(i) for i in slices]



ref_tees = ref_data.shape[3]

ref_exes = np.arange(0,ref_tees,1)
ref_slices = [ref_data[:,:,:,i] for i in ref_exes]
ref_whys = [np.mean(i) for i in ref_slices]

plt.figure()
plt.plot(ref_exes,ref_whys,label='Reference',alpha=0.5)
plt.plot(exes,whys,label='Target',alpha=1)

slices_not_in = [i for i in range(ref_tees) if i not in range(tees)]

new_data = np.empty(ref_data.shape)

for i in slices_not_in:
    new_data[:,:,:,i] = data[:,:,:,tees-1]
    
for i in range(tees):
    new_data[:,:,:,i] = data[:,:,:,i]
    


add_slices = [new_data[:,:,:,i] for i in ref_exes]
add_whys = [np.mean(i) for i in add_slices]
plt.plot(ref_exes,add_whys,label='Added',alpha=0.5)
    
plt.title('Rectification')
plt.legend()

head['dim'] = ref_head['dim']

out_image = nib.Nifti1Image(new_data,img.affine,head)
nib.save(out_image, write_filename)


# check to make sure it worked

w_img = nib.load(write_filename)
w_head = w_img.header
w_data = w_img.get_fdata()
w_tees = w_data.shape[3]
w_exes = np.arange(0,w_tees,1)
w_slices = [w_data[:,:,:,i] for i in w_exes]
w_whys = [np.mean(i) for i in w_slices]

plt.figure()
plt.title('Checking')

plt.plot(ref_exes,ref_whys,label='Reference',alpha=0.5)
plt.plot(w_exes,w_whys,label='Rectified',alpha=1)

plt.legend()


