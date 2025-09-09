# Rubeho Treatment Area Labeling Tool

A Streamlit web application for identifying and labeling treatment areas in Tanzania's Rubeho region to support treatment-control matching for program evaluation.

## Project Overview

This labeling tool helps researchers identify and validate treatment areas where conservation programs (ARR and REDD) have been implemented. The application processes administrative boundaries and survey data to create labeled datasets needed for matching treatment areas to appropriate control locations in future impact evaluation studies.

## Key Features

- **Treatment Area Identification**: Interactive interface for identifying and validating treatment locations
- **Spatial Data Labeling**: Label grid cells as treatment  areas
- **Quality Control**: Review and correct treatment area classifications
- **Export for Analysis**: Generate labeled datasets for treatment-control matching studies

## Repository Structure

```
rubeho_mapper/
├── config/
│   ├── __init__.py
│   └── settings.py              # Project configuration and CRS settings
├── data/
│   ├── processed/               # Generated labeled datasets (gitignored)
│   └── raw/                     # Source data files (gitignored)
├── notebooks/
│   └── 01_explore_districts.py  # Data processing and labeling script
├── pages/                       # Streamlit app pages for labeling workflow
├── utils/                       # Utility functions
├── .gitignore                   # Git ignore rules
├── app.py                       # Main Streamlit labeling application
├── requirements.txt             # Python dependencies
└── README.md                    # This file
```

## Data Sources

### Input Files (not included in repository)

- **ALL WARDS TANZANIA/Ward05082023.shp**: Tanzania administrative boundaries at ward level
- **Rubeho Villages for HH survey - v2.xlsx**: Survey data with treatment locations (ARR/REDD programs)

### Generated Output Files

- **relevant_wards_with_flags.geojson**: Ward boundaries labeled with treatment status
- **region_coverage_plan.json**: Metadata for treatment-control area matching

## Installation

1. Clone the repository:
```bash
git clone https://github.com/riklinssen/tz_rubeho_mapper.git
cd tz_rubeho_mapper
```

2. Create and activate virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Place your data files in the appropriate directories:
   - Shapefile: `data/raw/ALL WARDS TANZANIA/`
   - Survey data: `data/raw/Rubeho Villages for HH survey - v2.xlsx`

## Usage

### 1. Initial Data Processing

Generate the base labeled dataset:

```bash
python notebooks/01_explore_districts.py
```

This processes the raw data and creates initial treatment area labels.

### 2. Launch the Labeling Application

Start the interactive labeling tool:

```bash
streamlit run app.py
```

Access the application at `http://localhost:8501`

### 3. Labeling Workflow

The application provides:

- **Treatment Verification**: Review and validate automatically identified treatment areas
- **Manual Labeling**: Manually label additional areas based on local knowledge
- **Spatial Review**: Visual inspection of treatment area boundaries and adjacencies

## Application Features

### Interactive Labeling Interface
- Map-based interface for reviewing ward boundaries
- Point-and-click labeling of treatment/control status
- Visual validation of treatment area locations


### Treatment-Control Preparation
- Identification of program regions (Dodoma, Morogoro) vs adjacent control regions
- Spatial buffer analysis for control area selection
- Generation of balanced datasets for impact evaluation



