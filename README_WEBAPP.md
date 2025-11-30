# TumorBoard Web Application

An Angular/Flask web application for AI-powered cancer variant actionability assessment.

## Architecture

This application uses a modern full-stack architecture:

- **Frontend**: Angular 17 with standalone components
- **Backend**: Flask REST API with async support
- **Core Logic**: Python library (`src/tumorboard/`) shared between CLI and API
- **APIs**: MyVariant.info for variant data, OpenAI for LLM assessment

```
tumor_board_v0/
├── frontend/               # Angular application
│   ├── src/
│   │   ├── app/
│   │   │   ├── services/  # API communication services
│   │   │   └── components # UI components
│   │   ├── styles.scss    # Global styles
│   │   └── main.ts        # Application bootstrap
│   ├── angular.json
│   └── package.json
├── backend/               # Flask REST API
│   ├── app.py            # API endpoints
│   ├── run.py            # Development server
│   └── requirements.txt  # Python dependencies
└── src/tumorboard/       # Shared core logic
    ├── api/              # MyVariant.info client
    ├── llm/              # LLM assessment service
    ├── models/           # Data models
    └── engine.py         # Main assessment engine
```

## Getting Started

### Prerequisites

- Python 3.11+
- Node.js 18+ and npm
- OpenAI API key

### Backend Setup

1. **Navigate to project root**:
   ```bash
   cd tumor_board_v0
   ```

2. **Create and activate virtual environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install Python dependencies**:
   ```bash
   pip install -e .
   pip install -r backend/requirements.txt
   ```

4. **Set up environment variables**:
   ```bash
   cp .env.example .env
   # Edit .env and add your OPENAI_API_KEY
   ```

5. **Start the Flask API server**:
   ```bash
   cd backend
   python run.py
   ```

   The API will be available at `http://localhost:5000`

   API Endpoints:
   - `GET /api/health` - Health check
   - `POST /api/assess` - Assess a variant
   - `GET /api/evidence/<gene>/<variant>` - Get raw evidence

### Frontend Setup

1. **Navigate to frontend directory**:
   ```bash
   cd tumor_board_v0/frontend
   ```

2. **Install Node dependencies**:
   ```bash
   npm install
   ```

3. **Start the Angular development server**:
   ```bash
   npm start
   ```

   The application will be available at `http://localhost:4200`

### Running Both Servers

For development, you'll need two terminal windows:

**Terminal 1 - Backend**:
```bash
cd tumor_board_v0/backend
source ../venv/bin/activate
python run.py
```

**Terminal 2 - Frontend**:
```bash
cd tumor_board_v0/frontend
npm start
```

Then open your browser to `http://localhost:4200`

## API Reference

### POST /api/assess

Assess a variant for clinical actionability.

**Request Body**:
```json
{
  "gene": "BRAF",
  "variant": "V600E",
  "tumor_type": "Melanoma"
}
```

**Response**:
```json
{
  "variant": {
    "gene": "BRAF",
    "variant": "V600E",
    "tumor_type": "Melanoma"
  },
  "assessment": {
    "tier": "Tier I",
    "confidence": 95.0,
    "rationale": "BRAF V600E is a well-established therapeutic target..."
  },
  "identifiers": {
    "cosmic_id": "COSM476",
    "ncbi_gene_id": "673",
    "dbsnp_id": "rs113488022",
    "clinvar_id": "13961"
  },
  "clinvar": {
    "clinical_significance": "Pathogenic",
    "accession": "RCV000014992"
  },
  "annotations": {
    "snpeff_effect": "missense_variant",
    "polyphen2_prediction": "D",
    "cadd_score": 32.0,
    "gnomad_exome_af": 3.97994e-06
  },
  "transcript": {
    "id": "NM_004333.4",
    "consequence": "missense_variant"
  }
}
```

### GET /api/evidence/{gene}/{variant}

Get raw evidence for a variant from MyVariant.info.

**Response**: Similar structure to assessment but without the LLM analysis.

## Features

### Variant Assessment
- Input gene symbol, variant notation, and optional tumor type
- Real-time assessment using LLM analysis
- Comprehensive display of all annotations and evidence

### Database Integration
- **MyVariant.info**: Aggregates data from CIViC, ClinVar, COSMIC, dbSNP
- **COSMIC**: Mutation IDs and cancer-specific data
- **ClinVar**: Clinical significance and accession numbers
- **dbSNP**: Reference SNP IDs
- **gnomAD**: Population allele frequencies

### Functional Annotations
- **SnpEff**: Predicted variant effects
- **PolyPhen2**: Pathogenicity predictions
- **CADD**: Combined annotation scores
- **HGVS**: Standard genomic, protein, and transcript notations

### AMP/ASCO/CAP Tier Classification
- **Tier I**: Strong clinical significance with FDA-approved therapies
- **Tier II**: Potential clinical significance with strong evidence
- **Tier III**: Unknown clinical significance
- **Tier IV**: Benign or likely benign variants

## Development

### Backend Development

The Flask backend is organized as:

- `backend/app.py`: Main Flask application with API endpoints
- `backend/run.py`: Development server launcher
- CORS enabled for cross-origin requests from Angular

Key dependencies:
- `flask`: Web framework
- `flask-cors`: Cross-origin resource sharing
- `httpx`: Async HTTP client for external APIs
- `pydantic`: Data validation and parsing

### Frontend Development

The Angular frontend uses:

- **Standalone Components**: Modern Angular architecture without modules
- **Reactive Forms**: Form handling with NgModel
- **HTTP Client**: API communication with observables
- **SCSS**: Styled with gradient design and card-based layout

Key files:
- `app.component.ts`: Main component logic
- `app.component.html`: Template with form and results display
- `tumorboard-api.service.ts`: API client service
- `styles.scss`: Global styles and design system

### Adding New Features

1. **Add API Endpoint**: Update `backend/app.py`
2. **Add Service Method**: Update `frontend/src/app/services/tumorboard-api.service.ts`
3. **Update Component**: Modify `app.component.ts` and `app.component.html`
4. **Update Types**: Add interfaces to service for type safety

## Building for Production

### Backend
```bash
# Install production dependencies
pip install gunicorn

# Run with gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 backend.app:app
```

### Frontend
```bash
cd frontend
npm run build

# Output will be in frontend/dist/tumorboard/
# Serve with any static file server
```

## Troubleshooting

### API Connection Failed
- Ensure Flask backend is running on port 5000
- Check browser console for CORS errors
- Verify OPENAI_API_KEY is set in backend environment

### Assessment Timeout
- Large evidence sets may take 30-60 seconds
- Check backend logs for API errors
- Verify OpenAI API is accessible

### Build Errors
- Ensure Node.js 18+ and Python 3.11+ are installed
- Clear caches: `npm cache clean --force` and `rm -rf node_modules`
- Check that all dependencies are installed

## Limitations

- **Research Tool Only**: Not for clinical decision-making
- **API Costs**: OpenAI API calls incur costs
- **Rate Limits**: Subject to MyVariant.info and OpenAI rate limits
- **Network Required**: Requires internet for external API calls

## Original CLI Tool

The original CLI tool is still available:

```bash
source venv/bin/activate
tumorboard assess BRAF V600E --tumor "Melanoma"
```

See the main [README.md](README.md) for CLI documentation.

## License

This is a research prototype. See main README for full disclaimer and limitations.
