#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Jul 30 12:38:31 2020

@author: manusdonahue
"""

import os
import time

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