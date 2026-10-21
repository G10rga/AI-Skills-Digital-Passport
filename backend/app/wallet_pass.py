"""Wallet pass (Apple/Google Wallet) — stub generator.

Produces a Google Wallet-style generic pass JSON plus a .pkpass-shaped
placeholder manifest. Real passes need Apple/Google signing certificates;
those are a production follow-up and slot in behind build_wallet_pass().
"""
from __future__ import annotations


def build_wallet_pass(passport: dict, version: dict, verify_url: str = "") -> dict:
    code = version.get("verification_code", "")
    name = f"{passport.get('first_name','')} {passport.get('last_name','')}".strip()
    return {
        "format": "stub",
        "googleWallet": {
            "genericObject": {
                "id": f"btu.{passport.get('passport_id','')}.v{version.get('version',1)}",
                "classId": "btu.ai-skills-passport",
                "state": "ACTIVE",
                "cardTitle": {"defaultValue": {"language": "en", "value": "BTU AI Skills Digital Passport"}},
                "header": {"defaultValue": {"language": "en", "value": name}},
                "subheader": {"defaultValue": {"language": "en",
                                               "value": passport.get("passport_id", "")}},
                "barcode": {"type": "QR_CODE", "value": verify_url or code,
                            "alternateText": code},
                "textModulesData": [
                    {"id": "version", "header": "VERSION", "body": f"V{version.get('version',1)}"},
                    {"id": "code", "header": "VERIFICATION CODE", "body": code},
                ],
            }
        },
        "appleWallet": {
            "formatVersion": 1, "passTypeIdentifier": "pass.ge.edu.btu.ai-skills",
            "teamIdentifier": "STUB", "organizationName": "Business and Technology University (BTU)",
            "description": "BTU AI Skills Digital Passport",
            "generic": {"primaryFields": [{"key": "name", "label": "NAME", "value": name}],
                        "secondaryFields": [{"key": "passport", "label": "PASSPORT ID",
                                             "value": passport.get("passport_id", "")}]},
            "barcodes": [{"format": "PKBarcodeFormatQR", "message": verify_url or code,
                          "messageEncoding": "iso-8859-1", "altText": code}],
            "_stub": "Unsigned placeholder — production requires an Apple Pass Type ID certificate.",
        },
    }
