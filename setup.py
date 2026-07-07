from setuptools import setup
setup(
    name = 'Ankikado',
    version = '0.1.0',
    description="Simple CLI flashcard program",
    author="Jake Choi",
    author_email="JChoi2527@gmail.com",
    python_requires='>=3.8',
    py_modules = ['main'],
    entry_points = {
        'console_scripts': [
            'ankikado = main:main'
        ]
    })