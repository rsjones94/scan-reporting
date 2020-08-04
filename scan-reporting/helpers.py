#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Jul 30 12:38:31 2020

@author: manusdonahue
"""

import os
import time
from PIL import Image

from pptx import Presentation
from pptx.util import Inches


def replace_in_ppt(search_str, repl_str, filename):
    """"search and replace text in PowerPoint while preserving formatting"""
    #Useful Links ;)
    #https://stackoverflow.com/questions/37924808/python-pptx-power-point-find-and-replace-text-ctrl-h
    #https://stackoverflow.com/questions/45247042/how-to-keep-original-text-formatting-of-text-with-python-powerpoint
    prs = Presentation(filename)
    for slide in prs.slides:
        for shape in slide.shapes:
            if shape.has_text_frame:
                if(shape.text.find(search_str))!=-1:
                    text_frame = shape.text_frame
                    cur_text = text_frame.paragraphs[0].runs[0].text
                    new_text = cur_text.replace(str(search_str), str(repl_str))
                    text_frame.paragraphs[0].runs[0].text = new_text
    prs.save(filename)


def analyze_ppt(inp, output):
    """ Take the input file and analyze the structure.
    The output file contains marked up information to make it easier
    for generating future powerpoint templates.
    """
    prs = Presentation(inp)
    # Each powerpoint file has multiple layouts
    # Loop through them all and  see where the various elements are
    for index, _ in enumerate(prs.slide_layouts):
        slide = prs.slides.add_slide(prs.slide_layouts[index])
        # Not every slide has to have a title
        try:
            title = slide.shapes.title
            title.text = 'Title for Layout {}'.format(index)
        except AttributeError:
            print("No Title for Layout {}".format(index))
        # Go through all the placeholders and identify them by index and type
        for shape in slide.placeholders:
            if shape.is_placeholder:
                phf = shape.placeholder_format
                # Do not overwrite the title which is just a special placeholder
                try:
                    if 'Title' not in shape.text:
                        shape.text = 'Placeholder index:{} type:{}'.format(phf.idx, shape.name)
                except AttributeError:
                    print("{} has no text attribute".format(phf.type))
                print('{} {}'.format(phf.idx, shape.name))
    prs.save(output)


def plot_dot(slide, dot_img, x, y, origin, xpi, ypi, size=0.1):
    """
    A very specific function for putting a dot on an image of a line plot
    in a powerpoint.
    

    Parameters
    ----------
    slide : pptx slide object
        the slide you're plotting in.
    dot_img : str
        path to image you want to place
    x : float
        the x value to plot.
    y : float
        the y value to plot.
    origin : tuple of int
        x,y of the origin of the chart in inches.
    xpi : float
        the number of x units per inch.
    ypi : float
        the number of y units per inch.
    size: float
        size of the inserted dot image

    Returns
    -------
    None.

    """
    
    # images are placed using the coords of their upper left corner... right?
    
    loc_x = x / xpi
    loc_y = y / ypi
    
    im = Image.open(dot_img)
    width, height = (size,size)
    
    x_offset = int(width/2)
    y_offset = int(height/2)
    
    actual_x = loc_x - x_offset
    actual_y = loc_y - y_offset
    
    ox, oy = origin
    plot_x = ox + actual_x
    plot_y = oy - actual_y 

    shp = slide.shapes
    picture = shp.add_picture(im, Inches(plot_x), Inches(y))


def add_ppt_image(slide, img, scale=0.3, insert_type='img', poster=None):
    
    shp = slide.shapes
    
    if insert_type=='img':
        im = Image.open(img)
        width, height = im.size
        picture = shp.add_picture(img, 0, 0)
        picture.width = int(picture.width*scale)
        picture.height = int(picture.height*scale)
    elif insert_type=='mov':
        picture = slide.shapes.add_movie(img, 0, 0, 20000, 20000, poster_frame_image=poster, mime_type='video/mp4')
        

def add_ppt_image_ph(slide, placeholder_id, image_url):
    placeholder = slide.placeholders[placeholder_id]
 
    # Calculate the image size of the image
    im = Image.open(image_url)
    width, height = im.size
 
    # Make sure the placeholder doesn't zoom in
    placeholder.height = height
    placeholder.width = width
 
    # Insert the picture
    placeholder = placeholder.insert_picture(image_url)
    
    # Calculate ratios and compare
    image_ratio = width / height
    placeholder_ratio = placeholder.width / placeholder.height
    ratio_difference = placeholder_ratio - image_ratio
 
    # Placeholder width too wide:
    if ratio_difference > 0:
        difference_on_each_side = ratio_difference / 2
        placeholder.crop_left = -difference_on_each_side
        placeholder.crop_right = -difference_on_each_side
    # Placeholder height too high
    else:
        difference_on_each_side = -ratio_difference / 2
        placeholder.crop_bottom = -difference_on_each_side
        placeholder.crop_top = -difference_on_each_side


def get_terminal(path):
    """
    Takes a filepath or directory tree and returns the last file or directory
    

    Parameters
    ----------
    path : path
        path in question.

    Returns
    -------
    str of only the final file or directory.

    """
    
    return os.path.basename(os.path.normpath(path))


def str_time_elapsed(start):
    now = time.time()
    out = now - start
    pretty = round(out/60, 2)
    return pretty


def any_in_str(s, l):
    """
    Returns whether any of a list of substrings is in a string
    

    Parameters
    ----------
    s : str
        string to look for substrings in.
    l : list of str
        substrings to check for in s.

    Returns
    -------
    bool

    """
    
    return any([substr in s for substr in l])