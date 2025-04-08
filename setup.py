from setuptools import setup, find_packages

setup(
    name="comiccaster",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "feedgen>=0.9.0",
        "flask>=2.0.0",
        "requests>=2.25.0",
        "beautifulsoup4>=4.9.0",
        "pytz>=2021.1",
        "selenium>=4.0.0",
    ],
    extras_require={
        "dev": [
            "pytest>=6.0.0",
            "pytest-cov>=2.0.0",
            "pytest-flask>=1.2.0",
            "pytest-mock>=3.6.0",
        ],
    },
    python_requires=">=3.9",
) 