import logging
import subprocess

logger = logging.getLogger(__name__)

def extract_start_time(video_path):
    from datetime import datetime
    import pytz
    from tzlocal import get_localzone

    cmd = ["ffprobe",
           "-v", "quiet",
           "-print_format", "compact",
           "-show_entries", "format_tags=creation_time",
           video_path]
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=False)
    out = process.stdout.read().decode('UTF-8', 'ignore')
    creation_time_str = out.split("=")[1].split("Z")[0]
    creation_time = datetime.strptime(creation_time_str, "%Y-%m-%dT%H:%M:%S.%f")
    local_tz = get_localzone()
    try:
      localized_creation_time = local_tz.localize(creation_time)
    except:
      localized_creation_time = creation_time.replace(tzinfo = local_tz)
    utc_creation_time = localized_creation_time.astimezone(pytz.utc).replace(tzinfo=None)
    logger.debug(f"raw creation at {creation_time_str}")
    # Declare this to be in local time, then convert to UTC
    logger.debug(f"video starts at {utc_creation_time}")
    return utc_creation_time

def is_flipped(video_path):
    cmd = ["ffprobe",
           "-v", "quiet",
           "-of", "default=nw=1:nk=1",
           "-select_streams", "v:0",
           "-show_entries", "stream_tags=rotate",
           video_path]
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=False)
    out = process.stdout.read().decode('UTF-8', 'ignore')
    flipped = out == "180\n"
    return flipped

def timestamp_to_seconds(timestamp):
    from datetime import datetime
    return (timestamp - datetime.min).total_seconds()

def seconds_to_timestamp(seconds):
    from datetime import datetime, timedelta
    from pytz import utc
    return utc.localize(datetime.min + timedelta(seconds=seconds))

def km_to_mi(km):
    return km / 1.609

def c_to_f(c):
    return 9 / 5 * c + 32

def m_to_ft(m):
    return m * 3.2808399

def merge_dict(dct, merge_dct):
    """Recursive dict merge. Inspired by ``dict.update()``, instead of
    updating only top-level keys, dict_merge recurses down into dicts nested
    to an arbitrary depth, updating keys. The ``merge_dct`` is merged into
    ``dct``.

    Args:
        dct: dict onto which the merge is executed
        merge_dct: dct merged into dct

    Returns dct after the merge.
    """
    import collections

    for k, v in merge_dct.items():
        if (k in dct and isinstance(dct[k], dict)
                and isinstance(merge_dct[k], collections.Mapping)):
            merge_dict(dct[k], merge_dct[k])
        else:
            dct[k] = merge_dct[k]

    return dct
