# Color some text using ANSI escape codes
print("\033[1;31mHello World\033[0m")
input()
# Clear the screen
print("\033[2J")
# Move cursor to the top left of the screen and print blue hello world
print("\033[H\033[0;34mHello World\033[0m")
input()
