"""
Email service abstraction.

In development / when MAIL_PROVIDER=console, OTPs are just logged to the
server console so the app is fully runnable with zero external services.
Swap MAIL_PROVIDER=smtp and fill in MAIL_* env vars to send real email
through any standard SMTP provider (SendGrid, SES, Mailgun, Gmail, etc.)
without touching calling code -- that's the point of the abstraction.
"""
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

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
        self._dispatch(to_email, subject, body)

    def send_password_reset_email(self, to_email: str, reset_url: str):
        subject = "Reset your WhistleVault password"
        body = (
            "We received a request to reset your WhistleVault password.\n\n"
            f"Open this link to choose a new password:\n{reset_url}\n\n"
            f"This link expires in {self._config('PASSWORD_RESET_EXPIRY_MINUTES', 30)} minutes. "
            "If you did not request this, you can safely ignore this email."
        )
        self._dispatch(to_email, subject, body)

    def _dispatch(self, to_email, subject, body):
        provider = self._config("MAIL_PROVIDER", "console")
        if provider == "smtp":
            self._send_smtp(to_email, subject, body)
        else:
            self._send_console(to_email, subject, body)

    def _send_console(self, to_email, subject, body):
        logger.info(
            "\n----- [SIMULATED EMAIL] -----\nTo: %s\nSubject: %s\n\n%s\n------------------------------",
            to_email, subject, body,
        )

    def _send_smtp(self, to_email, subject, body):
        msg = MIMEMultipart()
        msg["From"] = self._config("MAIL_DEFAULT_SENDER")
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        server = self._config("MAIL_SERVER")
        port = self._config("MAIL_PORT")
        username = self._config("MAIL_USERNAME")
        password = self._config("MAIL_PASSWORD")
        use_tls = self._config("MAIL_USE_TLS", True)

        try:
            with smtplib.SMTP(server, port, timeout=10) as smtp:
                if use_tls:
                    smtp.starttls()
                if username and password:
                    smtp.login(username, password)
                smtp.sendmail(msg["From"], [to_email], msg.as_string())
        except Exception:
            logger.exception("Failed to send SMTP email to %s -- falling back to console log", to_email)
            self._send_console(to_email, subject, body)


email_service = EmailService()
