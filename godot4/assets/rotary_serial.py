"""Forward the rotary encoder's raw serial bytes to Godot on Linux."""

import argparse
from contextlib import suppress
import os
import select
import sys
import termios


def stream_port(port: str) -> None:
    serial = os.open(port, os.O_RDONLY | os.O_NOCTTY | os.O_NONBLOCK)
    previous = None
    try:
        previous = termios.tcgetattr(serial)
        settings = previous.copy()
        settings[6] = previous[6].copy()
        settings[0] = 0  # Raw input without software flow control.
        settings[1] = 0
        settings[2] &= ~(termios.PARENB | termios.CSTOPB | termios.CSIZE | termios.CRTSCTS)
        settings[2] |= termios.CS8 | termios.CLOCAL | termios.CREAD
        settings[3] = 0  # No canonical input, echo, or terminal signals.
        settings[4] = settings[5] = termios.B115200
        settings[6][termios.VMIN] = 1
        settings[6][termios.VTIME] = 0
        termios.tcsetattr(serial, termios.TCSAFLUSH, settings)

        print("READY", file=sys.stderr, flush=True)
        parent = sys.stdin.fileno()
        while True:
            readable, _, _ = select.select([parent, serial], [], [])
            if parent in readable and not os.read(parent, 4096):
                return
            if serial in readable:
                try:
                    data = os.read(serial, 4096)
                except BlockingIOError:
                    continue
                if not data:
                    raise OSError("serial device disconnected")
                os.write(sys.stdout.fileno(), data)
    finally:
        if previous is not None:
            # A disconnected device can no longer accept termios settings.
            with suppress(termios.error):
                termios.tcsetattr(serial, termios.TCSANOW, previous)
        os.close(serial)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("port")
    port = parser.parse_args().port
    try:
        stream_port(port)
    except BrokenPipeError:
        return 0
    except (OSError, termios.error) as error:
        print(f"{port}: {error}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
