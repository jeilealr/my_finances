"""Transaction categorization logic for dashboard analytics."""

from __future__ import annotations

import re
from dataclasses import dataclass

import pandas as pd

MAIN_ACCOUNT_NAME = "Main Account"
TRANSFER_CATEGORIES = {
    "Blocked Account",
    "Card Repayment",
    "Colombia Transfer",
    "Internal Transfer",
    "Investments",
    "Savings",
}


@dataclass(frozen=True)
class CategoryRule:
    """Ordered category rule matched against normalized transaction text."""

    category: str
    patterns: tuple[str, ...]


CATEGORY_RULES = [
    CategoryRule(
        category="Colombia Transfer",
        patterns=(
            r"\bTRANSFERWISE\b",
            r"\bTRANSFER\s*WISE\b",
            r"\bTRA\s*NSFERWISE\b",
            r"\bTRA\s*NSFER\s*WISE\b",
            r"\bWISE\b",
            r"\bTRWIBEB1XXX\b",
            r"\bBE79967040785533\b",
            r"\bBE76967369030095\b",
        ),
    ),
    CategoryRule(
        category="Internal Transfer",
        patterns=(
            r"\bREVOLUT\b",
            r"\bREVO\s*LUT\b",
            r"\bREVODEB2\w*\b",
            r"\bTOP-UP BY\b",
            r"\bTO POCKET\b",
            r"\bPOCKET WITHDRAWAL\b",
            r"\bLEAL ROJAS, JEISSON JAVIER\b",
            r"\bJEISSON JAVIER LEAL ROJAS\b",
            r"\bPARA EMERGENCIAS\b",
            r"\bNEQUI\b",
            r"\bTRANSFERENCIA CTA SUC VIRTUAL\b",
        ),
    ),
    CategoryRule(
        category="Investments",
        patterns=(
            r"\bISIN\b",
            r"\bDEPOT\b",
            r"\bKAUF\b",
            r"\bORDER-NR\b",
            r"\bORDER NR\b",
        ),
    ),
    CategoryRule(
        category="Interest Income",
        patterns=(
            r"\bNET INTEREST PAID TO 'INSTANT ACCESS SAVINGS'",
            r"\bINTERESES AHORROS\b",
        ),
    ),
    CategoryRule(
        category="Savings",
        patterns=(r"\bINSTANT ACCESS SAVINGS\b",),
    ),
    CategoryRule(
        category="Salary",
        patterns=(
            r"\bHELMHOLTZ-ZENTRUM\b",
            r"\bLOHN/GEHALT\b",
            r"\bSALARY\b",
            r"\bPAYROLL\b",
        ),
    ),
    CategoryRule(
        category="Blocked Account",
        patterns=(
            r"\bKLARNA\b",
            r"\bKLRNDEBEXXX\b",
        ),
    ),
    CategoryRule(
        category="Card Repayment",
        patterns=(
            r"\bAMERICAN EXPRESS\b",
            r"\bZAHLUNG/ÜBERWEISUNG ERHALTEN BESTEN DANK\b",
            r"\bZAHLUNG/UEBERWEISUNG ERHALTEN BESTEN DANK\b",
            r"\bTC VISA\b",
        ),
    ),
    CategoryRule(
        category="Rent",
        patterns=(
            r"\bRENT\b",
            r"\bSOLOMIIA\b",
            r"\bANNIKA\b",
            r"\bSCHWARZER\s+HAUS\b",
            r"\bDR\s+SACHA\s+SCHWARZER\b",
            r"\bPETZSCHERSTR\b",
            r"\bAMSTERDAM\b.*\bHOTEL\b",
        ),
    ),
    CategoryRule(
        category="Grocery Shopping",
        patterns=(
            r"\bLIDL\b",
            r"\bREWE\b",
            r"\bREWE\s+MARKT\b",
            r"\bPENNY\b",
            r"\bALDI\b",
            r"\bALDI\s+NORD\b",
            r"\bALDI\s+SUD\b",
            r"\bEDEKA\b",
            r"\bE[\s-]?CENTER\b",
            r"\bHIT\b",
            r"\bALNATURA\b",
            r"\bKAUFLAND\b",
            r"\bKONSUM\b",
            r"\bKONSUM\s+LEIPZIG\b",
            r"\bKONSUM\s+THERESIENSTRASSE\b",
            r"\bNETTO\b",
            r"\bNETTO\s+\d+\b",
            r"\bNAHKAUF\b",
            r"\bMARKTKAUF\b",
            r"\bTEGUT\b",
            r"\bBIO COMPANY\b",
            r"\bD1\b",
            r"\bDENN",
            r"\bROSSMANN\b",
            r"\bSUPERMARKT\b",
            r"\bSUPERMARKET\b",
            r"\bGROCERIES\b",
            r"\bFLINK\b",
            r"\bGETIR\b",
            r"\bGORILLAS\b",
            r"\bPICNIC\b",
            r"\bRB BROT MARKT\b",
            r"\bRUSSISCH BROT MARKT\b",
        ),
    ),
    CategoryRule(
        category="Restaurants & Delivery",
        patterns=(
            r"\bLIEFERANDO\b",
            r"\bDELIVEROO\b",
            r"\bUBER EATS\b",
            r"\bWOLT\b",
            r"\bRESTAURANT\b",
            r"\bCAFE\b",
            r"\bCOFFEE\b",
            r"\bKEBAB\b",
            r"\bBISTRO\b",
            r"\bVIYANA KAHVESI\b",
            r"\bVENTO MARE\b",
            r"\bDEAN DAVID\b",
            r"\bALEX\b",
            r"\bCINNAMOOD\b",
            r"\bNEMO\b",
            r"\bTURGAY USTA\b",
            r"\bZIYA BABA\b",
            r"\bKOMSU EV YEMEKLERI\b",
            r"\bNIIKO ASIA STREETFOOD\b",
            r"\bVAPIANO\b",
            r"\bDEAN\s*&\s*DAVID\b",
            r"\bMARCH[ÉE]\s+M[ÖO]VENPICK\b",
            r"\bMID 90S BURGER\b",
            r"\bRAMEN\b",
            r"\bTAKUMI\b",
            r"\bMAISON VIET\b",
            r"\bNORDSEE\b",
            r"\bSTARBUCKS\b",
            r"\bBURGERMEISTER\b",
            r"\bLUCKYCATCOFFEE\b",
            r"\bPHOLOSOPHY\b",
            r"\bRIALTO\b",
            r"\bBUKOWINA\b",
            r"\bKUTTER UND K[ÜU]STENFISC\b",
            r"\bBEST MAZA\b",
        ),
    ),
    CategoryRule(
        category="Electricity",
        patterns=(r"\bLEIPZIGER STADTWERKE\b",),
    ),
    CategoryRule(
        category="Phone & Internet",
        patterns=(
            r"\bVODAFONE\b",
            r"\bDRILLISCH\b",
            r"\bHANDYVERTRAG\b",
            r"\bRUNDFUNK\b",
        ),
    ),
    CategoryRule(
        category="Dance",
        patterns=(
            r"\bBAILEO\b",
            r"\bTANZSCHULE\b",
        ),
    ),
    CategoryRule(
        category="Utilities",
        patterns=(r"\bSTROM\b",),
    ),
    CategoryRule(
        category="Pharmacy",
        patterns=(
            r"\bCARDIF\b",
            r"\bSURAMER\b",
            r"\bSEGUROS\b",
            r"\bAPOTHEKE\b",
            r"\bHERZ-APOTHEKE\b",
            r"\bCARE VISION\b",
            r"\bENSENAUTO\b",
        ),
    ),
    CategoryRule(
        category="Fitness",
        patterns=(
            r"\bFIT/ONE\b",
            r"\bFITX\b",
            r"\bFITNESS FIRST\b",
        ),
    ),
    CategoryRule(
        category="ATM Withdrawal",
        patterns=(
            r"\bBARGELDAUSZAHLUNG\b",
            r"\bRETIRO\s+CAJERO\b",
            r"\bCAJERO\b",
            r"\bGELDAUSZAHLUNG\b",
        ),
    ),
    CategoryRule(
        category="Transport",
        patterns=(
            r"\bDB VERTRIEB\b",
            r"\bBAHN\.DE/ABOPORTAL\b",
            r"\bDEUTSCHLANDTICKET\b",
            r"\bANTALYKART\b",
            r"\bBELBIM\b",
            r"\bBEAM\b",
            r"\bPTT\b",
            r"\bAJET\b",
            r"\bWIZZ AIR\b",
            r"\bMETRO\b",
            r"\bNEXTBIKE\b",
        ),
    ),
    CategoryRule(
        category="Travel",
        patterns=(
            r"\bHOTEL\b",
            r"\bBOOKING\.COM\b",
            r"\bGETYOURGUIDE\b",
            r"\bSIXx PAXX\b",
            r"\bCITADINES\b",
            r"\bDUSSELDORF\b",
            r"\bBARCELONA\b",
            r"\bISTANBUL\b",
            r"\bAMSTERDAM\b",
            r"\bLUFTHANSA\b",
            r"\bTURKISH AIRLINES\b",
            r"\bPEGASUS\b",
            r"\bFLIXBUS\b",
            r"\bDEUTSCHEBAHN\b",
            r"\bDEUTSCHE BAHN\b",
            r"\bPENSION VILLA FROHSINN\b",
            r"\bSTAYCITY APARTHOTEL\b",
            r"\bBERGHOTEL\b",
            r"\bMONBUS\b",
            r"\bHOTELLDRIFT HELSINKI\b",
        ),
    ),
    CategoryRule(
        category="Retail & Online Shopping",
        patterns=(
            r"\bAMZN\b",
            r"\bAMAZON\b",
            r"\bTEMU\b",
            r"\bTK MAXX\b",
            r"\bSATURN\b",
            r"\bPOCO\b",
            r"\bOBI\b",
            r"\bORIENT MASTER\b",
            r"\bEURO GOLD\b",
            r"\bVIVENU\b",
            r"\bH\s*&\s*M\b",
            r"\bBERSHKA\b",
            r"\bDEICHMANN\b",
            r"\bVERSUNI\b",
            r"\bNANU NANA\b",
            r"\bMEDION\b",
            r"\bDOUGLAS\b",
            r"\bRITUALS\b",
            r"\bBLUME2000\b",
            r"\bBLUME 2000\b",
            r"\bLUSH\b",
            r"\bALLOPTIK\b",
            r"\bXXL HANDELS\b",
            r"\bMAEC GEIZ\b",
        ),
    ),
    CategoryRule(
        category="Entertainment",
        patterns=(
            r"\bKONFETTI\b",
            r"\bTICKET\.IO\b",
            r"\bZOO LEIPZIG\b",
            r"\bNIGHTFLY LOUNG\b",
            r"\bNIGHTFLY LOUNGE\b",
            r"\bMUSIKPAVILLON\b",
            r"\bDARK MATTER\b",
            r"\bNATIONALPARK-ZENTRUM K[ÖO]NIGSSTUHL\b",
            r"\bSACHSEN THERME\b",
        ),
    ),
    CategoryRule(
        category="Bank Fees",
        patterns=(
            r"\bCARD DELIVERY FEE\b",
            r"\bMANEJO TARJETA\b",
            r"\bGELDAUTOMAT\b",
            r"\bGEB.UHR\b",
            r"\bGEBÜHR\b",
            r"\bFEE\b",
            r"\bAJUSTE INTERES\b",
        ),
    ),
    CategoryRule(
        category="Income",
        patterns=(
            r"\bABONO\b",
            r"\bÜBERWEISUNG VON\b",
            r"\bPAYMENT FROM\b",
            r"\bTRANSF INTERNACIONAL RECIBIDA\b",
            r"\bZAHLUNG/ÜBERWEISUNG ERHALTEN\b",
        ),
    ),
]


def _normalized_text(row: pd.Series) -> str:
    """Build a single uppercase text blob for categorization."""
    parts = [
        row.get("account", ""),
        row.get("subaccount", ""),
        row.get("description", ""),
        row.get("notes", ""),
    ]
    return " ".join(str(part) for part in parts if part).upper()


def categorize_transaction(row: pd.Series) -> str:
    """Return the first matching category for a transaction row."""
    normalized_text = _normalized_text(row)
    for rule in CATEGORY_RULES:
        if any(re.search(pattern, normalized_text) for pattern in rule.patterns):
            return rule.category

    if str(row.get("bank", "")).lower() == "payback":
        return "Card Repayment"

    if pd.notna(row.get("amount")) and float(row["amount"]) > 0:
        return "Income"
    return "Other"


def determine_flow_group(amount: float, category: str) -> str:
    """Split transactions into Income, Expense, or Transfer for analytics."""
    if category in TRANSFER_CATEGORIES:
        return "Transfer"
    if amount >= 0:
        return "Income"
    return "Expense"


def enrich_transactions(transactions: pd.DataFrame) -> pd.DataFrame:
    """Add dashboard-friendly derived columns to the transactions export."""
    dataframe = transactions.copy()
    if dataframe.empty:
        return dataframe

    dataframe["subaccount"] = (
        dataframe["subaccount"].fillna("").replace("", MAIN_ACCOUNT_NAME)
    )
    dataframe["category"] = dataframe.apply(categorize_transaction, axis=1)
    dataframe["flow_group"] = dataframe.apply(
        lambda row: determine_flow_group(float(row["amount"]), row["category"]),
        axis=1,
    )
    dataframe["month"] = dataframe["date"].dt.to_period("M").dt.to_timestamp()
    dataframe["month_label"] = dataframe["month"].dt.strftime("%Y-%m")
    dataframe["expense_amount"] = (
        dataframe["amount"]
        .where(
            dataframe["flow_group"].eq("Expense"),
            0.0,
        )
        .abs()
    )
    dataframe["income_amount"] = dataframe["amount"].where(
        dataframe["flow_group"].eq("Income"),
        0.0,
    )
    dataframe["account_label"] = dataframe.apply(
        lambda row: f"{row['bank']} / {row['account']} / {row['subaccount']}",
        axis=1,
    )
    return dataframe
