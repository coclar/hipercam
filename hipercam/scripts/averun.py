import sys
import os

import numpy as np

import hipercam as hcam
from hipercam import cline, utils
from hipercam.cline import Cline

__all__ = ['averun',]

############################
#
# combine -- combines images
#
############################

def averun(args=None):
    """Averages images from a run using median combination. Only combines those
    CCDs for which is_data() is true (i.e. it skips blank frames caused by
    NSKIP / NBLUE options). The intention is to provide a simple routine to
    create median frames suitable for aperture selection with 'setaper'. See
    'combine' if you want more fine-grained control for frame averaging.

    Arguments::

        source  : (string) [hidden]
           Data source, five options::

               'hs' : HiPERCAM server
               'hl' : local HiPERCAM FITS file
               'us' : ULTRACAM server
               'ul' : local ULTRACAM .xml/.dat files
               'hf' : list of HiPERCAM hcm FITS-format files

           'hf' is used to look at sets of frames generated by 'grab' or
           converted from foreign data formats.

        run     : (string) [if source ends 's' or 'l']
           run number to access, e.g. 'run034'

        flist   : (string) [if source ends 'f']
           name of file list

        first   : (int) [if source ends 's' or 'l']
           exposure number to start from. 1 = first frame ('0' is
           not supported).

        last    : (int) [if source ends 's' or 'l']
           last exposure number must be >= first.

        twait   : (float) [if source ends 's' or 'l'; hidden]
           time to wait between attempts to find a new exposure, seconds.

        tmax    : (float) [if source ends 's' or 'l'; hidden]
           maximum time to wait between attempts to find a new exposure, seconds.

        bias    : (string)
           Name of bias frame to subtract, 'none' to ignore.

        clobber : (bool) [hidden]
           clobber any pre-existing output files

        output  : (string)
           output file

    Notes: this routine reads all inputs into memory (40MB per frame for full
    5 CCD HiPERCAM frames for instance), so it can be a bit of a
    hog. 'combine' has a smaller footprint; 'averun' is meant for quick
    generation of averages from the first few files of a run rather than
    something more sophisticated.

    """

    command, args = utils.script_args(args)

    # get the inputs
    with Cline('HIPERCAM_ENV', '.hipercam', command, args) as cl:

        # register parameters
        cl.register('source', Cline.GLOBAL, Cline.HIDE)
        cl.register('run', Cline.GLOBAL, Cline.PROMPT)
        cl.register('first', Cline.LOCAL, Cline.PROMPT)
        cl.register('last', Cline.LOCAL, Cline.PROMPT)
        cl.register('twait', Cline.LOCAL, Cline.HIDE)
        cl.register('tmax', Cline.LOCAL, Cline.HIDE)
        cl.register('flist', Cline.LOCAL, Cline.PROMPT)
        cl.register('bias', Cline.LOCAL, Cline.PROMPT)
        cl.register('clobber', Cline.LOCAL, Cline.HIDE)
        cl.register('output', Cline.LOCAL, Cline.PROMPT)

        # get inputs
        source = cl.get_value(
            'source', 'data source [hs, hl, us, ul, hf]',
            'hl', lvals=('hs','hl','us','ul','hf')
        )

        # set a flag
        server_or_local = source.endswith('s') or source.endswith('l')

        if server_or_local:
            run = cl.get_value('run', 'run name', 'run005')
            first = cl.get_value('first', 'first frame to average', 1, 1)
            last = cl.get_value('last', 'last frame to average', first, first)
            twait = cl.get_value(
                'twait', 'time to wait for a new frame [secs]', 1., 0.)
            tmax = cl.get_value(
                'tmax', 'maximum time to wait for a new frame [secs]', 10., 0.)

        else:
            run = cl.get_value('flist', 'file list',
                               cline.Fname('files.lis',hcam.LIST))
            first = 1

        # bias frame (if any)
        bias = cl.get_value(
            'bias', "bias frame ['none' to ignore]",
            cline.Fname('bias', hcam.HCAM), ignore='none'
        )
        if bias is not None:
            # read the bias frame
            bias = hcam.MCCD.read(bias)

        clobber = cl.get_value(
            'clobber', 'clobber any pre-existing files on output',
            False
        )

        outfile = cl.get_value(
            'output', 'output average',
            cline.Fname(
                'hcam', hcam.HCAM,
                cline.Fname.NEW if clobber else cline.Fname.NOCLOBBER
            )
        )

    # inputs done with

    # read and store the data
    mccds = []
    nframe = first
    total_time = 0
    print('Reading frames')
    with hcam.data_source(source, run, first) as spool:

        # 'spool' is an iterable source of MCCDs
        for mccd in spool:

            if server_or_local:
                # Handle the waiting game ...
                give_up, try_again, total_time = hcam.hang_about(
                    mccd, twait, tmax, total_time
                )

                if give_up:
                    print('rtplot stopped')
                    break
                elif try_again:
                    continue

            mccds.append(mccd)
            print(' read frame {:d}'.format(nframe))

            if nframe >= last:
                break
            nframe += 1

    if len(mccds) == 0:
        raise hcam.HipercamError('no frames read')
    else:
        print('{:d} frames read'.format(len(mccds)))

    # set up some buffers to hold the OK CCDs only
    template = mccd.copy()

    if bias is not None:
        # crop the bias
        bias = bias.crop(template)

    ccds = dict([(cnam,[]) for cnam in template])

    for mccd in mccds:
        for cnam, ccd in mccd.items():
            if ccd.is_data():
                if bias is not None:
                    ccd -= bias[cnam]
                ccds[cnam].append(ccd)

    # check that we have some frames in all CCDs
    for cnam in template:
        if len(ccds[cnam]) == 0:
            raise hcam.HipercamError(
                'found no valid frames for CCD {:s}'.format(cnam)
            )

    for cnam in template:

        # loop through CCD by CCD
        print(
            "Averaging {:d} CCDs labelled '{:s}'".format(
                len(ccds[cnam]),cnam)
        )

        for wnam, wind in template[cnam].items():
            # build list of all data arrays
            arrs = [ccd[wnam].data for ccd in ccds[cnam]]
            arr3d = np.stack(arrs)
            wind.data = np.median(arr3d,axis=0)

    # write out
    template.write(outfile, clobber)
    print('\nFinal average written to {:s}'.format(outfile))
