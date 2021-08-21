FROM debian:11

RUN echo deb http://deb.debian.org/debian bullseye non-free >> /etc/apt/sources.list
RUN echo deb http://deb.debian.org/debian bullseye-updates non-free >> /etc/apt/sources.list
RUN apt-get update
RUN apt-get install -y python3 python3-gst-1.0 python3-pip pkg-config libcairo2-dev libgstreamer-plugins-bad1.0-0 gstreamer1.0-plugins-base gstreamer1.0-plugins-good gstreamer1.0-plugins-ugly pulseaudio
RUN apt-get install -y fonts-ubuntu fonts-ubuntu-console fonts-dejavu-core
ADD requirements.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt
RUN apt-get install -y ffmpeg gstreamer1.0-libav
RUN mkdir /.local /.cache
RUN chmod a+rwx /.local /.cache
ENV PATH=/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
ENV PULSE_SERVER=/run/pulse/native
