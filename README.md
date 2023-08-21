# Elf size report

This script is based on [size_report](https://github.com/zephyrproject-rtos/zephyr/blob/master/scripts/footprint/size_report) from Zephyr Project scripts. It has been almost fully rewritten but the idea is the same. It uses binutils programs (readelf, nm, c++filt) to extract information about symbols and sections from an ELF file and filters them. Information is presented in a tree based on paths to files where the symbols have been defined.

![Example output](https://raw.githubusercontent.com/jedrzejboczar/elf-size-analyze/master/example.jpg)

## Requirements

* Python 3
* binutils: readelf, nm, c++filt (optional)

## Installation

For normal usage it's best to install from [PyPI](https://pypi.org/project/elf-size-analyze/):
```
pip install elf-size-analyze
```

For development it's recommended to install from sources in virtual environment in editable mode:
```
python -m venv venv
source ./venv/bin/activate
git clone https://github.com/jedrzejboczar/elf-size-analyze.git
pip install -e ./elf-size-analyze
```

## Usage 

Select the ELF file to be analyzed. To be able to extract path information about symbols from the ELF file, the program should be compiled with debug information (`gcc -g`).

If installed using `pip` then the package provides an entry point and you can just use the `elf-size-analyze` command.
Otherwise use `python -m elf_size_analyze` from the source directory.

Example usage:
```
elf-size-analyze -t arm-none-eabi- -w 120 -HaF build/myapp
```

For more options see help:
```
elf-size-analyze -h
```

For HTML output:
```
elf-size-analyze -t arm-none-eabi- -w 120 -HaF build/myapp -W > /tmp/index.html
firefox /tmp/index.html  # or other browser / xdg-open
```
