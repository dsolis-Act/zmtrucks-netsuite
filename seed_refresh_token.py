import sqlite3
from datetime import datetime, UTC

from config import DATABASE_FILE
from db import initialize_database

REFRESH_TOKEN = "eyJraWQiOiJjLjk1ODI5NDFfU0IxLjIwMjYtMDUtMjBfMDItNDAtNDIiLCJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.eyJzdWIiOiIxNTMxOzQ1ODMiLCJhdWQiOlsiOEI4MUMxRTEtOEQ5OC00MTg0LUExMTItOThBOEI2MTc5NjI5Ozk1ODI5NDFfU0IxIiwiM2ZkMDI0NWU3MTI2M2Q3Y2U2MDdhNTk0ZDlmM2QxOTRlOWIzZTQyOTJiNjQ2Y2JhYzA0N2I2NjAwMDQ4ZTNhMSJdLCJzY29wZSI6WyJyZXN0X3dlYnNlcnZpY2VzIl0sImlzcyI6Imh0dHBzOi8vc3lzdGVtLm5ldHN1aXRlLmNvbSIsIm9pdCI6MTc4MDQ0MDYxMywiZXhwIjoxNzgxMDQ1NDEzLCJpYXQiOjE3ODA0NDA2MTMsImp0aSI6Ijk1ODI5NDFfU0IxLnItYS4xNTA3MTdlZC1hYTYyLTQ1YTUtYjFhNy0zODFjNzI2NDY4OWJfMTc4MDQ0MDYxMzMxNy4wIn0.lRzJBMC2LDRsvYQ0Hqeom6Nvd3xK1Q7qSWYVy_XuqK9epF5qhcyB0rXVYO7xZn_s5gJFnzHg5N9m_-MwfEF8YINcDoEUCL5JPXbAURo3Y65g_KO3Wqo_QQVyouEReJ2gnw16tX8ASGPmvbUWz8lrDqdG__bLIpVaQkJeJTVpe0cZ9ftJSFWhl6VnCKKjhhjuwYHO7xeYEXd3rzUBbj46msBjMDWzzTWA1rL9NtAMEZohvz-Ebvhz69A5Q8oucy5CnQoz6ipGm7SdOdKRhC3JT4dYG252pJjoXlWIdsdyw8C24248qCA-bjIA_jwX3cvUh0cIaGKKrJURaGZDBr_ls_AEBvHKS9KwfDIL8wiUkqd0Qw7WpZv5FIrv_WtJff7Vne_oH_G2Rs2bAego8fPAE-akD4g6LaewydodJk5n9RAHxKWEPFSvVFsZUHYKwgOyf6hjAQDG0xMRs52cqSVODNcH5aSvGqHicWBL1A3vLQLLYfLacb5hB1eDmGrzC5-4L5qzyzgjEImWJSBpkfQxVX0L0q2uJfvna76dxbxhYmxsrXaYzamjQsb85avf8tqOSycCVaE-jro4gO0Qnor0y2cP0IlyOljqymhbsOPrKPi2-WJ2v9rvMlzQBuC-vAc0AfLQmQmNNH7oEZ-gogWTj674pX4u1mgv9as9ikwORD8"


def main():
    initialize_database()

    connection = sqlite3.connect(DATABASE_FILE)
    cursor = connection.cursor()

    cursor.execute("SELECT COUNT(*) FROM oauth_tokens")
    row_count = cursor.fetchone()[0]

    if row_count == 0:
        cursor.execute(
            """
            INSERT INTO oauth_tokens (
                access_token,
                refresh_token,
                token_type,
                expires_in,
                expires_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                "",
                REFRESH_TOKEN,
                "Bearer",
                0,
                "2000-01-01 00:00:00",
                datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S"),
            ),
        )
        print("Seeded initial refresh token.")
    else:
        print("oauth_tokens already has a record. Update it manually if needed.")

    connection.commit()
    connection.close()


if __name__ == "__main__":
    main()
