# AI Agent Instructions for my_finances

This document provides key context for AI agents working with the my_finances codebase. Focus on these project-specific patterns and conventions.

## Project Overview

my_finances is a Python CLI tool for extracting and processing financial transaction data from various bank statement PDFs. The core functionality includes:

- PDF data extraction with bank-specific parsers
- Command line interface for all operations
- Standardized output formats (CSV, Excel, JSON, Parquet)
- Configurable logging system

## Key Architecture Patterns

### Command Line Interface Structure
- Single entrypoint via `my_finances._cli._main`
- Each bank extractor has a dedicated CLI module in `_cli/` (e.g., `_bancolombia.py`)
- Standardized argument handling pattern:
  ```python
  def add_args(parser: argparse.ArgumentParser) -> None:
      # Add subcommand-specific arguments
  
  def run(args: argparse.Namespace):
      # Execute subcommand logic
  ```

### Data Extractors
- Bank-specific extractors in `data_extractor/` 
- Common pattern for PDF processing:
  1. Text extraction with pdfplumber
  2. Line-by-line parsing with regex patterns
  3. DataFrame construction and cleanup
  4. Output formatting
- Example: `bancolombia.py` demonstrates robust text parsing with:
  - Custom line grouping logic
  - Multi-line transaction merging
  - Currency normalization
  - Reference number extraction

### Output Conventions
- All extractors output standardized DataFrames with columns:
  - `page`: PDF page number
  - `date`: Transaction date
  - `description`: Transaction description
  - `reference`: Optional reference number
  - `amount_cop`: Amount in COP (float)

## Common Development Tasks

### Adding a New Bank Extractor
1. Create extractor module in `data_extractor/`
2. Create CLI module in `_cli/` following existing patterns
3. Register CLI command in `_main.py`
4. Add appropriate regex patterns and parsing logic
5. Return standardized DataFrame format

### Running Tests
- TBD (Tests to be implemented)

### Logging Conventions
Use the project's logger from `common.logger`:
```python
from my_finances.common.logger import logger

logger.info("Processing file: %s", filename)
logger.debug("Found %d transactions", len(df))
```

## Key Files

- `src/my_finances/_cli/_main.py`: CLI entrypoint and command registration
- `src/my_finances/data_extractor/bancolombia.py`: Example bank statement parser
- `src/my_finances/common/logger.py`: Logging configuration

## Dependencies
- Core: pandas, pdfplumber
- Output formats: openpyxl (Excel), pyarrow (Parquet)

## Future Considerations
- Implement test suite
- Add input validation
- Support additional banks