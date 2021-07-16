def extract_start_time(video_path):
    import subprocess
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
    localized_creation_time = local_tz.localize(creation_time)
    utc_creation_time = localized_creation_time.astimezone(pytz.utc).replace(tzinfo=None)
    print(f"raw creation at {creation_time_str}")
    # Declare this to be in local time, then convert to UTC
    print(f"video starts at {utc_creation_time}")
    return utc_creation_time

def timestamp_to_seconds(timestamp):
    from datetime import datetime
    return (timestamp - datetime.min).total_seconds()

def km_to_mi(km):
    return km / 1.609

def c_to_f(c):
    return 9 / 5 * c + 32

def m_to_ft(m):
    return m * 3.2808399
