import sys
import os
import time

import numpy as np
import matplotlib.pyplot as plt
from astropy.time import Time, TimeDelta

from trm.pgplot import *
import hipercam as hcam
import hipercam.cline as cline
from hipercam.cline import Cline

__all__ = ['rtplot',]

######################################
#
# rtplot -- display of multiple images
#
######################################

def rtplot(args=None):
    """Plots a sequence of images as a movie in near 'real time', hence
    'rt'. Designed to be used to look at images coming in while at the
    telescope, 'rtplot' comes with many options, a large number of which are
    hidden by default, and many of which are only prompted if other arguments
    are set correctly. If you want to see them all, invoke as 'rtplot PROMPT'.

    rtplot can source data from both the ULTRACAM and HiPERCAM servers, from
    local 'raw' ULTRACAM and HiPERCAM files (i.e. .xml + .dat for ULTRACAM, 3D
    FITS files for HiPERCAM) and from lists of HiPERCAM '.hcm' files.

    rtplot optionally allows the selection of targets to be fitted with
    gaussian or moffat profiles, and, if successful, will plot circles of 2x
    the measured FWHM in green over the selected targets. This option only
    works if a single CCD is being plotted.

    Arguments::

        source  : (string) [hidden]
           's' = server, 'l' = local, 'f' = file list (ucm for ULTRACAM /
           ULTRASPEC, FITS files for HiPERCAM)

        inst    : (string) [hidden]
           If 's' = server, 'l' = local, name of instrument. Choices: 'u' for
           ULTRACAM / ULTRASPEC, 'h' for HiPERCAM. This is needed because of the
           different formats.

        device  : (string) [hidden]
          Plot device. PGPLOT is used so this should be a PGPLOT-style name,
          e.g. '/xs', '1/xs' etc. At the moment only ones ending /xs are
          supported.

        width   : (float) [hidden]
           plot width (inches). Set = 0 to let the program choose.

        height  : (float) [hidden]
           plot height (inches). Set = 0 to let the program choose. BOTH width
           AND height must be non-zero to have any effect

        run     : (string) [if source == 's' or 'l']
           run number to access, e.g. 'run034'

        flist   : (string) [if source == 'f']
           name of file list

        first   : (int) [if source='s' or 'l']
           exposure number to start from. 1 = first frame; set = 0 to
           always try to get the most recent frame (if it has changed)

        twait   : (float) [if source == 's'; hidden]
           time to wait between attempts to find a new exposure, seconds.

        tmax    : (float) [if source == 's'; hidden]
           maximum time to wait between attempts to find a new exposure, seconds.

        pause   : (float) [hidden]
           seconds to pause between frames (defaults to 0)

        ccd     : (string)
           CCD(s) to plot, '0' for all, '1 3' to plot '1' and '3' only, etc.

        nx      : (int)
           number of panels across to display.

        bias    : (string)
           Name of bias frame to subtract, 'none' to ignore.

        msub    : (bool)
           subtract the median from each window before scaling for the
           image display or not. This happens after any bias subtraction.

        iset    : (string) [single character]
           determines how the intensities are determined. There are three
           options: 'a' for automatic simply scales from the minimum to the
           maximum value found on a per CCD basis. 'd' for direct just takes
           two numbers from the user. 'p' for percentile dtermines levels
           based upon percentiles determined from the entire CCD on a per CCD
           basis.

        ilo     : (float) [if iset='d']
           lower intensity level

        ihi     : (float) [if iset='d']
           upper intensity level

        plo     : (float) [if iset='p']
           lower percentile level

        phi     : (float) [if iset='p']
           upper percentile level

        profit  : (bool) [if plotting a single CCD only]
           carry out profile fits or not. If you say yes, then on the first
           plot, you will have the option to pick objects with a cursor. The
           program will then attempt to track these from frame to frame, and
           fit their profile. You may need to adjust 'first' to see anything.
           The parameters used for profile fits are hidden and you may want to
           invoke the command with 'PROMPT' the first time you try profile
           fitting.

        fdevice : (string) [if profit; hidden]
           plot device for profile fits, PGPLOT-style name.
           e.g. '/xs', '2/xs' etc. 

        fwidth  : (float) [hidden]
           fit plot width (inches). Set = 0 to let the program choose.

        fheight : (float) [hidden]
           fit plot height (inches). Set = 0 to let the program choose.
           BOTH fwidth AND fheight must be non-zero to have any effect

        method : (string) [if profit; hidden]
           this defines the profile fitting method, either a gaussian or a
           moffat profile. The latter is usually best.

        beta   : (float) [if profit and method == 'm'; hidden]
           default Moffat exponent

        fwhm   : (float) [if profit; hidden]
           default FWHM, unbinned pixels.

        fwhm_min : (float) [if profit; hidden]
           minimum FWHM to allow, unbinned pixels.

        shbox  : (float) [if profit; hidden]
           half width of box for searching for a star, unbinned pixels. The
           brightest target in a region +/- shbox around an intial position
           will be found. 'shbox' should be large enough to allow for likely
           changes in position from frame to frame, but try to keep it as
           small as you can to avoid jumping to different targets and to reduce
           the chances of interference by cosmic rays.

        smooth : (float) [if profit; hidden]
           FWHM for gaussian smoothing, binned pixels. The initial position
           for fitting is determined by finding the maximum flux in a smoothed
           version of the image in a box of width +/- shbox around the starter
           position. Typically should be comparable to the stellar width. Its main
           purpose is to combat cosmi rays which tend only to occupy a single pixel.

        splot  : (bool) [if profit; hidden]
           Controls whether an outline of the search box and a target number
           is plotted (in red) or not.

        fhbox  : (float) [if profit; hidden]
           half width of box for profile fit, unbinned pixels. The fit box is centred
           on the position located by the initial search. It should normally be
           > ~2x the expected FWHM.

        thresh : (float) [if profit; hidden]
           height threshold to accept a fit. If the height is below this value, the
           position will not be updated. This is to help in cloudy conditions.

        read   : (float) [if profit; hidden]
           readout noise, RMS ADU, for assigning uncertainties

        gain   : (float) [if profit; hidden]
           gain, ADU/count, for assigning uncertainties

        sigma  : (float) [if profit; hidden]
           sigma rejection threshold
    """

    if args is None:
        args = sys.argv[1:]

    # get the inputs
    with Cline('HIPERCAM_ENV', '.hipercam', 'rtplot', args) as cl:

        # register parameters
        cl.register('source', Cline.LOCAL, Cline.HIDE)
        cl.register('inst', Cline.GLOBAL, Cline.HIDE)
        cl.register('device', Cline.LOCAL, Cline.HIDE)
        cl.register('width', Cline.LOCAL, Cline.HIDE)
        cl.register('height', Cline.LOCAL, Cline.HIDE)
        cl.register('run', Cline.GLOBAL, Cline.PROMPT)
        cl.register('first', Cline.LOCAL, Cline.PROMPT)
        cl.register('twait', Cline.LOCAL, Cline.HIDE)
        cl.register('tmax', Cline.LOCAL, Cline.HIDE)
        cl.register('flist', Cline.LOCAL, Cline.PROMPT)
        cl.register('ccd', Cline.LOCAL, Cline.PROMPT)
        cl.register('pause', Cline.LOCAL, Cline.HIDE)
        cl.register('nx', Cline.LOCAL, Cline.PROMPT)
        cl.register('bias', Cline.GLOBAL, Cline.PROMPT)
        cl.register('msub', Cline.GLOBAL, Cline.PROMPT)
        cl.register('iset', Cline.GLOBAL, Cline.PROMPT)
        cl.register('ilo', Cline.GLOBAL, Cline.PROMPT)
        cl.register('ihi', Cline.GLOBAL, Cline.PROMPT)
        cl.register('plo', Cline.GLOBAL, Cline.PROMPT)
        cl.register('phi', Cline.LOCAL, Cline.PROMPT)
        cl.register('xlo', Cline.GLOBAL, Cline.PROMPT)
        cl.register('xhi', Cline.GLOBAL, Cline.PROMPT)
        cl.register('ylo', Cline.GLOBAL, Cline.PROMPT)
        cl.register('yhi', Cline.GLOBAL, Cline.PROMPT)
        cl.register('profit', Cline.LOCAL, Cline.PROMPT)
        cl.register('fdevice', Cline.LOCAL, Cline.HIDE)
        cl.register('fwidth', Cline.LOCAL, Cline.HIDE)
        cl.register('fheight', Cline.LOCAL, Cline.HIDE)
        cl.register('method', Cline.LOCAL, Cline.HIDE)
        cl.register('beta', Cline.LOCAL, Cline.HIDE)
        cl.register('fwhm', Cline.LOCAL, Cline.HIDE)
        cl.register('fwhm_min', Cline.LOCAL, Cline.HIDE)
        cl.register('shbox', Cline.LOCAL, Cline.HIDE)
        cl.register('smooth', Cline.LOCAL, Cline.HIDE)
        cl.register('splot', Cline.LOCAL, Cline.HIDE)
        cl.register('fhbox', Cline.LOCAL, Cline.HIDE)
        cl.register('thresh', Cline.LOCAL, Cline.HIDE)
        cl.register('read', Cline.LOCAL, Cline.HIDE)
        cl.register('gain', Cline.LOCAL, Cline.HIDE)
        cl.register('sigma', Cline.LOCAL, Cline.HIDE)

        # get inputs

        # image plot
        source = cl.get_value('source', 'data source [s(erver), l(ocal), f(ile list)]',
                              'l', lvals=('s','l','f'))

        if source == 's' or source == 'l':
            inst = cl.get_value('inst', 'instrument [h(ipercam), u(ltracam/spec)]',
                                'h', lvals=('h','u'))

        # plot device stuff
        device = cl.get_value('device', 'plot device', '1/xs')
        width = cl.get_value('width', 'plot width (inches)', 0.)
        height = cl.get_value('height', 'plot height (inches)', 0.)

        if source == 's' or source == 'l':
            run = cl.get_value('run', 'run name', 'run005')
            first = cl.get_value('first', 'first frame to plot', 1, 1)

            if source == 's':
                twait = cl.get_value('twait', 'time to wait for a new frame [secs]', 1., 0.)
                tmax = cl.get_value('tmax', 'maximum time to wait for a new frame [secs]', 10., 0.)

        else:
            # set inst = 'h' as only lists of HiPERCAM files are supported
            inst = 'h'
            run = cl.get_value('flist', 'file list', cline.Fname('files.lis',hcam.LIST))
            first = 1

        flist = source == 'f'
        server = source == 's'
        if inst == 'u':
            instrument = 'ULTRA'
        elif inst == 'h':
            instrument = 'HIPER'

        # define the panel grid. first get the labels and maximum dimensions
        ccdinf = hcam.get_ccd_pars(instrument, run, flist)

        try:
            nxdef = cl.get_default('nx')
        except:
            nxdef = 3

        if len(ccdinf) > 1:
            ccd = cl.get_value('ccd', 'CCD(s) to plot [0 for all]', '0')
            if ccd == '0':
                ccds = list(ccdinf.keys())
            else:
                ccds = ccd.split()

            if len(ccds) > 1:
                nxdef = min(len(ccds), nxdef)
                cl.set_default('nx', nxdef)
                nx = cl.get_value('nx', 'number of panels in X', 3, 1)
            else:
                nx = 1
        elif len(ccdinf) == 1:
            nx = 1
            ccds = list(ccdinf.keys())

        cl.set_default('pause', 0.)
        pause = cl.get_value('pause', 'time delay to add between frame plots [secs]', 0., 0.)

        # bias frame (if any)
        bias = cl.get_value(
            'bias', "bias frame ['none' to ignore]",
            cline.Fname('bias', hcam.HCAM), ignore='none'
        )
        if bias is not None:
            # read the bias frame
            bframe = hcam.MCCD.rfits(bias)

        # define the display intensities
        msub = cl.get_value('msub', 'subtract median from each window?', True)

        iset = cl.get_value(
            'iset', 'set intensity a(utomatically), d(irectly) or with p(ercentiles)?',
            'a', lvals=['a','A','d','D','p','P'])
        iset = iset.lower()

        plo, phi = 5, 95
        ilo, ihi = 0, 1000
        if iset == 'd':
            ilo = cl.get_value('ilo', 'lower intensity limit', 0.)
            ihi = cl.get_value('ihi', 'upper intensity limit', 1000.)
        elif iset == 'p':
            plo = cl.get_value('plo', 'lower intensity limit percentile', 5., 0., 100.)
            phi = cl.get_value('phi', 'upper intensity limit percentile', 95., 0., 100.)

        # region to plot
        nxmax, nymax = 0, 0
        for cnam in ccds:
            nxtot, nytot = ccdinf[cnam]
            nxmax = max(nxmax, nxtot)
            nymax = max(nymax, nytot)

        xlo = cl.get_value('xlo', 'left-hand X value', 0., 0., float(nxmax+1))
        xhi = cl.get_value('xhi', 'right-hand X value', float(nxmax), 0., float(nxmax+1))
        ylo = cl.get_value('ylo', 'lower Y value', 0., 0., float(nymax+1))
        yhi = cl.get_value('yhi', 'upper Y value', float(nymax), 0., float(nymax+1))

        # profile fitting if just one CCD chosen
        if len(ccds) == 1:
            # many parameters for profile fits, although most are not plotted
            # by default
            profit = cl.get_value('profit', 'do you want profile fits?', False)

            if profit:
                fdevice = cl.get_value('fdevice', 'plot device for fits', '2/xs')
                fwidth = cl.get_value('fwidth', 'fit plot width (inches)', 0.)
                fheight = cl.get_value('fheight', 'fit plot height (inches)', 0.)
                method = cl.get_value('method', 'fit method g(aussian) or m(offat)', 'm', lvals=['g','m'])
                if method == 'm':
                    cl.get_value('beta', 'initial exponent for Moffat fits', 5., 0.5)
                fwhm_min = cl.get_value('fwhm_min', 'minimum FWHM to allow [unbinned pixels]', 1.5, 0.01)
                fwhm = cl.get_value('fwhm', 'initial FWHM [unbinned pixels] for profile fits', 6., fwhm_min)
                shbox = cl.get_value(
                    'shbox', 'half width of box for initial location of target [unbinned pixels]', 11., 2.)
                smooth = cl.get_value(
                    'smooth', 'FWHM for smoothing for initial object detection [binned pixels]', 6.)
                splot = cl.get_value(
                    'splot', 'plot outline of search box?', True)
                fhbox = cl.get_value(
                    'fhbox', 'half width of box for profile fit [unbinned pixels]', 21., 3.)
                thresh = cl.get_value('thresh', 'peak height threshold to counts as OK', 50.)
                read = cl.get_value('read', 'readout noise, RMS ADU', 3.)
                gain = cl.get_value('gain', 'gain, ADU/e-', 1.)
                sigma = cl.get_value('sigma', 'readout noise, RMS ADU', 3.)

        else:
            profit = False


    ################################################################
    #
    # all the inputs have now been obtained. Get on with doing stuff


    # open image plot device
    imdev = hcam.pgp.Device(device)
    if width > 0 and height > 0:
        pgpap(width,height/width)

    # set up panels and axes
    nccd = len(ccds)
    ny = nccd // nx if nccd % nx == 0 else nccd // nx + 1

    # slice up viewport
    pgsubp(nx,ny)

    # plot axes, labels, titles
    for cnam in ccds:
        pgsci(hcam.pgp.Params['axis.ci'])
        pgsch(hcam.pgp.Params['axis.number.ch'])
        pgenv(xlo, xhi, ylo, yhi, 1, 0)
        pglab('X','Y','CCD {:s}'.format(cnam))


    # a couple of initialisations
    total_time = 0 # time waiting for new frame
    fpos = [] # list of target positions to fit

    # plot images
    with hcam.data_source(instrument, run, flist, server, first) as spool:

        # 'spool' is an iterable source of MCCDs
        for n, frame in enumerate(spool):

            # None objects are returned from failed server reads. This could
            # be because the file is still exposing, so we hang about.
            if server and frame is None:

                if tmax < total_time + twait:
                    print('Have waited for {:.1f} sec. cf tmax = {:.1f}; will wait no more'.format(total_time, tmax))
                    print('rtplot stopped.')
                    break

                print('Have waited for {:.1f} sec. cf tmax = {:.1f}; will wait another twait = {:.1f} sec.'.format(
                        total_time, tmax, twait
                        ))

                # pause
                time.sleep(twait)
                total_time += twait

                # have another go
                continue

            elif server:
                # reset the total time waited when we have a success
                total_time = 0

            # indicate progress
            if flist:
                print('File {:d}: '.format(n+1), end='')
            else:
                print('Frame {:d}: '.format(frame.head['NFRAME']), end='')

            # display the CCDs chosen
            message = ''
            for nc, cnam in enumerate(ccds):
                ccd = frame[cnam]

                # subtract the bias
                if bias is not None:
                    ccd -= bframe[cnam]

                if msub:
                    # subtract median from each window
                    for wind in ccd.values():
                        wind -= wind.median()

                # set to the correct panel and then plot CCD
                ix = (nc % nx) + 1
                iy = nc // nx + 1
                pgpanl(ix,iy)
                vmin, vmax = hcam.pgp.pccd(ccd,iset,plo,phi,ilo,ihi)

                # accumulate string of image scalings
                if nc:
                    message += ', ccd {:s}: {:.2f} to {:.2f}'.format(cnam,vmin,vmax)
                else:
                    message += 'ccd {:s}: {:.2f} to {:.2f}'.format(cnam,vmin,vmax)

            # end of CCD display loop
            print(message)

            if n == 0 and profit:
                # cursor selection of targets after first plot, if profit
                # accumulate list of starter positions

                print('Please select targets for profile fitting. You can select as many as you like.')
                x, y, reply = (xlo+xhi)/2, (ylo+yhi)/2, ''
                ntarg = 0
                pgsci(2)
                pgslw(2)
                while reply != 'Q':
                    print("Place cursor on fit target. Any key to register, 'q' to quit")
                    x, y, reply = pgcurs(x, y)
                    if reply == 'q':
                        break
                    else:
                        # check that the position is inside a window
                        wnam = ccd.inside(x, y, 2)

                        if wnam is not None:
                            # store the position, Windat label, target number, box size
                            ntarg += 1
                            fpos.append(Fpar(x,y,wnam,ntarg,shbox,fwhm))

                            # report information, overplot search box
                            print('Target {:d} selected at {:.1f},{:.1f} in window {:s}'.format(ntarg,x,y,wnam))
                            if splot:
                                fpos[-1].plot()

                if len(fpos):
                    print(len(fpos),'targets selected')
                    # if some targets were selected, open the fit plot device
                    fdev = hcam.pgp.Device(fdevice)
                    if fwidth > 0 and fheight > 0:
                        pgpap(fwidth,fheight/fwidth)

            # carry out fits. Nothing happens if fpos is empty
            for fpar in fpos:
                # switch to the image plot
                imdev.select()

                # plot search box
                if splot:
                    fpar.plot()

                # extract search box from the CCD
                swind = fpar.swind(ccd)

                # carry out initial search
                x,y,peak = swind.find(smooth, False)

                # now for a more refined fit. First extract fit Windat
                fwind = ccd[fpar.wnam].window(x-fhbox, x+fhbox, y-fhbox, y+fhbox)
                sky = np.percentile(fwind.data, 25)

                if method == 'g':
                    (sky, peak, x, y, fwhm), sigs, (fit, X, Y, weights) = \
                    fwind.fitGaussian(sky, peak-sky, x, y, fpar.fwhm, fwhm_min, read, gain, sigma)

                    if sigs is None:
                        print(' >> Targ {:d}: fit failed ***'.format(fpar.ntarg))
                        pgsci(2)
                    else:
                        esky, epeak, ex, ey, efwhm = sigs 
                        print(' >> Targ {:d}: x,y = {:.1f}({:.1f}),{:.1f}({:.1f}), FWHM = {:.2f}({:.2f}), peak = {:.1f}({:.1f}), sky = {:.1f}({:.1f})'.format(
                            fpar.ntarg,x,ex,y,ey,fwhm,efwhm,peak,epeak,sky,esky)
                        )

                        if peak > thresh:
                            # update search centre & fwhm for next frame
                            fpar.x, fpar.y, fpar.fwhm = x, y, fwhm

                            # plot values versus radial distance
                            R = np.sqrt((X-x)**2+(Y-y)**2)
                            fdev.select()
                            vmin, vmax = fwind.min(), fwind.max()
                            range = vmax-vmin
                            pgeras()
                            pgvstd()
                            pgswin( 0, R.max(), vmin-0.05*range, vmax+0.05*range)
                            pgsci(4)
                            pgbox('bcnst',0,0,'bcnst',0,0)
                            pgsci(1)
                            pgpt(R.flat, fwind.data.flat, 1)

                            # line fit
                            pgsci(3)
                            r = np.linspace(0,R.max(),200)
                            g = sky+peak*np.exp(-4*np.log(2)*(r/fwhm)**2)
                            pgline(r,g)

                            # back to the image to plot circle of radius FWHM
                            imdev.select()
                            pgsci(3)
                            pgcirc(x,y,fwhm)

                        else:
                            print('     *** below detection threshold; position & FWHM will not updated')
                            pgsci(2)
                else:
                    raise NotImplementedError('{:s} fitting method not implemented'.format(method))

                # plot location on image as a cross
                pgpt1(x, y, 5)

# From here is support code not visible outside

class Fpar:
    """Class for profile fits. Able to plot the search box around an x,y
    position and come up with a Windat representing that region."""

    def __init__(self, x, y, wnam, ntarg, shbox, fwhm):
        self.x = x
        self.y = y
        self.wnam = wnam
        self.ntarg = ntarg
        self.shbox = shbox
        self.fwhm = fwhm

    def region(self):
        return (self.x-self.shbox, self.x+self.shbox, self.y-self.shbox, self.y+self.shbox)

    def plot(self):
        """Plots search region"""
        pgsci(2)
        xlo, xhi, ylo, yhi = self.region()
        pgrect(xlo, xhi, ylo, yhi)
        pgptxt(xlo, ylo, 0, 1.3, str(self.ntarg))

    def swind(self, ccd):
        """Returns with search Windat"""
        xlo, xhi, ylo, yhi = self.region()
        return ccd[self.wnam].window(xlo, xhi, ylo, yhi)