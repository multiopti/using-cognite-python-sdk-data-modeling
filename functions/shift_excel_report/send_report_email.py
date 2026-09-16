"""
Standalone local test: emails the current CDF Files copy of the customer
Excel report via AWS SES, as a real attachment (not just body text).

Uses boto3's default credential chain (picks up this machine's AWS CLI
credentials at ~/.aws/credentials) and CDF via cdf_auth.get_client(), same
local-auth pattern as functions/*/local_test.py. Nothing here touches
handler.py yet -- this is just to validate the SES send end-to-end before
it becomes a step inside the deployed Function.

Run:
    E:\\source\\repos\\streamlit\\myenv\\Scripts\\python functions\\shift_excel_report\\send_report_email.py
"""
import sys
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import boto3

THIS_DIR = Path(__file__).parent
REPO_ROOT = THIS_DIR.parents[1]
sys.path.insert(0, str(REPO_ROOT / "streamlit"))

from cdf_auth import get_client  # noqa: E402

FROM_ADDRESS = "gustavo.ingedaca@gmail.com"
TO_ADDRESS = "gustavo.sanchez@ingedaca.com"
AWS_REGION = "us-east-2"  # SES identities are region-specific -- verified here, not us-east-1
FILE_EXTERNAL_ID = "short_can_report"
ATTACHMENT_NAME = "short_can_report.xlsx"


def build_email(attachment_bytes: bytes) -> MIMEMultipart:
    msg = MIMEMultipart()
    msg["Subject"] = "Short Can - D&I y STD (reporte de turno) - PRUEBA"
    msg["From"] = FROM_ADDRESS
    msg["To"] = TO_ADDRESS
    msg.attach(MIMEText(
        "Adjunto el reporte de produccion actualizado (D&I y Standum).\n\n"
        "Este es un envio de prueba generado localmente, no automatizado todavia.",
        "plain",
    ))
    part = MIMEApplication(attachment_bytes, Name=ATTACHMENT_NAME)
    part["Content-Disposition"] = f'attachment; filename="{ATTACHMENT_NAME}"'
    msg.attach(part)
    return msg


def main():
    cdf_client = get_client()
    content = cdf_client.files.download_bytes(external_id=FILE_EXTERNAL_ID)
    print(f"Downloaded {len(content)} bytes from CDF Files ({FILE_EXTERNAL_ID})")

    msg = build_email(content)

    ses = boto3.client("ses", region_name=AWS_REGION)
    response = ses.send_raw_email(
        Source=FROM_ADDRESS,
        Destinations=[TO_ADDRESS],
        RawMessage={"Data": msg.as_bytes()},
    )
    print("Sent. SES MessageId:", response["MessageId"])


if __name__ == "__main__":
    main()
