# News Veracity Detector

## Overview

**News Veracity Detector** is an advanced, AI-powered platform for analyzing the credibility of news articles. It leverages state-of-the-art language models, web crawling, and fact-checking APIs to extract, analyze, and verify claims from news content, providing users with a transparent, evidence-based credibility score and detailed report.

---

## Table of Contents
- [Features](#features)
- [Architecture](#architecture)
- [Technologies Used](#technologies-used)
- [Backend Details](#backend-details)
- [Frontend Details](#frontend-details)
- [Workflow](#workflow)
- [Setup & Installation](#setup--installation)
- [Usage](#usage)
- [License](#license)

---

## Features
- **Automated News Analysis:** Analyze articles via URL or raw text.
- **Claim Extraction:** Uses LLMs to extract factual claims from articles.
- **Bias Detection:** Detects and rates bias in news content.
- **Fact-Checking:** Verifies claims using Google Fact Check API and corroborates with trusted sources.
- **Credibility Scoring:** Assigns a transparent, multi-factor credibility score.
- **Modern UI:** Newspaper-inspired, responsive frontend for clear results presentation.

---

## Architecture

```mermaid
graph TD;
  User-->|Submits Article|Frontend;
  Frontend-->|API Request|Backend;
  Backend-->|Crawling/LLM/Fact-Check|External_Services;
  Backend-->|Results|Frontend;
  Frontend-->|Displays Report|User;
  External_Services["LLMs, Fact-Check APIs, Web Crawlers"]
```

---

## Technologies Used

### Backend
- **Python 3.9+**
- **FastAPI** (API server)
- **httpx** (Async HTTP requests)
- **dotenv** (Environment variable management)
- **pydantic** (Data validation)
- **Crawl4ai**(extraction)
- **OpenAI, Together AI, Google Fact Check API**

### Frontend
- **React** (Vite-powered)
- **Framer Motion** (Animations)
- **Tailwind CSS** (Optional, for utility-first styling)
- **Custom CSS** (Newspaper theme)

---

## Backend Details

The backend is a robust, asynchronous FastAPI server that orchestrates a multi-phase pipeline for news analysis. It leverages state-of-the-art language models and fact-checking APIs to provide a transparent, evidence-based credibility score for news articles.

**Pipeline Phases:**
1. **Ingestion:**
   - Crawls and cleans article content from a URL or accepts raw text input.
   - Uses advanced web scraping strategies (via [Crawl4ai](https://github.com/crawl4ai/crawl4ai)) to extract the main article body.
   - Assigns a credibility tier to the publisher based on domain (e.g., Reuters = Tier 1, Infowars = Tier 5, etc.).
2. **Deconstruction:**
   - Utilizes a large language model (Meta Llama 3 via Together AI) to extract up to 7 significant factual claims and generate a bias report.
   - Outputs a structured JSON object with a bias summary and list of claims.
3. **Evidence Gathering:**
   - For each claim, queries the Google Fact Check API for existing fact-checks.
   - Performs targeted Google searches (restricted to trusted domains) and scrapes top results for corroborating evidence.
   - All evidence is collected asynchronously for efficiency.
4. **Synthesis & Scoring:**
   - Uses OpenAI GPT (gpt-3.5-turbo or gpt-4o) to synthesize the evidence for each claim, assign a verdict (e.g., "Well-Supported", "Disputed"), and provide a rationale.
   - Computes a final credibility score based on source tier, bias, and claim-level evidence.

**Models & APIs Used:**
- **Meta Llama 3 (Together AI):** Claim extraction & bias analysis
- **OpenAI GPT (gpt-3.5-turbo / gpt-4o):** Evidence synthesis & verdict assignment
- **Google Fact Check API:** Automated fact-checking

**Async Architecture:**
- All major steps are performed asynchronously for scalability and responsiveness.
- Supports concurrent evidence gathering and claim analysis.

**Example Output:**
- Final report includes: credibility score, score breakdown, publisher tier, bias report, and claim-by-claim verdicts with evidence.

---

## Frontend Details

- **User Interface:**
  - Lets users submit news articles by URL or text.
  - Shows progress, results, and errors in a visually appealing, newspaper-inspired layout.
  - Displays credibility score, bias report, and claim-by-claim verdicts.
- **API Integration:**
  - Communicates with the backend for analysis requests and result polling.
  - Handles asynchronous workflows and updates UI in real time.
- **Responsive Design:**
  - Optimized for both desktop and mobile devices.
  - Print-friendly styles for sharing or archiving reports.

---

## Workflow

```mermaid
graph TD;
  User["User"]-->|"Submits Article (URL/Text)"|Frontend["Frontend (React)"];
  Frontend-->|"POST /analyze"|Backend["Backend (FastAPI)"];
  Backend-->|"Phase 1: Ingestion"|Ingestion["Ingestion (Crawl4ai)"];
  Ingestion-->|"Cleaned Content, Source Tier"|Deconstruction["Deconstruction (LLM)"];
  Deconstruction-->|"Claims, Bias Report"|Evidence["Evidence Gathering (Fact Check API, Google Search)"];
  Evidence-->|"Fact-Checks, Corroboration"|Synthesis["Synthesis & Scoring (OpenAI GPT)"];
  Synthesis-->|"Final Report"|Frontend;
  Frontend-->|"Displays Results"|User;
  Evidence-->|"Fact Check API, Google Search"|External["External Services"];
  Deconstruction-->|"Together AI (Llama 3)"|External;
  Synthesis-->|"OpenAI GPT"|External;
```

---

## Setup & Installation

### Prerequisites
- Python 3.9+
- Node.js (for frontend)
- API keys for OpenAI, Together AI, and Google Fact Check API

### Backend Setup
```bash
cd news_veracity_detector/news/Backend
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
# Set up your .env file with required API keys
uvicorn api:app --reload
```

### Frontend Setup
```bash
cd news_veracity_detector/news/Fronted
npm install
npm run dev
```

---

## Usage

1. Start the backend server (see above).
2. Start the frontend development server.
3. Open the frontend in your browser (usually at `http://localhost:5173`).
4. Enter a news article URL or paste text, then click "Analyze".
5. Review the credibility score, bias report, and claim-by-claim analysis.

---

## License

This project is for educational and research purposes. For commercial or production use, please contact the maintainers.
