# elf-size-analyze

elf-size-analyze is a Python tool that uses regular binutils programs (readelf, nm, c++filt) to extract information about symbols and sections from an ELF file and filters them. Information is presented in a tree based on paths to files where the symbols have been defined.

It's main usage is optimization of memory usage (FLASHH/RAM/etc.) by inspecting which modules/symbols in code contribute the most to final size. 
Main output format is an ASCII tree, but it supports other formats, e.g. JSON (for usage in other scripts), or HTML-based visualization (e.g. static HTML or Plotly graph).  

> This script was initially based on [size_report](https://github.com/zephyrproject-rtos/zephyr/blob/master/scripts/footprint/size_report) from Zephyr Project scripts (some old version), but it has been almost fully rewritten but the idea is the same. 

## Gallery 

<img width="1799" height="1097" alt="cmdline" src="https://github.com/user-attachments/assets/be65a738-efb1-4104-8276-481af264aca5" />

| Plotly treemap  | Plotly sunburst | HTML table |
| --- | --- | --- |
| <img width="1404" height="699" alt="treemap" src="https://github.com/user-attachments/assets/ae9eaa65-dd64-44b5-a737-2c7da00bccb6" /> | <img width="720" height="677" alt="sunburst" src="https://github.com/user-attachments/assets/17521780-cdb9-44c1-8547-fb734929374c" /> | <img width="1869" height="1178" alt="html" src="https://github.com/user-attachments/assets/e9cd0847-48c8-4503-b0f2-56ba59c312fb" /> |

## Requirements

* Python 3
* binutils: readelf, nm, c++filt (optional)

## Installation

For normal usage it's best to install from [PyPI](https://pypi.org/project/elf-size-analyze/):
```
pip install --upgrade elf-size-analyze
```

There are some optional dependencies not installed by default, e.g. to include support for Plotly graphs output use
```
pip insatll --upgrade elf-size-analyze[plotly]
```

For development it's recommended to install from sources in virtual environment in editable mode:
```
python -m venv venv
source ./venv/bin/activate
git clone https://github.com/jedrzejboczar/elf-size-analyze.git
pip install -e ./elf-size-analyze[dev,plotly]
```

## Usage 

Select the ELF file to be analyzed. To be able to extract path information about symbols from the ELF file, the program should be compiled with debug information (`gcc -g`).

If installed using `pip` then the package provides an entry point and you can just use the `elf-size-analyze` command.
Otherwise use `python -m elf_size_analyze` from the source directory.

Example usage (assumes that we're using `arm-none-eabi-gcc` toolchain):
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

For Plotly output (for big executables you might want to use `--plotly-max-depth`):
```
elf-size-analyze -t arm-none-eabi- -w 120 -HaF build/myapp --plotly --plotly-type treemap
```
