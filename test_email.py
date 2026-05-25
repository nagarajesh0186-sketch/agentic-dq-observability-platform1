import asyncio
from dotenv import load_dotenv
load_dotenv()  # ← load .env before anything else

from tools.alerts.email import EmailAlerter

async def test():
    alerter = EmailAlerter()
    result = await alerter.send_alert(
        subject="DQ Alert Test",
        title="Test Alert from DQ Platform",
        message="This is a test alert from your Agentic DQ Pipeline.",
        severity="WARN",
        table_name="enterprise_customer_transactions",
        run_id="test_run_001",
    )
    print("Email sent:", result)

asyncio.run(test())