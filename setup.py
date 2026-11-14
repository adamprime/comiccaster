from setuptools import setup, find_packages

setup(
    name="comiccaster",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "feedgen>=0.9.0",
        "flask>=3.1.3",
        "requests>=2.32.0",
        "beautifulsoup4>=4.9.0",
        "pytz>=2021.1",
        "selenium>=4.0.0",
        "feedparser>=6.0.11",
        "python-dotenv>=1.0.1",
    ],
    extras_require={
        "dev": [
            "pytest>=6.0.0",
            "pytest-cov>=2.0.0",
            "pytest-flask>=1.2.0",
            "pytest-mock>=3.6.0",
        ],
    },
    # The floor of the locked soupsieve (constraints.txt). Dependabot appears to
    # resolve against the lowest Python allowed here: while this said 3.10, it
    # proposed no soupsieve 3/4 or python-dateutil 4, which both need 3.11+.
    python_requires=">=3.11.5",
) 