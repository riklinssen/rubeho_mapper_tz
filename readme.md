# Laterite Rubeho CCT 

A comprehensive toolkit for treatment area labeling, geospatial data extraction, and treatment-control matching for IE of a programme

## Project Overview

1. **Labeling treatment areas** through an interactive web application
2. **Extracting  geospatial features** from Google Earth Engine  
3. **Identifying matched control areas** using propensity score and other matching methods
4. **Validating match quality** spatially and statistically

## Repository Structure

```
rubeho_mapper/
├── labeling_app/          # Interactive Streamlit app for treatment area mapping
│   ├── app.py            # Main application
│   ├── pages/            # Multi-page app components
│   └── utils/            # App-specific utilities
│
├── notebooks/            # Analysis pipeline notebooks
│   ├── 01_data_preparation/       # Initial data setup and exploration
│   ├── 02_gee_extraction/         # Google Earth Engine data extraction
│   └── 03_matching_analysis/      # Treatment-control matching algorithms
│
├── src/                  # Reusable Python modules
│   ├── gee_utils.py     # Google Earth Engine utilities
│   ├── matching.py      # Matching algorithms (to be created)
│   └── visualization.py # Plotting functions (to be created)
│
├── config/              # Configuration files
│   ├── settings.py      # Project settings (CRS, regions, etc.)
│   └── gee_config.py    # Google Earth Engine configuration
│
├── data/                # Data directory (gitignored except structure)
│   ├── raw/            # Original shapefiles and Excel files
│   ├── processed/      # Cleaned and labeled datasets
│   ├── gee/           # Satellite and geospatial data from GEE
│   └── analysis/      # Matching results and validation outputs
│
├── docs/               # Documentation
│   └── matching_methodology.md  # Detailed matching approach guide
│
└── scripts/            # Utility scripts
    └── setup_gee.py   # Google Earth Engine authentication setup
```

## Project Phases

### Phase 1: Treatment Area Labeling ✅ COMPLETE

**Objective**: Identify and digitize treatment area boundaries

**Tool**: Interactive Streamlit web application

**Key features**:
- Map-based interface for polygon drawing
- Integration with Google Sheets for multi-user collaboration
- Progress tracking dashboard
- Quality control validation

**Status**: ~43 treatment villages mapped across 20 wards

### Phase 2: Geospatial Data Extraction 🔄 IN PROGRESS

**Objective**: Extract baseline features for matching

**Data sources**:
- Dynamic world land cover
- Worldpop population estimates
- Google Alphaearth embeddings
- Other relevant datasets

**Key covariates extracted**:
- Land cover composition
- Elevation, slope, aspect
- Distance to roads/settlements
- Land use and land cover

**Tools**: Google Earth Engine Python API.

### Phase 3: Matching Analysis 📋 UPCOMING

**Objective**: Identify appropriate control areas

**Approach**:
- Propensity score matching (primary)
- Mahalanobis distance matching (robustness)
- Coarsened exact matching (sensitivity)

**Validation**:
- Covariate balance assessment (SMD < 0.1)
- Common support checks
- Spatial distribution validation
- Sensitivity analysis

## Installation

### For Labeling App Only

```bash
# Clone repository
git clone https://github.com/yourusername/rubeho_mapper.git
cd rubeho_mapper

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install app requirements
pip install -r requirements/app.txt

# Run labeling app
cd labeling_app
streamlit run app.py
```

### For Full Analysis Pipeline

```bash
# Install analysis requirements (includes GEE)
pip install -r requirements/analysis.txt

```

## Usage

### 1. Running the Labeling App

```bash
cd labeling_app
streamlit run app.py
```

The app provides:
- Ward-by-ward navigation
- Village-level mapping interface
- Real-time progress tracking
- Google Sheets integration for team collaboration

### 2. Extracting Geospatial Features

```bash
# Navigate to GEE extraction notebooks
cd notebooks/02_gee_extraction

# Run extraction (in Jupyter or VS Code)
jupyter notebook 01_extract_landcover.py
```

Key outputs:

### 3. Running Matching Analysis

```bash
# Navigate to matching notebooks
cd notebooks/03_matching_analysis

# Run matching pipeline
jupyter notebook 01_feature_engineering.py
jupyter notebook 02_propensity_matching.py
jupyter notebook 03_validate_matches.py
```

Key outputs:
- `data/analysis/matched_controls/` - Selected control areas
- `data/analysis/validation/` - Balance diagnostics and plots
- Matched control boundaries (GeoJSON)

## Data Sources

### Input Data (Not in Repository)

1. **Tanzania Ward Boundaries** (2023)
   - Source: National Bureau of Statistics
   - Format: Shapefile
   - Location: `data/raw/ALL WARDS TANZANIA/`

2. **Program Implementation Data**
   - Source: Project team Excel file
   - Villages with ARR/REDD programs
   - Location: `data/raw/`

3. **Treatment Area Labels** (Generated by app)
   - Source: Google Sheets via labeling app
   - Polygon boundaries for treatment villages
   - Location: `data/processed/treatment_areas_labeled.geojson`

### Generated Outputs (Shared)

These files ARE committed to the repository for team sharing:

- `data/processed/region_coverage_plan.json` - Study area metadata
- `data/processed/relevant_wards_with_flags.geojson` - Ward boundaries with treatment flags

## Matching Methodology

See `docs/matching_methodology.md` for detailed guidance on:
- Covariate selection
- Propensity score estimation
- Balance assessment
- Sensitivity analysis
- Common pitfalls


## Contributing



## Contact

## Roadmap

- [x] Phase 1: Treatment area labeling app
- [x] Phase 1: Complete village mapping (43/43 villages)
- [ ] Phase 2: Extract land cover data
- [ ] Phase 2: Extract baseline vegetation indices
- [ ] Phase 2: Extract terrain and climate data
- [ ] Phase 3: Implement propensity score matching
- [ ] Phase 3: Validate matched controls
- [ ] Phase 3: Sensitivity analysis
- [ ] Phase 4: Extract post-treatment outcomes
- [ ] Phase 4: Impact estimation
- [ ] Phase 5: Final report and visualization

---

**Last Updated**: November 2024  
**Current Phase**: Geospatial Data Extraction (Phase 2)