#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Functions for reading in a scan and generating a multislice plot for
sticking in reports

"""

import subprocess
import os
import itertools

import matplotlib.pyplot as plt
import numpy as np
import nibabel as nib
from scipy import ndimage

from helpers import get_terminal


def par2nii(dcm, out_folder):
    
    path_to_dcm2nii = '/Users/manusdonahue/Documents/Sky/mricron/dcm2nii'
    conversion_command = f'{path_to_dcm2nii} -o {out_folder} -a n -i n -d n -p n -e n -f y -v n {dcm}'
    
    original_stem = get_terminal(dcm)[:-4]
    
    subprocess.run(conversion_command, check=True, shell=True)
    
    return os.path.join(out_folder, f'{original_stem}.nii.gz') # this is the name of the output


def filter_zeroed_axial_slices(nii_data):
    # removes slices if they are all 0 or contain any NaN
    keep = []
    for i in range(nii_data.shape[2]):
        d = nii_data[:,:,i]
        if not (d==0).all() and not (np.isnan(d).any()):
            keep.append(True)
        else:
            keep.append(False)
    
    new = nii_data[:,:,keep]
    return new


def nii_image(nii, dimensions, out_name, cmap, fltr=(0.5,99.5)):
    """
    Produces a png representing multiple AXIAL slices of a NiFTI

    Parameters
    ----------
    nii : str
        path to NiFTI in question.
    dimensions : tuple of int
        the dimensions of the subimages, (x,y). Produces x*y subplots.
    out_name : str
        name of the output image.
    cmap : str or matplotlib cmap
        matplotlib color map.
    fltr : tuple of float
        tuple indicating what the lower and upper percentiles of intensities should be used
        set as the max and min of the plot

    Returns
    -------
    None.

    """
    img = nib.load(nii)
    data = img.get_data()
    data = filter_zeroed_axial_slices(data)
    num_slices = data.shape[2] - 1 # num of axial slices
    
    d0, d1 = dimensions
    
    appropriate = False
    
    while not appropriate:
        num_subs = d0*d1
        
        if num_subs <= (num_slices+1):
            appropriate = True
        else:
            print(f'Notice: not enough slices to fill plot. Reducing plot dimensions for {out_name}')
            if d1 >= d0:
                d1 -= 1
            else:
                d0 -= 1
                
        if 0 in (d0, d1):
            raise Exception('Subplot dimensions cannot include 0')
        
        
        
    step = (num_slices - 0) / (num_subs - 1)
    frames = [int(0 + step * i) for i in range(num_subs)]
    
    d0_l = [i for i in range(d0)]
    d1_l = [i for i in range(d1)]
    
    subplots = list(itertools.product(d0_l, d1_l))
    
    mult = 3
    fig, ax = plt.subplots(d0, d1, figsize=(d1*mult,d0*mult))
    
    vmin, vmax = [int(i) for i in np.nanpercentile(data, fltr)]
    
    # print(vmin,vmax)
    
    # print(frames)
    # print(data.shape)
    
    for (i,j), f in zip(subplots, frames):
        ax_slice = ndimage.rotate(data[:,:,f].T, 180)
        im = ax[i][j].imshow(ax_slice, interpolation='nearest', cmap=cmap, vmin=vmin, vmax=vmax)
        ax[i][j].axis('off')
        
    plt.subplots_adjust(wspace=0.025, hspace=0.025)
    
    if cmap != 'gray':
        cbar_ax = fig.add_axes([0.91, 0.15, 0.01, 0.7])
        fig.colorbar(im, cbar_ax)

    plt.savefig(out_name)
    
    