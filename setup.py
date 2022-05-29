from setuptools import setup

requirements = ['click', 'PyQt5', 'PyYAML', 'SQLAlchemy']

setup(
    name='tagcounter',
    version='1.0',
    author='Andrey Kolotushkin',
    packages=['tagcounter'],
    description='The program to count number of html tags on a webpage',
    package_data={'': ['tagcounter_data/synonyms.yml']},
    install_requires=requirements,
    test_suite='tests',
    entry_points={'console_scripts': ['tagcounter = tagcounter.tagcounter:run']},
)

