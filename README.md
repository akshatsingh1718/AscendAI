# AscendAI — Lead Generation & Assessment Platform

![](./assets/images/flowchart.png)

AscendAI is an AI-powered lead generation and assessment platform that helps identify and evaluate potential PayU customers through web search and intelligent analysis.

## Features

- 🤖 **AI-Powered Lead Generation**: Automatically discovers potential leads using web search
- 📊 **Intelligent Lead Assessment**: Evaluates leads on multiple factors including tech stack, business maturity, and integration readiness
- 🎯 **FastAPI Backend**: RESTful API for lead management operations
- 🎨 **Streamlit Frontend**: Modern web interface for interacting with the platform
- 💾 **Database Integration**: SQLite/PostgreSQL support for persistent lead storage

## Prerequisites

- **Python 3.12+**
- **uv** — Fast Python package installer and resolver ([Installation Guide](https://github.com/astral-sh/uv))

### Installing uv

```bash
# macOS and Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# Or via pip
pip install uv
```

## Setup

### 1. Clone the Repository

```bash
git clone <repository-url>
cd ascendai
```

### 2. Install Dependencies

The project uses `uv` for dependency management. Dependencies are automatically installed when you run commands with `uv run`.

To explicitly sync dependencies:

```bash
uv sync
```

### 3. Install Browser Dependencies (for web scraping)

The project uses Playwright for browser automation. Install system dependencies:

```bash
sudo uv run playwright install-deps
```

### 4. Configure Environment Variables

Copy the example environment file and configure your API keys:

```bash
cp example.env .env
```

Edit `.env` and set the following variables:

```env
AWS_SECRET_ACCESS_KEY=your_aws_secret_key
AWS_BEARER_TOKEN_BEDROCK=your_bedrock_token
AWS_DEFAULT_REGION=us-east-1
SERPER_API_KEY=your_serper_api_key
SERPAPI_API_KEY=your_serpapi_key
DATABASE_URL=sqlite:///payu_leads.db
DATABASE_PATH=payu_leads.db
```

**Required API Keys:**
- **SERPER_API_KEY**: For web search functionality ([Get API Key](https://serper.dev))
- **AWS Credentials**: For AWS Bedrock LLM integration
- **SERPAPI_API_KEY**: Alternative search API (optional)

## Running the Application

The application consists of two components: a FastAPI backend and a Streamlit frontend.

### Backend (FastAPI)

Start the API server:

```bash
uv run ./src/ascendai/api.py
```

The API will be available at:
- **API Base URL**: `http://localhost:8000`
- **Interactive Docs (Swagger)**: `http://localhost:8000/docs`
- **Alternative Docs (ReDoc)**: `http://localhost:8000/redoc`
- **Health Check**: `http://localhost:8000/health`

### Frontend (Streamlit)

In a separate terminal, start the Streamlit application:

```bash
uv run streamlit run src/ascendai/streamlit_app.py --server.port 8502 --server.address 0.0.0.0
```

The Streamlit UI will be available at:
- **Web Interface**: `http://localhost:8502`

> **Note**: Make sure the backend API is running before using the frontend, as the Streamlit app connects to the API at `http://localhost:8000` by default.

## Usage

### Using the Streamlit UI

1. Open `http://localhost:8502` in your browser
2. Use the sidebar to navigate between actions:
   - **Generate Leads**: Create new leads from web search
   - **Assess Leads**: Evaluate existing leads with AI analysis
   - **List Leads**: Browse and filter leads
   - **Lead Detail**: View detailed information about a specific lead
   - **Stats**: View database statistics

### Using the API Directly

See [API_DOCS.md](./API_DOCS.md) for detailed API documentation and examples.

**Quick Examples:**

```bash
# Generate leads
curl -X POST http://localhost:8000/leads/generate \
  -H "Content-Type: application/json" \
  -d '{"limit": 5}'

# Assess leads
curl -X POST http://localhost:8000/leads/assess \
  -H "Content-Type: application/json" \
  -d '{"limit": 3}'

# List leads
curl http://localhost:8000/leads?status=assessed&limit=10

# Get statistics
curl http://localhost:8000/stats
```

## Project Structure

```
ascendai/
├── src/
│   ├── ascendai/
│   │   ├── api.py              # FastAPI backend application
│   │   ├── streamlit_app.py    # Streamlit frontend application
│   │   ├── lead_generation.py  # Lead discovery logic
│   │   ├── lead_assessor.py    # Lead assessment logic
│   │   └── llm.py              # AWS Bedrock LLM integration
│   ├── models/
│   │   ├── lead.py             # Lead database model
│   │   └── search_query.py     # Search query model
│   └── utils/
│       └── web_search.py       # Web search utilities
├── pyproject.toml              # Project dependencies and configuration
├── example.env                  # Environment variables template
└── README.md                    # This file
```

## Development

### Running in Development Mode

The FastAPI backend runs with auto-reload enabled by default. The Streamlit app also supports auto-reload.

### Database

By default, the application uses SQLite (`payu_leads.db`). You can switch to PostgreSQL by updating the `DATABASE_URL` in your `.env` file:

```env
DATABASE_URL=postgresql://user:password@localhost/ascendai
```

## Troubleshooting

### Port Already in Use

If port 8000 or 8502 is already in use, you can change them:

**Backend:**
- Edit `src/ascendai/api.py` and modify the `uvicorn.run()` port parameter

**Frontend:**
- Change the port in the streamlit command: `--server.port 8503`

### Browser Dependencies

If you encounter issues with Playwright, ensure system dependencies are installed:

```bash
sudo uv run playwright install-deps
uv run playwright install chromium
```

### API Connection Errors

If the Streamlit app cannot connect to the API:
1. Verify the backend is running on `http://localhost:8000`
2. Check the API base URL in the Streamlit sidebar
3. Ensure no firewall is blocking the connection

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Contributing

Contributions are welcome and greatly appreciated! Here's how you can help:

### How to Contribute

1. **Fork the repository** and clone it to your local machine
2. **Create a branch** for your feature or bugfix:
   ```bash
   git checkout -b feature/your-feature-name
   ```
3. **Make your changes** and ensure they follow the project's code style
4. **Test your changes** to make sure everything works correctly
5. **Commit your changes** with clear, descriptive commit messages:
   ```bash
   git commit -m "Add: description of your changes"
   ```
6. **Push to your fork** and open a Pull Request

### Contribution Guidelines

- **Code Style**: Follow Python PEP 8 style guidelines
- **Documentation**: Update documentation for any new features or API changes
- **Testing**: Add tests for new features when possible
- **Commit Messages**: Use clear, descriptive commit messages
- **Pull Requests**: 
  - Provide a clear description of what your PR does
  - Reference any related issues
  - Ensure all tests pass before submitting

### Reporting Issues

If you find a bug or have a suggestion, please [open an issue](<repository-url>/issues) with:
- A clear description of the problem or suggestion
- Steps to reproduce (for bugs)
- Expected vs. actual behavior
- Your environment details (OS, Python version, etc.)

### Code of Conduct

- Be respectful and inclusive
- Welcome newcomers and help them get started
- Focus on constructive feedback
- Celebrate diverse perspectives and experiences

## Support

For issues and questions, please [open an issue](<repository-url>/issues) or contact the maintainers.
