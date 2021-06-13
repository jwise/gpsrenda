# gpsrenda: simple open-source GPS statistics video overlay renderer

`gpsrenda` is a video overlay renderer that takes statistics from a FIT
file, and renders gauges on top of video captured by a GoPro.  It uses Cairo
to do all its graphics rendering, and Gstreamer as a video backend.  It takes
its configuration programmatically, and is designed to be (relatively)
simple, hackable, and extensible (at least, if you think that using Python
as a configuration language without having a GUI at all is simple).  It
competes with DashWare and Garmin VIRB (with the hope that it's easier to
automate than DashWare, and more flexible than VIRB).

I have it tested with a GoPro Hero 8 Black, and a Wahoo ELEMNT BOLT.  To get
the best use of it, hit the start button on the GPS *with the GoPro
running*, and then use the GPS start sound in the video to synchronize the
time offset between the GPS data and the video.

I've successfully fed the output to `kdenlive`, which is extremely slow at
rendering... I'll try other non-linear video editors next.

## Setup

You need a handful of Python packages installed, including `cairo`,
`fitparse`, and the PyGObject bridge for Gst (on my Ubuntu machine, the
package is called `python3-gst-1.0`).  For a usage example, check out
`sample.py`, which generates output that looks as below:

![an example image generated with gpsrenda](sample.jpg)

