from setuptools import setup, find_packages
setup(
    name = 'Ankikado',
    version = '0.1.0',
    description="Simple CLI flashcard program",
    author="Jake Choi",
    author_email="JChoi2527@gmail.com",
    packages = find_packages(),
    entry_points = {
        'console_scripts': [
            'ankikado = src.main:main'
        ]
    })