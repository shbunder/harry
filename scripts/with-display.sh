#!/bin/sh
# The image's entrypoint: a virtual display for the headed browser De Tijd is read with, then
# whatever the container was asked to run.
#
# Headed because De Tijd's edge refuses every headless browser, and virtual because the NUC has
# no screen. Started for the whole container rather than by the connector, the same way the
# image provides the fonts WeasyPrint renders with: a capability uses what the image has.
#
# `exec`, so Harry — not this shell — is the process `docker stop` signals. A shell left as
# PID 1 would swallow the signal, and every stop would wait out Docker's ten seconds and kill.

display_number="${DISPLAY#:}"

# A container restarted in place keeps /tmp, and a lock left by the last Xvfb makes the next one
# refuse to start. Nothing else in this container owns that display.
rm -f "/tmp/.X${display_number}-lock" "/tmp/.X11-unix/X${display_number}"

# In the background, and not fatal: without a display Harry still starts, and De Tijd's articles
# answer "the browser could not start" rather than taking the page down. Its complaints go to
# the container's log, which is the only place a display that failed can be seen.
Xvfb "$DISPLAY" -screen 0 1280x1024x24 -nolisten tcp >/dev/null &

# Up to five seconds for its socket, so the display exists before Harry does. Xvfb is ready in a
# fraction of that; if it never comes, Harry starts anyway, for the reason above.
waited=0
while [ ! -S "/tmp/.X11-unix/X${display_number}" ] && [ "$waited" -lt 50 ]; do
    sleep 0.1
    waited=$((waited + 1))
done
[ -S "/tmp/.X11-unix/X${display_number}" ] ||
    echo "with-display: Xvfb did not start on $DISPLAY, so De Tijd's articles will say the browser could not start" >&2

exec "$@"
