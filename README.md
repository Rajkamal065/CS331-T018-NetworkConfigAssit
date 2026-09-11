# CS331 Computer Networks — Course Project

- **Team ID:** T018
- **Project ID:** CS331-T018
- **Project Title:** NetOps MCP Assistant: Safe Linux Network Automation

---

## 👥 Team Members

| Roll Number | Full Name |
| :--- | :--- |
| **23110366** | Yalla Sai Teja |
| **23110259** | Pulakurthi Manohar |
| **23110319** | Sowpati Raj Kamal |
| **23110123** | Guda Avinash Reddy |
| **23110144** | Jangam Sanjay |
| **23110115** | Gella Jaya Rama Krishna |

---

## 📁 Folder Structure

```text
README.md
/code       → all source code
/report     → final report (PDF)
/ppt        → presentation slides (PDF or .pptx)
/AI_Used    → AI usage documentation
```

### Directory Contents Summary:
- **`code/`**: Complete implementation of NetOps MCP Assistant (FastMCP server `server.py`, LLM bridge `llm_client.py`, coordinator `assistant.py`, web/desktop UI `ui/`, validation rules `rules/policies.yaml`, verification tools `tools/`, Docker container setup, and test suite).
- **`report/`**: Final project report PDF (`report.pdf`) and benchmark figures.
- **`ppt/`**: Final presentation slides (`CN_PPT.pdf` / `presentation.pdf`).
- **`AI_Used/`**: Comprehensive disclosure of AI tools, prompts, thought processes, and verification workflows used throughout the project.

---

## 🚀 Quick Start (Running the Application)

Navigate to the `code/` directory:
```bash
cd code
```

### Run Desktop / Web UI
```bash
# Optional: Setup virtual environment
python -m venv .venv
# Activate: .venv\Scripts\activate (Windows) or source .venv/bin/activate (Linux)

pip install -r requirements.txt
python app.py
```
*(For browser-only mode: `python app.py --web` and open http://localhost:5000)*

### Run via Docker
```bash
docker compose up --build
```

### Run Automated Test Suite
```bash
pytest tests/ -v
```
*(All 34 unit and integration tests passing)*