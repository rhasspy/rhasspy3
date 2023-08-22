#!/usr/bin/env python3
from pathlib import Path

import setuptools
from setuptools import setup

this_dir = Path(__file__).parent
module_dir = this_dir / "wyoming_openwakeword"

requirements = []
requirements_path = this_dir / "requirements.txt"
if requirements_path.is_file():
    with open(requirements_path, "r", encoding="utf-8") as requirements_file:
        requirements = requirements_file.read().splitlines()

models_dir = module_dir / "models"
model_files = [str(f.relative_to(module_dir)) for f in models_dir.glob("*.tflite")]

# -----------------------------------------------------------------------------

setup(
    name="wyoming_openwakeword",
    version="1.3.0",
    description="Wyoming server for openWakeWord",
    url="http://github.com/rhasspy/rhasspy3",
    author="Michael Hansen",
    author_email="mike@rhasspy.org",
    packages=setuptools.find_packages(),
    package_data={"wyoming_openwakeword": model_files},
    install_requires=requirements,
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: Apache Software License",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
    ],
    keywords="rhasspy wyoming openwakeword",
)
