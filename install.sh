apt install python3-pip
pip3 uninstall ankikado
pip3 install --user -e .
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
