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
import matplotlib
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


def filter_zeroed_axial_slices(nii_data, thresh=0.99):
    # removes slices if the number of pixels that are lesser than or equal to 0 exceeds a % threshold, and replaces NaN with -1
    the_data = nii_data.copy()
    wherenan = np.isnan(the_data)
    the_data[wherenan] = -1
    
    if thresh:
        keep = []
        for i in range(the_data.shape[2]):
            d = the_data[:,:,i]
            
            near_zero = np.isclose(d,0)
            less_zero = (d <= 0)
            
            bad_pixels = np.logical_or(near_zero, less_zero)
            
            perc_bad = bad_pixels.sum() / d.size
            
            if not perc_bad >= thresh:
                keep.append(True)
            else:
                keep.append(False)
        
        new = the_data[:,:,keep]
        return new
    else:
        return the_data


def compare_nii_images(niis, cmaps=[matplotlib.cm.gray,matplotlib.cm.inferno],
                       cmaxes=[None,None], save=True,
                       out_name=None, frames=6, ax_font_size=32):
    
    
    plt.style.use('dark_background')
        
    if type(frames) == int:
        nrows = frames
    elif type(frames) == list:
        nrows = len(frames)

    fig, axs = plt.subplots(nrows, 3, figsize=(3*3,nrows*1.95))
    fig.subplots_adjust(hspace=0.0, wspace=-0.4)
    
    data1 = nib.load(niis[0]).get_fdata()
    data2 = nib.load(niis[1]).get_fdata()
    datas = [data1,data2]
    
    num_slices = data1.shape[2] - 1 # num of axial slices
    
    if type(frames) == int:
        a_fifth = int(num_slices * 0.15)
        step = ((num_slices-a_fifth) - (0+a_fifth)) / (frames - 1)
        selected_frames = [int((0+a_fifth) + step * i) for i in range(frames)]
    else:
        selected_frames = frames
    
    for cmap in cmaps:
        cmap.set_bad('black',1.)
    
    for ax_row, f in zip(axs, selected_frames):
        
        ax_slice1 = ndimage.rotate(data1[:,:,f].T, 180)
        ax_slice1[np.isclose(ax_slice1,0)] = np.nan
        ax_slice1[ax_slice1 < 0] = np.nan
        ax_slice1 = np.fliplr(ax_slice1) # convert to radiological orientation
        
        ax_slice2 = ndimage.rotate(data2[:,:,f].T, 180)
        ax_slice2[np.isclose(ax_slice2,0)] = np.nan
        ax_slice2[ax_slice2 < 0] = np.nan
        ax_slice2 = np.fliplr(ax_slice2) # convert to radiological orientation
        
        
        vvals = [None,None]
        for i,val in enumerate(vvals):
            cmax = cmaxes[i]
            if cmaps[i] != matplotlib.cm.gray:
                if cmax is not None:    
                    vvals[i] = [0, cmax]
                else:
                    vvals[i] = [0, round(np.nanpercentile(datas[i], 99.5),2)]
            
            else:
                if cmax is not None:
                    vvals[i] = [0, round(np.nanpercentile(datas[i], cmax),2)]
                else:
                    vvals[i] = [0, round(np.nanpercentile(datas[i], 97.5),2)]
        
        #print(f'vvals: {vvals}')
        
        im1 = ax_row[0].imshow(ax_slice1, interpolation='nearest', cmap=cmaps[0], vmin=vvals[0][0], vmax=vvals[0][1])
        ax_row[0].axis('off')
        
        im3 = ax_row[2].imshow(ax_slice2, interpolation='nearest', cmap=cmaps[1], vmin=vvals[1][0], vmax=vvals[1][1])
        ax_row[2].axis('off')

        im2p1 = ax_row[1].imshow(ax_slice1, interpolation='nearest', cmap=cmaps[0], vmin=vvals[0][0], vmax=vvals[0][1], alpha=1)
        im2p2 = ax_row[1].imshow(ax_slice2, interpolation='nearest', cmap=cmaps[1], vmin=vvals[1][0], vmax=vvals[1][1], alpha=0.5)
        ax_row[1].axis('off')
        
    vmax = vvals[1][1]
    if vmax > 100:
        rounder = 0
        by = 20
    elif vmax > 50:
        rounder = 0
        by = 10
    elif vmax > 10:
        rounder = 0
        by = 5
    elif vmax > 1:
        rounder = 1
        by = 0.5
    else:
        rounder = 2
        by = 0.1
    
    vmax = round(vmax, rounder)

    if cmaps[1] != matplotlib.cm.gray:
            
        tks = list(np.arange(0, vmax, by))
        tks.append(vmax)
        
        if tks[-1] - tks[-2] < 0.35*by:
            del tks[-2] # if the last two ticks are very close together, delete the penultimate tick
        
        cbar_ax = fig.add_axes([0.1,0.055,0.8,0.015])
        fig.colorbar(im3, cbar_ax, orientation='horizontal', ticks=tks)
    
    #plt.tight_layout(0.2)
    if save:
        plt.savefig(out_name, dpi=200, bbox_inches='tight')
    else:
        plt.show()
        
    
    plt.rcParams.update(plt.rcParamsDefault)
    


def nii_image(nii, dimensions, out_name, cmap, cmax=None, save=True, specified_frames=None, ax_font_size=32):
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
    cmax : float
        optional arg for setting colorbar/intensity thresholds. If cmap is
        grayscale, cmax is used to set the upper percentile threshold. Otherwise,
        cmax is the maximum value of the colorbar.

    Returns
    -------
    The thresholding value (upper percentile for grayscale, absolute value for all other cmaps).

    """
    
    plt.style.use('dark_background')
    
    img = nib.load(nii)
    data = img.get_fdata()
    #data = filter_zeroed_axial_slices(data)
    data = filter_zeroed_axial_slices(data, thresh=False)
    
    num_slices = data.shape[2] - 1 # num of axial slices
    
    d0, d1 = dimensions
    
    """
    appropriate = False
    
    while not appropriate:
        num_subs = d0*d1
        
        if num_subs <= (num_slices+1):
            appropriate = True
        else:
            print(f'\n!!!!!\n\nNotice: not enough slices to fill plot. Reducing plot dimensions for {out_name}\n\n!!!!!\n')
            if d1 >= d0:
                d1 -= 1
            else:
                d0 -= 1
                
        if 0 in (d0, d1):
            raise Exception('Subplot dimensions cannot include 0')
        
    step = (num_slices - 0) / (num_subs - 1)
    frames = [int(0 + step * i) for i in range(num_subs)]
    """
    if cmap != matplotlib.cm.gray:
        frames = np.arange(10,40,1)
    else:
        frames = np.arange(0,25,1)
        
    if specified_frames:
        frames = specified_frames
    
    #print(f"FRAMES: {frames}")
    
    d0_l = [i for i in range(d0)]
    d1_l = [i for i in range(d1)]
    
    subplots = list(itertools.product(d0_l, d1_l))
    
    
    mult = 3
    
    fig, ax = plt.subplots(d0, d1, figsize=(d1*mult,d0*mult))
    
    if cmap != matplotlib.cm.gray:
        if cmax is not None:    
            vmin, vmax = [0, cmax]
        else:
            vmin, vmax = [0, round(np.nanpercentile(data, 99.5),2)]
        
        """
        round the scaling to nearest 10 for CBF, nearest 0.1 for CVR and CVRMax, and nearest 10 for CVRDelay. 
        """
        if vmax > 100:
            rounder = 0
            by = 20
        elif vmax > 50:
            rounder = 0
            by = 10
        elif vmax > 10:
            rounder = 0
            by = 5
        elif vmax > 1:
            rounder = 1
            by = 0.5
        else:
            rounder = 2
            by = 0.1
        
        vmax = round(vmax, rounder)
        ret_max = vmax
            
        
    else:
        if cmax is not None:
            vmin, vmax = [0, round(np.nanpercentile(data, cmax),2)]
            ret_max = cmax
        else:
            vmin, vmax = [0, round(np.nanpercentile(data, 97.5),2)]
            ret_max = 97.5
    
    # print(vmin,vmax)
    
    # print(frames)
    # print(data.shape)
    
        
    cmap.set_bad('black',1.)
    for (i,j), f in zip(subplots, frames):
        #print(f'FRAMING: {f}')
        ax_slice = ndimage.rotate(data[:,:,f].T, 180)
        ax_slice[np.isclose(ax_slice,0)] = np.nan
        ax_slice[ax_slice < 0] = np.nan
        ax_slice = np.fliplr(ax_slice) # convert to radiological orientation
        im = ax[i][j].imshow(ax_slice, interpolation='nearest', cmap=cmap, vmin=vmin, vmax=vmax)
        ax[i][j].axis('off')
    
    
    matplotlib.rcParams.update({'font.size': ax_font_size})
    plt.tight_layout(0.8)
    
    if cmap != matplotlib.cm.gray:
            
        tks = list(np.arange(0, vmax, by))
        tks.append(vmax)
        
        if tks[-1] - tks[-2] < 0.35*by:
            del tks[-2] # if the last two ticks are very close together, delete the penultimate tick
        
        cbar_ax = fig.add_axes([0.1,0.055,0.8,0.015])
        fig.colorbar(im, cbar_ax, orientation='horizontal', ticks=tks)
    else:
        pass
    
    plt.subplots_adjust(wspace=0.000, hspace=0.000)

    if save:
        plt.savefig(out_name, dpi=200)
    else:
        plt.show()
    
    plt.rcParams.update(plt.rcParamsDefault)
    
    return ret_max
    
    