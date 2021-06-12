import datetime
import glob
import os

import gpsrenda
from gpsrenda.widgets import *

# start
#FILE='/home/joshua/gopro/20210605-copperopolis/GX010026.MP4'
#SEEKTIME=140

# robin
#FILE='/home/joshua/gopro/20210605-copperopolis/GX010037.MP4'
#SEEKTIME=0

# descent
#FILE='/home/joshua/gopro/20210605-copperopolis/GX010031.MP4'
#SEEKTIME=0

# VERY SHORT clip
FILE='/home/joshua/gopro/20210605-copperopolis/GX010035.MP4'
SEEKTIME=0

fit = gpsrenda.fit.FitByTime('/home/joshua/gopro/20210605-copperopolis/Copperopolis_Road_Race_off_the_back_7_19_but_at_least_I_didn_t_DNF_.fit')
INGLOB='/home/joshua/gopro/20210605-copperopolis/GX*.MP4'
OUTDIR='/home/joshua/gopro/20210605-copperopolis/output/'
TIMEFUDGE=datetime.timedelta(hours = 7, seconds = -36.58)
RECORD_DATE=datetime.datetime(year = 2021, month = 6, day = 5)

cadence_gauge    = GaugeHorizontal(30, 1080 - 30 - 65 * 1,
                                   label = '{val:.0f}', caption = 'rpm',
                                   data_range = [
                                       (75, (1.0, 0, 0)),
                                       (90, (0.0, 0.6, 0.0)),
                                       (100, (0.0, 0.6, 0.0)),
                                       (120, (1.0, 0.0, 0.0))
                                   ])
heart_rate_gauge = GaugeHorizontal(30, 1080 - 30 - 65 * 2,
                                   label = '{val:.0f}', caption = 'bpm',
                                   data_range = [
                                       (120, (0, 0.6, 0)),
                                       (150, (0.2, 0.6, 0.0)),
                                       (180, (0.8, 0.0, 0.0))
                                   ])
speed_gauge      = GaugeHorizontal(30, 1080 - 30 - 65 * 3,
                                   label = '{val:.1f}', caption = 'mph',
                                   data_range = [
                                       (8, (0.6, 0, 0)),
                                       (15, (0.0, 0.6, 0.0)),
                                       (30, (1.0, 0.0, 0.0))
                                   ])
temp_gauge       = GaugeVertical  (1920 - 120, 30,
                                   data_range = [
                                       (60, (0.6, 0.6, 0.0)),
                                       (80, (0.6, 0.3, 0)),
                                       (100, (0.8, 0.0, 0.0))
                                   ])
dist_total_mi    = gpsrenda.km_to_mi(fit.fields['distance'][-1][1])
dist_gauge       = GaugeHorizontal(30, 30, w = 1920 - 120 - 30 - 30,
                                   label = "{val:.1f}", caption = f" / {dist_total_mi:.1f} miles",
                                   dummy_label = "99.9", dummy_caption = None,
                                   data_range = [(0, (0.8, 0.7, 0.7)), (dist_total_mi, (0.7, 0.8, 0.7))])
map              = GaugeMap(1920 - 30 - 400, 1080 - 30 - 65 * 3, h = 65 * 3)
elevmap          = GaugeElevationMap(1920 - 30 - 400 - 30 - 400, 1080 - 30 - 65 * 3, h = 65 * 3)
map.prerender(fit.fields['position_lat'], fit.fields['position_long'])
elevmap.prerender(fit.fields['distance'], fit.fields['altitude'])

cadence = fit.interpolator('cadence', flatten_zeroes = datetime.timedelta(seconds = 2.0))
heart_rate = fit.interpolator('heart_rate')
speed_kph = fit.interpolator('speed')
dist_km = fit.interpolator('distance')
temp_c = fit.interpolator('temperature')
latitude = fit.interpolator('position_lat')
longitude = fit.interpolator('position_long')
altitude = fit.interpolator('altitude')
grade = fit.interpolator('grade')

def paint(ctx, w, h, tm):
    cadence_gauge.render(ctx, cadence.value(tm))
    heart_rate_gauge.render(ctx, heart_rate.value(tm))
    speed_gauge.render(ctx, speed_kph.value(tm, transform = gpsrenda.km_to_mi))
    temp_gauge.render(ctx, temp_c.value(tm, transform = gpsrenda.c_to_f))
    dist_gauge.render(ctx, dist_km.value(tm, transform = gpsrenda.km_to_mi))
    map.render(ctx, latitude.value(tm), longitude.value(tm))
    elevmap.render(ctx, dist_km.value(tm), altitude.value(tm), grade.value(tm))

try:
    os.mkdir(OUTDIR)
except FileExistsError:
    pass
for input in glob.glob(INGLOB):
    output = f"{OUTDIR}/{os.path.basename(input)}"
    print(f"rendering {input} -> {output}")
    gpsrenda.video.RenderLoop(gpsrenda.video.source.VideoSourceGoPro(input, date = RECORD_DATE, timefudge = TIMEFUDGE), painter = paint).encode(output)
#RenderLoop(VideoSourceGoPro(FILE, timefudge = datetime.timedelta(hours = 7, seconds = -TIMEFUDGE)), painter = paint).preview()
