from unittest.mock import MagicMock, patch

import pytest

from ai_reporter import (
    validate_args,
    is_valid_email,
    derive_recipient_name,
    fetch_weather_data,
    fetch_news_data,
    build_prompt,
    generate_summary,
    format_email_body,
    send_email,
)

def test_validate_args_with_valid_input():
    argv = ["ai_reporter.py", "user@example.com", "weather"]
    email, report_type = validate_args(argv)
    assert email == "user@example.com"
    assert report_type == "weather"


def test_validate_args_wrong_number_of_arguments():
    argv = ["ai_reporter.py", "user@example.com"]
    with pytest.raises(ValueError):
        validate_args(argv)


def test_validate_args_invalid_email():
    argv = ["ai_reporter.py", "not-an-email", "weather"]
    with pytest.raises(ValueError):
        validate_args(argv)


def test_validate_args_unsupported_report_type():
    argv = ["ai_reporter.py", "user@example.com", "stock_update"]
    with pytest.raises(ValueError):
        validate_args(argv)


def test_is_valid_email_accepts_reasonable_addresses():
    assert is_valid_email("user@example.com") is True


def test_is_valid_email_rejects_missing_at_symbol():
    assert is_valid_email("userexample.com") is False


def test_is_valid_email_rejects_missing_dot_in_domain():
    assert is_valid_email("user@examplecom") is False


@patch("ai_reporter.requests.get")
def test_fetch_weather_data_returns_json(mock_get):
    fake_response = MagicMock()
    fake_response.json.return_value = {"current_condition": [{"temp_C": "25"}]}
    fake_response.raise_for_status.return_value = None
    mock_get.return_value = fake_response

    data = fetch_weather_data("Kampala")

    assert data == {"current_condition": [{"temp_C": "25"}]}
    mock_get.assert_called_once()


@patch("ai_reporter.requests.get")
def test_fetch_news_data_returns_json(mock_get):
    fake_response = MagicMock()
    fake_response.json.return_value = {"articles": [{"title": "Breaking news"}]}
    fake_response.raise_for_status.return_value = None
    mock_get.return_value = fake_response

    data = fetch_news_data()

    assert data == {"articles": [{"title": "Breaking news"}]}
    mock_get.assert_called_once()


def test_build_prompt_weather_includes_data():
    prompt = build_prompt("weather", {"temp_C": "25"})
    assert "weather" in prompt.lower()
    assert "25" in prompt


def test_build_prompt_weather_instructs_no_greeting():
    prompt = build_prompt("weather", {"temp_C": "25"})
    assert "greeting" in prompt.lower()


def test_build_prompt_news_instructs_no_greeting():
    prompt = build_prompt("news_summary", {"articles": []})
    assert "greeting" in prompt.lower()


def test_build_prompt_unsupported_type_raises():
    with pytest.raises(ValueError):
        build_prompt("stock_update", {})


def test_generate_summary_returns_text_on_success():
    fake_choice = MagicMock()
    fake_choice.message.content = "It's sunny and 25C today."
    fake_response = MagicMock()
    fake_response.choices = [fake_choice]

    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value = fake_response

    summary = generate_summary(fake_client, "Summarize this weather data")

    assert summary == "It's sunny and 25C today."


def test_generate_summary_returns_none_on_api_error():
    from openai import APIError

    fake_client = MagicMock()
    fake_client.chat.completions.create.side_effect = APIError(
        "boom", request=MagicMock(), body=None
    )

    summary = generate_summary(fake_client, "Summarize this")

    assert summary is None


def test_derive_recipient_name_from_dot_separated_email():
    assert derive_recipient_name("joan.smith@gmail.com") == "Joan Smith"


def test_derive_recipient_name_strips_digits():
    assert derive_recipient_name("joan85@gmail.com") == "Joan"


def test_derive_recipient_name_falls_back_when_unparseable():
    assert derive_recipient_name("12345@gmail.com") == "there"



def test_format_email_body_includes_formal_greeting():
    body = format_email_body("weather", "Sunny and 25C today.", "Joan")
    assert body.startswith("Dear Joan,")


def test_format_email_body_includes_formal_closing():
    body = format_email_body("weather", "Sunny and 25C today.", "Joan")
    assert "Kind regards," in body
    assert body.strip().endswith("Automated Reporting Service")


def test_format_email_body_defaults_greeting_when_no_name_given():
    body = format_email_body("weather", "Sunny and 25C today.")
    assert body.startswith("Dear there,")


def test_format_email_body_uses_readable_report_label():
    body = format_email_body("news_summary", "Top story: markets rally.", "Joan")
    assert "News Summary" in body


def test_format_email_body_includes_the_summary_content():
    body = format_email_body("weather", "Sunny and 25C today.", "Joan")
    assert "Sunny and 25C today." in body


@patch("ai_reporter.smtplib.SMTP_SSL")
def test_send_email_returns_true_on_success(mock_smtp_class, monkeypatch):
    monkeypatch.setenv("GMAIL_ADDRESS", "bot@example.com")
    monkeypatch.setenv("GMAIL_APP_PASSWORD", "fake-app-password")

    mock_server = MagicMock()
    mock_smtp_class.return_value.__enter__.return_value = mock_server

    result = send_email("user@example.com", "Test Subject", "Test body")

    assert result is True
    mock_server.login.assert_called_once_with("bot@example.com", "fake-app-password")
    mock_server.sendmail.assert_called_once()


@patch("ai_reporter.smtplib.SMTP_SSL")
def test_send_email_returns_false_on_failure(mock_smtp_class, monkeypatch):
    import smtplib

    monkeypatch.setenv("GMAIL_ADDRESS", "bot@example.com")
    monkeypatch.setenv("GMAIL_APP_PASSWORD", "fake-app-password")

    mock_smtp_class.side_effect = smtplib.SMTPException("connection failed")

    result = send_email("user@example.com", "Test Subject", "Test body")

    assert result is False