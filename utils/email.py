"""
Email service abstraction.

In development / when MAIL_PROVIDER=console, OTPs are logged to the console.
Set MAIL_PROVIDER=sendgrid_api (recommended on Render) to send via SendGrid's
v3 HTTP REST API over port 443, bypassing Render's outbound SMTP port blocks.
Set MAIL_PROVIDER=smtp for traditional SMTP servers.
"""
import logging
import smtplib
import threading
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import requests

logger = logging.getLogger("whistlevault.mail")


class EmailService:
    def __init__(self, app=None):
        self.app = app

    def init_app(self, app):
        self.app = app

    def _config(self, key, default=None):
        return self.app.config.get(key, default)

    def send_otp_email(self, to_email: str, otp_code: str):
        subject = "Your WhistleVault verification code"
        body = (
            f"Your WhistleVault verification code is: {otp_code}\n\n"
            f"This code expires in {self._config('OTP_EXPIRY_MINUTES', 10)} minutes. "
            "If you did not request this, you can safely ignore this email."
        )
        self._dispatch_async(to_email, subject, body)

    def send_password_reset_email(self, to_email: str, reset_url: str):
        subject = "Reset your WhistleVault password"
        body = (
            "We received a request to reset your WhistleVault password.\n\n"
            f"Open this link to choose a new password:\n{reset_url}\n\n"
            f"This link expires in {self._config('PASSWORD_RESET_EXPIRY_MINUTES', 30)} minutes. "
            "If you did not request this, you can safely ignore this email."
        )
        self._dispatch_async(to_email, subject, body)

    def _dispatch_async(self, to_email, subject, body):
        """Queue delivery so email latency never blocks a user request."""
        app = self.app

        def deliver():
            try:
                with app.app_context():
                    self._dispatch(to_email, subject, body)
            except Exception:
                logger.exception("Background email delivery failed for %s", to_email)

        threading.Thread(target=deliver, name="whistlevault-mail", daemon=True).start()

    def _dispatch(self, to_email, subject, body):
        provider = self._config("MAIL_PROVIDER", "console")
        if provider == "sendgrid_api":
            self._send_sendgrid_api(to_email, subject, body)
        elif provider == "smtp":
            self._send_smtp(to_email, subject, body)
        else:
            self._send_console(to_email, subject, body)

    def _send_console(self, to_email, subject, body):
        logger.info(
            "\n----- [SIMULATED EMAIL] -----\nTo: %s\nSubject: %s\n\n%s\n------------------------------",
            to_email, subject, body,
        )

    def _send_sendgrid_api(self, to_email, subject, body):
        """Sends email via SendGrid v3 REST API (HTTPS port 443)."""
        api_key = self._config("MAIL_PASSWORD")
        sender = self._config("MAIL_DEFAULT_SENDER")
        timeout = int(self._config("MAIL_TIMEOUT_SECONDS", 8))

        if not api_key or not sender:
            logger.error("SendGrid API error: MAIL_PASSWORD (API Key) or MAIL_DEFAULT_SENDER not configured.")
            self._send_console(to_email, subject, body)
            return

        url = "https://api.sendgrid.com/v3/mail/send"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "personalizations": [{"to": [{"email": to_email}]}],
            "from": {"email": sender},
            "subject": subject,
            "content": [{"type": "text/plain", "value": body}],
        }

        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
            if resp.status_code == 202:
                logger.info("Email successfully sent via SendGrid API to %s", to_email)
            else:
                logger.error("SendGrid API rejected delivery [%s]: %s", resp.status_code, resp.text)
                self._send_console(to_email, subject, body)
        except Exception:
            logger.exception("SendGrid HTTP API request failed for %s -- falling back to console", to_email)
            self._send_console(to_email, subject, body)

    def _send_smtp(self, to_email, subject, body):
        msg = MIMEMultipart()
        msg["From"] = self._config("MAIL_DEFAULT_SENDER")
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        server = self._config("MAIL_SERVER")
        port = int(self._config("MAIL_PORT", 587))
        username = self._config("MAIL_USERNAME")
        password = self._config("MAIL_PASSWORD")
        use_tls = self._config("MAIL_USE_TLS", True)

        try:
            with smtplib.SMTP(
                server,
                port,
                timeout=int(self._config("MAIL_TIMEOUT_SECONDS", 8)),
            ) as smtp:
                if use_tls:
                    smtp.starttls()
                if username and password:
                    smtp.login(username, password)
                smtp.sendmail(msg["From"], [to_email], msg.as_string())
                logger.info("Email successfully sent via SMTP to %s", to_email)
        except Exception:
            logger.exception("Failed to send SMTP email to %s -- falling back to console log", to_email)
            self._send_console(to_email, subject, body)


email_service = EmailService()