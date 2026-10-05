import smtplib
from datetime import datetime, timedelta, UTC
from email.mime.text import MIMEText

import requests
from requests.auth import HTTPBasicAuth

from config import (
    CLIENT_ID,
    CLIENT_SECRET,
    FAILURE_EMAIL_FROM,
    FAILURE_EMAIL_TO,
    PO_RECORD_URL,
    SMTP_HOST,
    SMTP_PASSWORD,
    SMTP_PORT,
    SMTP_USERNAME,
    SMTP_USE_TLS,
    SO_RECORD_URL,
    SUITEQL_URL,
    TOKEN_URL,
)
from db import get_current_token_record, update_token_record


class NetSuiteClient:
    def __init__(self, logger):
        self.logger = logger

    def get_valid_access_token(self):
        token_record = get_current_token_record()

        if not token_record:
            raise RuntimeError("No token record found. Seed refresh token into oauth_tokens first.")

        token_id = token_record["id"]
        access_token = token_record["access_token"]
        refresh_token = token_record["refresh_token"]
        token_type = token_record["token_type"] or "Bearer"
        expires_at = token_record["expires_at"]

        token_is_valid = False

        if access_token and expires_at:
            try:
                expires_at_datetime = datetime.strptime(expires_at, "%Y-%m-%d %H:%M:%S").replace(tzinfo=UTC)
                if datetime.now(UTC) < expires_at_datetime:
                    token_is_valid = True
            except ValueError:
                token_is_valid = False

        if token_is_valid:
            self.logger.info("Using current access token from database.")
            return access_token

        self.logger.info("Access token missing or expired. Requesting new token.")

        response = requests.post(
            TOKEN_URL,
            auth=HTTPBasicAuth(CLIENT_ID, CLIENT_SECRET),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
            },
            timeout=60,
        )

        self.logger.info("Token refresh status: %s", response.status_code)
        self.logger.info("Token refresh response: %s", response.text)

        response.raise_for_status()
        token_json = response.json()

        access_token = token_json["access_token"]
        token_type = token_json.get("token_type", token_type)
        expires_in = token_json.get("expires_in", 3600)
        new_refresh_token = token_json.get("refresh_token")

        if new_refresh_token:
            refresh_token = new_refresh_token

        expires_at_datetime = datetime.now(UTC) + timedelta(seconds=expires_in - 60)
        expires_at = expires_at_datetime.strftime("%Y-%m-%d %H:%M:%S")

        update_token_record(
            token_id=token_id,
            access_token=access_token,
            refresh_token=refresh_token,
            token_type=token_type,
            expires_in=expires_in,
            expires_at=expires_at,
        )

        self.logger.info("Saved refreshed token to database.")
        return access_token

    def run_suiteql(self, query):
        access_token = self.get_valid_access_token()

        response = requests.post(
            SUITEQL_URL,
            headers={
                "Prefer": "transient",
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            json={"q": query},
            timeout=60,
        )

        self.logger.info("SuiteQL status: %s", response.status_code)
        self.logger.info("SuiteQL response: %s", response.text)

        response.raise_for_status()
        payload = response.json()

        if "items" in payload:
            return payload["items"]

        if "results" in payload:
            return payload["results"]

        return payload

    def get_purchase_order_header(self, po_internal_id):
        return self._get_record_header(f"{PO_RECORD_URL}/{po_internal_id}", po_internal_id, "purchase order")

    # def get_sales_order_header(self, so_internal_id):
    #     return self._get_record_header(f"{SO_RECORD_URL}/{so_internal_id}", so_internal_id, "sales order")

    def get_sales_order_header(self, so_internal_id):
        return self._get_record_header(
            f"{SO_RECORD_URL}/{so_internal_id}?expandSubResources=true",
            so_internal_id,
            "sales order"
        )

    def _get_record_header(self, url, record_internal_id, record_type_label):
        access_token = self.get_valid_access_token()

        response = requests.get(
            url,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json",
            },
            timeout=60,
        )

        self.logger.info("%s header status for %s: %s", record_type_label.title(), record_internal_id, response.status_code)
        self.logger.info("%s header response for %s: %s", record_type_label.title(), record_internal_id, response.text)

        response.raise_for_status()
        return response.json()

    def send_failure_email(self, subject, body):
        if not FAILURE_EMAIL_FROM or not FAILURE_EMAIL_TO or not SMTP_HOST:
            self.logger.warning("Failure email not sent. SMTP settings are missing.")
            return

        message = MIMEText(body)
        message["Subject"] = subject
        message["From"] = FAILURE_EMAIL_FROM
        message["To"] = FAILURE_EMAIL_TO

        smtp = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=60)

        try:
            if SMTP_USE_TLS:
                smtp.starttls()

            if SMTP_USERNAME:
                smtp.login(SMTP_USERNAME, SMTP_PASSWORD)

            smtp.sendmail(FAILURE_EMAIL_FROM, [FAILURE_EMAIL_TO], message.as_string())
            self.logger.info("Failure email sent to %s", FAILURE_EMAIL_TO)
        finally:
            smtp.quit()
