#!/bin/bash
WHOAMI=$(id -un)
NAME=gpsrenda-$WHOAMI

if docker container inspect $NAME >/dev/null 2>&1; then
	echo "container $NAME already exists; rm it first before recreating"
	echo "launch it with:"
	echo "  $ docker start -ia $NAME"
	exit 1
fi

RENDAPATH=$(realpath $(dirname $0))
set -x
docker create \
	-v /run/user/$UID/pulse/native:/run/pulse/native \
	-v /tmp/.X11-unix:/tmp/.X11-unix \
	-e DISPLAY=$DISPLAY \
	-v $RENDAPATH:/gpsrenda \
	-v /etc/localtime:/etc/localtime \
	-v /etc/timezone:/etc/timezone \
	-u $UID \
	-it \
	"$@" \
	--name $NAME \
	gpsrenda
docker start $NAME >/dev/null
docker exec -u 0 $NAME useradd -u $UID -d / $WHOAMI
docker exec $NAME pip3 install -e gpsrenda
docker stop -t 0 $NAME >/dev/null
set +x

echo
echo
echo
echo "to launch shell in gpsrenda environment:"
echo "   $ docker start -ia $NAME"
