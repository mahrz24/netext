import sys
import tty
import termios


def get_mouse_event():
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setcbreak(fd)
        while True:
            try:
                event = sys.stdin.read(1)
            except UnicodeDecodeError:
                continue
            if event == "\x1b":
                if sys.stdin.read(2) == "[M":
                    mouse_data = sys.stdin.read(3)
                    button = ord(mouse_data[0]) - 32
                    x = ord(mouse_data[1]) - 32
                    y = ord(mouse_data[2]) - 32
                    return button, x, y
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


def main():
    # Enable mouse tracking
    sys.stdout.write("\x1b[?1003h")
    sys.stdout.flush()

    print("Move the mouse and click once. Press Ctrl+C to exit.")

    covered_coords = []

    try:
        while True:
            button, x, y = get_mouse_event()
            if button & 0b11 == 0:  # Left mouse button pressed
                print(f"Mouse clicked at ({x}, {y})")
                break
            covered_coords.append((x, y))
            print(f"Mouse moved to ({x}, {y})")
    except KeyboardInterrupt:
        pass
    finally:
        # Disable mouse tracking
        sys.stdout.write("\x1b[?1003l")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
