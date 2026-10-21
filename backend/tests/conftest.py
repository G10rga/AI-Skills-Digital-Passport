import os
import tempfile
from pathlib import Path

_tmp = Path(tempfile.mkdtemp(prefix="btu-backend-test-"))
os.environ["DATABASE_PATH"] = str(_tmp / "test.db")
os.environ["ISSUER_KEY_FILE"] = str(_tmp / "issuer_key.pem")
os.environ["ADMIN_API_KEY"] = ""  # open admin API in tests
os.environ["ALLOW_DEV_VERIFICATION_CODES"] = "true"  # tests read codes from responses
