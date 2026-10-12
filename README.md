# AI Reporter

A Python command-line tool that fetches live data from public APIs, uses an LLM
to summarize it, and emails the result.

## How it works
1. Validates the email address and report type.
2. Fetches data: weather (wttr.in) or top headlines (NewsAPI).
3. Builds a prompt for that report type and sends it to an LLM through OpenRouter (openai/gpt-5-mini).
4. Emails the generated summary through Gmail SMTP.

## Setup
    python3 -m venv venv && source venv/bin/activate
    pip install -r requirements.txt
    cp .env.example .env    # then fill in your keys

## Usage
    python ai_reporter.py you@example.com weather
    python ai_reporter.py you@example.com news_summary

## Design notes
- One function per step (validation, fetching, prompting, summarizing, emailing).
- Keys and credentials come from environment variables, never from the code.
- API and email failures print a clear message and exit with a non-zero code.

## Sample output
See sample_output.txt.
