#!/bin/bash
# Auto-detect the first USB video capture device for mjpg_streamer.
# Skips Pi-internal codec/ISP devices (bcm2835) that also appear under /dev/video*.
# Called by r2d2-camera.service — install via setup_master.sh or update.sh.
#
# Resolution/FPS/quality are read from master/config/camera.env (written by the
# web dashboard Config tab). Defaults: 640x480 / 30fps / quality 80.

ENV_FILE="/home/artoo/r2d2/master/config/camera.env"
[ -f "$ENV_FILE" ] && source "$ENV_FILE"
CAMERA_RESOLUTION="${CAMERA_RESOLUTION:-640x480}"
CAMERA_FPS="${CAMERA_FPS:-30}"
CAMERA_QUALITY="${CAMERA_QUALITY:-80}"

CAM_DEV=""
for dev in /dev/video[0-9] /dev/video[0-9][0-9]; do
    [ -e "$dev" ] || continue
    devname=$(basename "$dev")
    syspath="/sys/class/video4linux/$devname/device"
    [ -L "$syspath" ] || continue
    realpath_dev=$(readlink -f "$syspath")
    echo "$realpath_dev" | grep -q "/usb" || continue
    v4l2-ctl -d "$dev" --all 2>/dev/null | grep -q "Video Capture" || continue
    CAM_DEV="$dev"
    break
done

if [ -z "$CAM_DEV" ]; then
    logger -t r2d2-camera "No USB video capture device found"
    exit 1
fi

logger -t r2d2-camera "Starting on $CAM_DEV"
logger -t r2d2-camera "Settings: ${CAMERA_RESOLUTION} @ ${CAMERA_FPS}fps q${CAMERA_QUALITY}"
exec /usr/local/bin/mjpg_streamer \
    -i "/usr/local/lib/mjpg-streamer/input_uvc.so -d $CAM_DEV -r $CAMERA_RESOLUTION -f $CAMERA_FPS -q $CAMERA_QUALITY" \
    -o "/usr/local/lib/mjpg-streamer/output_http.so -p 8080 -w /usr/local/share/mjpg-streamer/www"
