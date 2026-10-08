import os
import smtplib
import sys
from datetime import datetime
from email.mime.text import MIMEText

import requests
from dotenv import load_dotenv
from openai import OpenAI, APIError

load_dotenv()

SUPPORTED_REPORT_TYPES = ["weather", "news_summary"]
DEFAULT_WEATHER_LOCATION = "Kampala"
MODEL = "openai/gpt-5-mini"


def validate_args(argv):
    """
    Validate command-line arguments.

    Returns (email, report_type) if valid.
    Raises ValueError with a clear message if not.
    """
    if len(argv) != 3:
        raise ValueError(
            "Usage: python ai_reporter.py <email_address> <report_type>"
        )

    email = argv[1]
    report_type = argv[2]

    if not is_valid_email(email):
        raise ValueError(f"'{email}' does not look like a valid email address.")

    if report_type not in SUPPORTED_REPORT_TYPES:
        raise ValueError(
            f"'{report_type}' is not supported. "
            f"Choose one of: {', '.join(SUPPORTED_REPORT_TYPES)}"
        )

    return email, report_type


def is_valid_email(email):
    """A simple check: must contain '@' and '.' after the '@'."""
    if "@" not in email:
        return False
    local, _, domain = email.partition("@")
    if not local or "." not in domain:
        return False
    return True


def derive_recipient_name(email):
    """
    Derive a simple, presentable name from the local part of an email
    address (the part before '@'), for use in the formal greeting.
    e.g. "joan.smith85@gmail.com" -> "Joan Smith"
    """
    local_part = email.split("@")[0]
    local_part = "".join(char for char in local_part if not char.isdigit())
    words = [w for w in local_part.replace("_", ".").split(".") if w]
    if not words:
        return "there"
    return " ".join(word.capitalize() for word in words)


def fetch_weather_data(location=DEFAULT_WEATHER_LOCATION):
    """Fetch current weather data from wttr.in as JSON."""
    url = f"https://wttr.in/{location}?format=j1"
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    return response.json()


def fetch_news_data():
    """Fetch top headlines from NewsAPI as JSON."""
    api_key = os.environ.get("NEWS_API_KEY")
    url = "https://newsapi.org/v2/top-headlines"
    params = {"country": "us", "pageSize": 5, "apiKey": api_key}
    response = requests.get(url, params=params, timeout=10)
    response.raise_for_status()
    return response.json()


def get_report_data(report_type):
    """Dispatch to the correct fetch function based on report_type."""
    if report_type == "weather":
        return fetch_weather_data()
    elif report_type == "news_summary":
        return fetch_news_data()
    else:
        raise ValueError(f"No data fetcher implemented for '{report_type}'")


def build_prompt(report_type, raw_data):
    """Turn raw API data into an instruction prompt for the LLM."""
    if report_type == "weather":
        return (
            "Here is raw weather JSON data:\n\n"
            f"{raw_data}\n\n"
            "Write a short, friendly 3-4 sentence weather update suitable "
            "for the body of an email. Mention temperature, conditions, "
            "and any useful advice (e.g. bring an umbrella). "
            "Do not include a greeting (e.g. 'Good morning', 'Hello') or a "
            "sign-off -- write only the weather content itself, since it "
            "will be inserted into an existing email template."
        )
    elif report_type == "news_summary":
        return (
            "Here is raw news headline JSON data:\n\n"
            f"{raw_data}\n\n"
            "Write a concise email-friendly summary of the top headlines, "
            "as a short bulleted list with a one-line description each. "
            "Do not include a greeting (e.g. 'Good morning', 'Hello') or a "
            "sign-off -- write only the news content itself, since it "
            "will be inserted into an existing email template."
        )
    else:
        raise ValueError(f"No prompt template implemented for '{report_type}'")


def generate_summary(client, prompt):
    """
    Send the prompt to the LLM via OpenRouter and return the generated
    text. Returns None if the request failed.
    """
    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=800,
        )
        return response.choices[0].message.content
    except APIError as e:
        print(f"Error generating summary from OpenRouter: {e}")
        return None


def format_email_body(report_type, summary, recipient_name=None):
    """
    Wrap the AI-generated summary in a formal email structure: a proper
    salutation, a date line, an introductory sentence, the summary as
    the body, and a formal closing -- rather than sending the raw AI
    text on its own.
    """
    report_label = report_type.replace("_", " ").title()
    today = datetime.now().strftime("%B %d, %Y")
    greeting_name = recipient_name if recipient_name else "there"

    return (
        f"Dear {greeting_name},\n\n"
        f"Date: {today}\n\n"
        f"Please find below your requested {report_label} Report, "
        "generated on your behalf.\n\n"
        "-----------------------------------\n"
        f"{summary}\n"
        "-----------------------------------\n\n"
        "Should you have any questions regarding this report, please "
        "do not hesitate to reach out.\n\n"
        "Kind regards,\n"
        "AI Reporter\n"
        "Automated Reporting Service"
    )


def send_email(to_address, subject, body):
    """
    Send an email via Gmail using smtplib.
    Returns True on success, False on failure.
    """
    gmail_address = os.environ.get("GMAIL_ADDRESS")
    gmail_app_password = os.environ.get("GMAIL_APP_PASSWORD")

    message = MIMEText(body)
    message["Subject"] = subject
    message["From"] = gmail_address
    message["To"] = to_address

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(gmail_address, gmail_app_password)
            server.sendmail(gmail_address, [to_address], message.as_string())
        return True
    except (smtplib.SMTPException, OSError) as e:
        print(f"Error sending email: {e}")
        return False

def main():
    try:
        email, report_type = validate_args(sys.argv)
    except ValueError as e:
        print(e)
        sys.exit(1)

    print(f"Fetching {report_type} data...")
    raw_data = get_report_data(report_type)

    print("Generating summary...")
    prompt = build_prompt(report_type, raw_data)
    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=os.environ.get("OPENROUTER_API_KEY"),
    )
    summary = generate_summary(client, prompt)

    if summary is None:
        print("Could not generate a summary. Exiting.")
        sys.exit(1)

    print("Sending email...")
    subject = f"Your {report_type.replace('_', ' ').title()} Report"
    recipient_name = derive_recipient_name(email)
    email_body = format_email_body(report_type, summary, recipient_name)
    sent = send_email(email, subject, email_body)

    if sent:
        print(f"Report sent to {email}!")
    else:
        print("Failed to send the email.")
        sys.exit(1)


if __name__ == "__main__":
    main()