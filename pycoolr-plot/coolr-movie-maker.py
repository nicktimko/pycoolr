#!/usr/bin/env python

#
# generate a mp4 movie file from specified json file
#
# This tool and its config file are not flexible.
# I marked a customizable point as 'CUSTOMIZE'
#
#
#
#
# Kazutomo Yoshii <ky@anl.gov>
# 

import time, sys, os
import numpy as np

from genframes import *
from listrotate import *

monitor=True

import matplotlib
if not monitor:
    matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.animation as manimation
matplotlib.rcParams.update({'font.size': 12})
from clr_matplot_graphs import *


#
#

# XXX: add these to the option later
fps = 2
lrlen = 240  # this is for listrotate. the size of array
gxsec = lrlen * (1.0/fps) # graph x-axis sec
dpi = 120  # for writer.saving()
outputfn = 'm.mp4'


#

if len(sys.argv) < 3:
    print 'Usage: %s config data..' % sys.argv[0]
    sys.exit(1)

print 'Config: ', sys.argv[1]
print 'Data: ', ' '.join(sys.argv[2:])
    
with open(sys.argv[1]) as f:
    cfg = json.load(f)
frames = genframes(sys.argv[2:])
# XXX: single node target now
node = frames.getnodes()[0]
info = frames.info[node]
npkgs = info['npkgs']
ncpus = info['ncpus']

#
# 
frames.setfps(fps)
nframes = frames.nframes # % 60 # just for debugging
ts = frames.ts  # the start time

#
# data set
#
params = {}  # graph params XXX: extend for multinode
params['cfg'] = cfg
params['info'] = info
params['gxsec'] = gxsec
params['cur'] = ts  # this will be updated
params['pkgcolors'] = [ 'blue', 'green' ] # for now

# create frame data from time-series data
# frame data is a list with frameno as index
temp_data = frames.getlist(node,'temp')
freq_data = frames.getlist(node,'freq')
rapl_data = frames.getlist(node,'energy')


# listrotate is used for plotting function in matplotlib
# CUSTOMIZE when need more details
temp_lr = [listrotate2D(length=lrlen) for i in range(npkgs)]
freq_lr = [listrotate2D(length=lrlen) for i in range(npkgs)]
raplpkg_lr = [listrotate2D(length=lrlen) for i in range(npkgs)]
raplmem_lr = [listrotate2D(length=lrlen) for i in range(npkgs)]
raplpkgpwr_lr = [listrotate2D(length=lrlen) for i in range(npkgs)]
raplmempwr_lr = [listrotate2D(length=lrlen) for i in range(npkgs)]
rapltotpwr_lr = listrotate2D(length=lrlen)

# ad hoc
draw_xsbench = False
if len(sys.argv) == 4:
    draw_xsbench = True
    xsbench_data = frames.getlist(node,'xsbench')
    xsbench_lr = listrotate2D(length=lrlen)
#
#
#

FFMpegWriter = manimation.writers['ffmpeg']
writer = FFMpegWriter(fps=2, 
                      metadata=
                      dict(title='foobar', artist='COOLR', comment='no comment'),bitrate=8000)


fig = plt.figure( figsize=(15,10) )

if monitor:
    plt.ion()
    plt.show()

# define fig's layout
# CUSTOMIZE
col = 3
row = 2
idx = 1
#
ax = plt.subplot(row,col,idx)
pl_temp = plot_line_err(ax, params, temp_lr)
idx += 1
#
ax = plt.subplot(row,col,idx)
pl_freq = plot_line_err(ax, params, freq_lr, ptype = 'freq')
idx += 1
#
ax = plt.subplot(row,col,idx)
pl_rapl = plot_rapl(ax, params, raplpkg_lr, raplmem_lr)
idx += 1
#
draw_totpwr = False
if draw_totpwr:
    ax = plt.subplot(row,col,idx)
    pl_totpwr = plot_totpwr(ax, params, rapltotpwr_lr)
    idx += 1
#
if draw_xsbench :
    ax = plt.subplot(row,col,idx)
    pl_xsbench = plot_xsbench(ax, params, xsbench_lr)
    idx += 1

#
ax = plt.subplot(row,col,idx)
pl_info = plot_info(ax, params)
idx += 1


fig.tight_layout()

#
#
#

def draw_frames():
    for i in range(nframes):
        print 'frame:%04d/%04d / %5.1lf %%' % (i,nframes, (100.*i/nframes))
        #
        # CUSTOMIZE
        #
        tempd = temp_data[i]
        freqd = freq_data[i]
        rapld = rapl_data[i]

        if draw_xsbench:
            xsd = xsbench_data[i]
            if not xsd == None:
                t = xsd['time'] - ts
                params['cur'] = t # this is used in update()
                v = xsd['lps']
                xsbench_lr.add(t,v)
                pl_xsbench.update(params, xsbench_lr)
        #
        if not tempd == None:
            for p in range(npkgs):
                t = tempd['time'] - ts
                params['cur'] = t # this is used in update()
                v0 = tempd['p%d' % p]['mean']
                v1 = tempd['p%d' % p]['std']
                temp_lr[p].add(t,v0,v1)
            pl_temp.update(params, temp_lr)
        #
        if not freqd == None:
            for p in range(npkgs):
                t = freqd['time'] - ts
                params['cur'] = t
                v0 = freqd['p%d' % p]['mean']
                v1 = freqd['p%d' % p]['std']
                freq_lr[p].add(t,v0,v1)
            pl_freq.update(params, freq_lr, ptype = 'freq')
        #
        if not rapld == None:
            for p in range(npkgs):
                t = rapld['time'] - ts
                params['cur'] = t
                # need to calculate the rate
                v = rapld['energy']['p%d' % p]
                #vp = rapld['power']['p%d' % p]
                # vp may be off because 
                # instantaneous power at sampling 
                raplpkg_lr[p].add(t,v)
                v = rapld['energy']['p%d/dram' % p]
                #vp = rapld['power']['p%d/dram' % p]
                raplmem_lr[p].add(t,v)
                #
                # get the power from the rate of the change
                pwrpkg = raplpkg_lr[p].getlastr()
                if pwrpkg < 0.0:
                    pwrpkg += params["info"]["max_energy_uj"]["p%d" % pkgid]
                pwrpkg *= 1e-6
                pwrmem = raplmem_lr[p].getlastr()
                if pwrmem < 0.0:
                    pwrmem += params["info"]["max_energy_uj"]["p%d" % pkgid]
                pwrmem *= 1e-6
                vc = rapld['powercap']['p%d' % p]
                raplpkgpwr_lr[p].add(t,pwrpkg, vc)
                raplmempwr_lr[p].add(t,pwrmem)
                rapltotpwr_lr.add(t,pwrpkg + pwrmem)
            pl_rapl.update(params, raplpkgpwr_lr, raplmempwr_lr)
            if draw_totpwr:
                pl_totpwr.update(params, rapltotpwr_lr)
        #

        if monitor:
            plt.draw()
        else:
            writer.grab_frame()

print 'Generating %s with %d frames ...' % (outputfn, nframes)
st = time.time()
with writer.saving(fig, outputfn, dpi):
    draw_frames()
elapsed = time.time() - st

print 'elapsed: %3lf' % elapsed
print '%.3f sec/frame' %  (float(elapsed)/nframes)
print 'done'
