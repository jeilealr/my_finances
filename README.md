# Hydroland

The **HydroLand** application is an open‑source, component‑based model coupling framework for Land surface Hydrology simulations. It provides wrappers and workflow automation around the unmodified mHM ([mesoscale hydrologic model - mHM](https://mhm-ufz.org)) code developed at the Helmholtz Centre for Environmental Research ([UFZ](https://www.ufz.de)) in Germany. Hydroland was developed as part of the Climate Change Adaptation Digital Twin ([Destination Earth](https://destine.ecmwf.int/climate-change-adaptation-digital-twin-climate-dt/)) project to run global simulations at high spatial resolution and it is executed using [Autosubmit](https://pypi.org/project/autosubmit/) within the project. Users can access Hydroland software as an open-source Python package, which has been tailored specifically to plug into the broader Climate Digital Twin (Climate DT) workflow.

---

## Table of Contents

1. [Introduction](#introduction)
2. [Features](#features)
3. [Data Naming Conventions](#data-naming-conventions)
4. [Installation](#installation)
5. [HydroLand Model](#hydroland-model)
   - [1. Initialisation](#1-initialisation)
   - [2. Forcing Preparation](#2-forcing-preparation)
   - [3. mHM](#3-mhm)
   - [4. mRM](#4-mrm)
   - [5. Completion](#5-completion)
6. [Hydroland Indicators](#hydroland-indicators)
   - [1. Aridity Index](#1-aridity-index)
   - [2. Soil Moisture Indicators](#2-soil-moisture-indicators)
   - [3. TDigest Percentiles](#3-tdigest-percentiles)
   - [4. Discharge Events](#4-discharge-events)
   - [5. Discharge Indicators](#5-discharge-indicators)
7. [Command‑Line Interface](#command‑line-interface)
8. [Repository Structure](#repository-structure)
9. [Output Folder Layout](#output-folder-layout)
10. [DOI](#doi)
11. [License](#license)

---

## Introduction

The HydroLand application orchestrates unmodified mHM (mesoscale Hydrologic Model) and mRM (Multiscale Routing Model) binaries to perform global‑scale runs at high spatial (0.05° / 0.1°) and temporal (hourly/daily) resolutions. 

Key capabilities include:

- Seamless Model Coupling: integrates state and flux exchanges between mHM and mRM, supporting consistent restart and hot-start flows.
- Workflow Automation: single CLI entrypoint (hydroland) with subcommands for initialization, preprocessing, simulation runs, indicator computation, and cleanup.
- Flexible I/O Management: handles large NetCDF datasets with optional parallel I/O and spatial cropping.
- Extensible Indicator Suite: built-in routines for climate and hydrologic indicators (e.g., aridity index, discharge metrics).
- HPC Integration: compatible with Autosubmit for batch scheduling on LUMI, MareNostrum 5, and other HPC systems.
- Hydroland uses NetCDF restart files to store all state variables (soil moisture, snowpack, etc.) and supports seamless restarts and configurable flux/state outputs.

## Features

- Unified CLI: one hydroland command with global options (--version, --log_level, --verbose/--quiet, --log_file).
- Subcommand Structure: clear, consistent subcommands for each workflow step and indicator.
- Type-Safe Paths: uses pathlib.Path for robust file-system handling.
- Parallel Processing: supports multiprocessing and Dask for large-scale data tasks.
- Configurable Outputs: choose desired variables, temporal frequency, and spatial domain via simple flags.
- mHM and mRM output files follow CF naming conventions.
- **HPC ready**: Proven on LUMI and MareNostrum 5 via [Autosubmit](https://pypi.org/project/autosubmit/).

## Data Naming Conventions

When reading input forcings, HydroLand strictly follows the [OPA (One_Pass package)](https://earth.bsc.es/gitlab/digital-twins/de_340-2/one_pass) file‐naming conventions defined by the Climate DT project.  This ensures seamless downstream interoperability.

The name of the output files in OPA does follow a convention which conforms an interface with applications:
```bash
<time>to<time><variable>timestep<timestep><frequency><stat>.nc
<time><variable>timestep<timestep><frequency><stat>.nc
```

In which the elements between angular braces are the different values. `<time>` is always in one of the following formats:
```bash
- **`<time>`** can be:
  - `YYYY`  
  - `YYYY_MM`  
  - `YYYY_MM_DD`  
  - `YYYY_MM_DD_THH`  
  - `YYYY_MM_DD_THH_00`  
- **`<variable>`** is the short name (e.g. `2t` or `avg_tprate`).  
- **`<timestep>`** is the base interval in minutes (e.g. `60`).  
- **`<frequency>`** is the aggregation frequency (`daily`, `hourly`, etc.).  
- **`<stat>`** is the statistic (e.g. `mean`, `sum`).
```

Alternatively, the OPA can provide raw data, i.e. data passed on directly without any aggregation, as provided by the [GSV Interface](https://earth.bsc.es/gitlab/digital-twins/de_340-2/gsv_interface). This is also known as a raw statistic and it is requested by passing “raw” to the OPA request. In that case, the name convention of the output files are:

```bash
<time>_to_<time>_<variable>_raw_data.nc
<time>_<variable>_raw_data.nc
```
These output files are then read and interpreted by applications like HydroLand downstream of the OPA. In our case, HydroLand reads only hourly (raw) data and daily data from OPA.


## Installation

```bash
pip install git+https://github.com/DestinE-Climate-DT/hydroland.git
```

You will also need:

- Python 3.9+ with dependencies listed in `pyproject.toml` (e.g., `xarray`, `numpy`, `pytest`).
- mHM and mRM executables on your `$PATH`, or specify custom paths via CLI options.
- CDO version 2.4.4 or higher.

For compilation of binaries downloas mHM & mRM repositories and source any file of preference in `CI-scripts/`, for more information and guidance see documentation:
- [mHM model](https://mhm.pages.ufz.de/mhm/stable/)

mRM is part of mHM, but a new branch was detached and modified from mHM to executed global routing at a apropiate speed, the repositories are availabe at:
- [mHM](https://git.ufz.de/mhm/mhm)
- [mRM](https://git.ufz.de/destine_cats/mrm)

## HydroLand Model

Below is a minimal Hydroland model execution using the unified `hydroland` CLI.

### 1. Initialisation:
Creates all necessary directories and control files for both mHM and mRM.
```bash
hydroland initialisation \
  --ini-date          20200201 \
  --end-date          20200202 \
  --previous_date     20201231 \
  --stat-freq         daily \
  --resolution        0.1 \
  --init-files        /path/to/init_files \
  --app-outpath       /path/to/out_files \
  --current-mhm-dir   /path/to/mhm_dir \
  --forcings-dir      /path/to/forcings \
  --current-mrm-dir   /path/to/mrm_dir \
  --mhm-restart-dir   /path/to/mhm_restart \
  --mrm-restart-dir   /path/to/mrm_restart \
  --hydroland-opa     /path/to/opa \
  --bias-adjustment
```

### 2. Forcing Preparation:
Ensures that mHM and mRM receive correctly formatted NetCDF forcings.
```bash
hydroland preprocess \
  --ini_date          20210101 \
  --end_date          20210110 \
  --stat-freq         daily \
  --temp-var          2t
  --pre               avg_tprate    \
  --forcings-dir      /path/to/forcings \
  --lon-number        3600 \
  --hydroland-opa     /path/to/opa
```

### 3. mHM:
Executes mHM.
```bash
hydroland mhm \
  --ini_date          20210101 \
  --end_date          20210110 \
  --next-date         20210111 \
  --current-mhm-dir   /path/to/run_mhm \
  --forcings-dir      /path/to/forcings \
  --mhm-log-dir       /path/to/logs_mhm \
  --mhm-fluxes-dir    /path/to/fluxes_mhm \
  --mhm-restart-dir   /path/to/mhm_restart \
  --hydroland-opa     /path/to/opa \
  --pre               avg_tprate    \
  --stat-freq         daily \
  --mhm-out-file      mHM_fluxes.nc \
  --executable-mhm    mhm
```

### 4. mRM:
Executes mRM.
```bash
hydroland mrm \
  --current_mhm_dir   /path/to/run_mhm \
  --current_mrm_dir   /path/to/run_mrm \
  --mrm_restart_dir   /path/to/mrm_restart \
  --mrm_log_dir       /path/to/logs_mrm \
  --ini_date          20210101 \
  --end_date          20210110 \
  --next_date         20210111 \
  --stat_freq         daily \
  --init_files        /path/to/init \
  --forcings_dir      /path/to/forcings \
  --mhm_fluxes_dir    /path/to/fluxes_mhm \
  --mrm_fluxes_dir    /path/to/fluxes_mrm \
  --mhm_out_file      mHM_fluxes.nc \
  --mrm_out_file      mRM_fluxes.nc \
  --hydroland_opa     /path/to/opa \
  --pre               tp \
  --resolution        0.1 \
  --executable-mrm    mrm
```

### 5. Completion:
Removes intermediate files and any other data no longer needed.
```bash
hydroland completion \
  --previous-date      2021-01-10 \
  --forcings-dir       /path/to/forcings \
  --mhm-restart-dir    /path/to/mhm_restart \
  --mhm-log-dir        /path/to/logs_mhm \
  --mrm-restart-dir    /path/to/mrm_restart \
  --mrm-log-dir        /path/to/logs_mrm \
  --hydroland-opa      /path/to/opa \
  --delete-files \
  --bias-adjustment \
  --apply-indicators
```

## HydroLand Indicators

Hydroland provides a comprehensive set of hydrological indicators that can be computed directly from HydroLand model outputs and/or observational data. Each indicator is implemented as a dedicated CLI subcommand, offering spatial cropping, parallel execution, and flexible output formats:

Below is a minimal Hydroland indicators execution using the unified `hydroland` CLI.

### 1. Aridity Index:
Calculate the aridity index from actual evapotranspiration and precipitation.
```bash 
# first process months in parallel for $year 
hydroland aridity_index_indicators \
  --pre-dir       /path/to/pre \
  --aet-dir       /path/to/mhm \
  --output-dir       /path/to/out \
  --min-lon       -12 \
  --max-lon       45 \
  --min-lat       34 \
  --max-lat       72 \
  --year          1990 \
  --use-mfdataset

# when all years are executed
hydroland aridity_index_indicators \
  --output-dir       /path/to/out \
  --use-mfdataset \
  --merge-files
```

### 2. Soil Moisture Indicators:
Calculate soil moisture indicators from given file(s)
```bash 
# first to create monthly files
hydroland soil_moisture_indicators \
    --ref-input-dir   /path/to/indicators_data/mhm \
    --scen-input-dir  /path/to/indicators_data/mhm \
    --output-dir     /path/to/out \
    --sm-data-timestep monthly \
    --create-monthly-files \
    --year 1990 \
    --min-lon -12 \
    --max-lon 45 \
    --min-lat 34 \
    --max-lat 72

# merge all files into one final output
# here ref-input-dir and scen-input-dir change, the new path
# was created when --create-monthly-files was set:
# ${out-path}$/mean_dir/*ref_data*.nc or
# ${out-path}$/mean_dir/*scen_data*.nc
hydroland soil_moisture_indicators \
    --ref-input-dir   "/path/to/out/mean_dir/*ref_data*.nc" \
    --scen-input-dir  "/path/to/out/mean_dir/*scen_data*.nc" \
    --output-dir     /path/to/out
```

### 3. TDigest Percentiles:
Calculates the discharge quantile pkl and NetCDF files using the parsed arguments.
```bash
# first to calculated pkl files
hydroland tdigest_percentiles \
  --input-path   /path/to/mrm \
  --output-path  /path/to/pkl_files \
  --percetiles   "95 5" \
  --year         1990 \
  --min-lon -12 \
  --max-lon 45 \
  --min-lat 34 \
  --max-lat 72

# then to convert pkl files to nc files
hydroland tdigest_percentiles \
  --input-dir /path/to/pkl_files \
  --output-dir /path/to/nc_files \
  --percentiles "95 99 5 1" \
  --pkl-to-nc
```

### 4. Discharge Events:
Creates a file with discharge above or bellow a given percentile.
```bash
#after running `hydroland tdigest_percentiles`
hydroland discharge_events \
    --input-dir /path/to/mrm \
    --output-dir /path/to/events \
    --percentiles "95 99 5 1" \
    --percentiles-dir /path/to/nc_files \
    --match_date 1990 \
    --min-lon -12 \
    --max-lon 45 \
    --min-lat 34 \
    --max-lat 72
```

### 5. Discharge Indicators:
Calculate flood/drought indicators: duration, frequency, and intensity.
```bash
# first, after running hydroland discharge_events
hydroland discharge_indicators \
    --events-dir /path/to/events \
    --output-dir /path/to/indicators \
    --percentiles "95 99 5 1" \
    --match_date 1990 \
    --percentiles-dir /path/to/nc_files \
    --use-mfdataset

# after calculating indicators for several dates (--match_date)
time hydroland discharge_indicators \
    --output-dir /path/to/indicators \
    --merge-files \
    --percentiles "95 99 5 1"
```


## Command‑Line Interface

When typing `hydroland -h`, displays global help and version information with a single entrypoint:
```bash
usage: HydroLand [-h] [-V] [--log_level {DEBUG,INFO,WARNING,ERROR,CRITICAL}] [--verbose] [--quiet] \
                 [--log_file LOG_FILE] [--log_file_level {DEBUG,INFO,WARNING,ERROR,CRITICAL}] [--no_console_output] \
                 ...

Command line interface for HydroLand.

options:
  -h, --help            show this help message and exit
  -V, --version         Display version information.
  --log_level {DEBUG,INFO,WARNING,ERROR,CRITICAL}
                        Set the log level explicitly. (default: None)
  --verbose, -v         Increase verbosity (default: 0)
  --quiet, -q           Reduce verbosity; can be repeated (default: 0)
  --log_file LOG_FILE   Generate a log file. (default: None)
  --log_file_level {DEBUG,INFO,WARNING,ERROR,CRITICAL}
                        Set log level for the log file. Defaults to console level. (default: None)
  --no_console_output   Prohibit console output. (default: False)

Available Tools:
  All tools are provided as sub-commands. Please refer to each subcommand’s `--help`.

  completion              Removes intermediate files and any other data no longer needed.
  initialisation          Creates all necessary directories and control files for both mHM and mRM.
  mhm                     Executes mHM.
  mrm                     Executes mRM.
  preprocess              Ensures that mHM and mRM receive correctly formatted NetCDF forcings.
  aridity_index_indicators
                          Calculate the aridity index from actual evapotranspiration and precipitation.
  discharge_events        Creates a file with discharge above or below a given percentile.
  discharge_indicators    Calculate flood/drought indicators: duration, frequency, and intensity.
  soil_moisture_indicators
                          Calculate soil moisture indicators from given file(s).
  tdigest_percentiles     Calculates t-Digest quantiles and NetCDF outputs based on parsed arguments.
```

## Repository Structure

```text
.
├── AUTORS.md
├── CHANGELOG.md
├── COPYING
├── COPYING.LESSER
├── LICENSE.md
├── pyproject.toml
├── README.md
├── src
│   └── hydroland
│       ├── __init__.py
│       ├── _cli/
│       ├── common/
│       ├── dask/
│       ├── indicators/
│       └── model/
└── tests/
```

---

## Output Folder Layout

```text
hydroland/
├── forcings/
├── mhm/
│   ├── current_run/
│   ├── fluxes/
│   ├── log_files/
│   └── restart_files/
└── mrm/
    ├── current_run/
    ├── fluxes/
    ├── log_files/
    └── restart_files/
```

---

## DOI

- Latest version

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.15584779.svg)](https://doi.org/10.5281/zenodo.15584779)

---
## License

Hydroland is distributed under the **LGPL‑3.0** License. © 2025–2030 Hydroland developers, Helmholtz‑Zentrum für Umweltforschung GmbH – UFZ.
