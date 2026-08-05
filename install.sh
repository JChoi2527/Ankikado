#!/bin/bash
set -e

# Do NOT run this whole script with sudo. As root, pip installs the ankikado
# command into root's home (and leaves root-owned build files that block future
# installs), so the command won't be available to you. Only the apt step needs
# root, and it elevates itself below.
if [ "$(id -u)" -eq 0 ]; then
    echo "Please run ./install.sh WITHOUT sudo. You'll be prompted for your password only when it's needed."
    exit 1
fi

# Installing python3-pip requires root; this is the only step that does.
sudo apt install -y python3-pip

# These run as your normal user so the ankikado command lands in your home.
pip3 uninstall -y ankikado || true
pip3 install --user -e .
PATH_LINE='export PATH="$HOME/.local/bin:$PATH"'
if ! grep -qxF "$PATH_LINE" ~/.bashrc; then
    echo "$PATH_LINE" >> ~/.bashrc
fi

# This script runs in its own shell, so it cannot change the PATH of the
# terminal you launched it from. Reload your shell to pick up the new PATH.
echo ""
echo "Installation complete!"
echo "Run 'source ~/.bashrc' (or open a new terminal) to start using the ankikado command."