# My Finances



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


## Installation

```bash
pip install git+https://github.com/DestinE-Climate-DT/hydroland.git
```

You will also need:

- Python 3.9+ with dependencies listed in `pyproject.toml` (e.g., `xarray`, `numpy`, `pytest`).
- mHM and mRM executables on your `$PATH`, or specify custom paths via CLI options.
- CDO version 2.4.4 or higher.



## DOI

- Latest version

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.15584779.svg)](https://doi.org/10.5281/zenodo.15584779)

---
## License

 is distributed under the **LGPL‑3.0** License. © 