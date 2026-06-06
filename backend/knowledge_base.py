import re

# Comprehensive local jargon database for Manufacturing, Construction, and Financial Services.
JARGON_DB = {
    "manufacturing": {
        "OEE": {
            "full_form": "Overall Equipment Effectiveness",
            "plain_english": "A metric that measures how productive and efficient a manufacturing operation is compared to its full potential."
        },
        "Kanban": {
            "full_form": "Kanban",
            "plain_english": "A visual workflow management system that uses cards to optimize inventory levels and schedule production tasks."
        },
        "Kaizen": {
            "full_form": "Kaizen",
            "plain_english": "A business philosophy focused on continuous, incremental improvements in productivity, quality, and workplace efficiency."
        },
        "BOM": {
            "full_form": "Bill of Materials",
            "plain_english": "A comprehensive list of raw materials, assemblies, and parts needed to manufacture a finished product."
        },
        "SMED": {
            "full_form": "Single-Minute Exchange of Die",
            "plain_english": "A lean production method that dramatically reduces the time required to set up and switch over manufacturing machinery."
        },
        "Six Sigma": {
            "full_form": "Six Sigma",
            "plain_english": "A data-driven methodology used to improve manufacturing quality by identifying and removing causes of defects."
        },
        "Poka-Yoke": {
            "full_form": "Poka-Yoke",
            "plain_english": "Any mechanism or device in a manufacturing process designed to prevent human errors or mistake-proof a workflow."
        },
        "JIT": {
            "full_form": "Just-In-Time",
            "plain_english": "An inventory management strategy where materials are received and products are manufactured only as they are needed."
        },
        "MRP": {
            "full_form": "Material Requirements Planning",
            "plain_english": "A computer-based production planning and inventory control system used to manage manufacturing processes."
        },
        "FMEA": {
            "full_form": "Failure Mode and Effects Analysis",
            "plain_english": "A step-by-step approach for identifying all possible failures in a design, manufacturing process, or product."
        },
        "Takt Time": {
            "full_form": "Takt Time",
            "plain_english": "The maximum amount of time allowed to produce a product in order to meet customer demand."
        },
        "5S": {
            "full_form": "5S Methodology",
            "plain_english": "A workplace organization method that uses five Japanese words: Sort, Set in order, Shine, Standardize, and Sustain."
        },
        "CAPA": {
            "full_form": "Corrective and Preventive Action",
            "plain_english": "A systematic procedure to investigate, correct, and prevent recurring non-conformances or product defects."
        },
        "SPC": {
            "full_form": "Statistical Process Control",
            "plain_english": "The use of statistical methods to monitor and control a production process to ensure it operates efficiently."
        },
        "Gemba": {
            "full_form": "Gemba",
            "plain_english": "A Japanese term meaning 'the actual place,' referring to the shop floor where real manufacturing work is done."
        }
    },
    "construction": {
        "RFI": {
            "full_form": "Request for Information",
            "plain_english": "A formal process of requesting clarification on project blueprints, specifications, or contract agreements."
        },
        "BOQ": {
            "full_form": "Bill of Quantities",
            "plain_english": "A detailed document prepared by a quantity surveyor listing materials, parts, and labor costs needed for a project."
        },
        "Practical Completion": {
            "full_form": "Practical Completion",
            "plain_english": "The stage of construction where the project is sufficiently complete and safe to be occupied and used by the owner."
        },
        "Retention": {
            "full_form": "Retention",
            "plain_english": "A percentage of the contract value held back by the client to ensure the contractor fixes any future construction defects."
        },
        "Snagging": {
            "full_form": "Snagging",
            "plain_english": "The process of identifying minor defects, errors, or unfinished details at the final stages of a construction project."
        },
        "CDM": {
            "full_form": "Construction Design and Management",
            "plain_english": "Regulations governing the safety, health, and welfare requirements of construction projects."
        },
        "Prelims": {
            "full_form": "Preliminaries",
            "plain_english": "Costs in a construction contract for overheads, administration, scaffolding, and site setup that are not physical building works."
        },
        "PC Sum": {
            "full_form": "Prime Cost Sum",
            "plain_english": "An allowance in a contract for the cost of buying specific materials or services to be decided during construction."
        },
        "NEC": {
            "full_form": "New Engineering Contract",
            "plain_english": "A standard suite of contracts designed to promote collaboration, partnerships, and efficient project management."
        },
        "JCT": {
            "full_form": "Joint Contracts Tribunal",
            "plain_english": "A standard contract template used in the UK to clear up responsibilities, costs, and terms between builders and clients."
        },
        "Float": {
            "full_form": "Float",
            "plain_english": "The amount of time that a construction task can be delayed without delaying the final project completion date."
        },
        "Critical Path": {
            "full_form": "Critical Path Method",
            "plain_english": "The sequence of critical tasks in a project schedule that determines the minimum total time required to finish construction."
        },
        "Defects Liability": {
            "full_form": "Defects Liability Period",
            "plain_english": "A set timeframe after completion during which the contractor is legally obligated to fix any defects that appear."
        },
        "Dayworks": {
            "full_form": "Dayworks",
            "plain_english": "A method of billing for work based on the actual hours of labor and materials used, rather than predefined contract rates."
        },
        "Enabling Works": {
            "full_form": "Enabling Works",
            "plain_english": "Preparatory site activities (like demolition, excavation, or utility diversion) carried out before main construction begins."
        }
    },
    "financial_services": {
        "AUM": {
            "full_form": "Assets Under Management",
            "plain_english": "The total market value of all financial assets that a firm or financial institution manages on behalf of its clients."
        },
        "NAV": {
            "full_form": "Net Asset Value",
            "plain_english": "The value of an entity's assets minus its liabilities, typically used to measure the price per share of a mutual fund."
        },
        "KYC": {
            "full_form": "Know Your Customer",
            "plain_english": "A mandatory process of verifying the identity of clients to prevent financial crimes like money laundering."
        },
        "MiFID": {
            "full_form": "Markets in Financial Instruments Directive",
            "plain_english": "A European regulation designed to protect investors and standardize financial disclosures across financial markets."
        },
        "Drawdown": {
            "full_form": "Drawdown",
            "plain_english": "The peak-to-trough decline of an investment value, or the act of requesting committed funds from private equity investors."
        },
        "Alpha": {
            "full_form": "Alpha",
            "plain_english": "A measure of an investment portfolio's performance compared to a market benchmark, representing the value added by active management."
        },
        "Beta": {
            "full_form": "Beta",
            "plain_english": "A measure of an asset's volatility and risk compared to the overall movement of the financial market."
        },
        "EBITDA": {
            "full_form": "Earnings Before Interest, Taxes, Depreciation, and Amortization",
            "plain_english": "A key metric used to evaluate a company's operating performance by stripping out financing, tax, and accounting decisions."
        },
        "IRR": {
            "full_form": "Internal Rate of Return",
            "plain_english": "The annual rate of growth that an investment is expected to generate, used to calculate profitability of capital projects."
        },
        "WACC": {
            "full_form": "Weighted Average Cost of Capital",
            "plain_english": "The average rate of return a company is expected to pay to all its security holders to finance its assets."
        },
        "Due Diligence": {
            "full_form": "Due Diligence",
            "plain_english": "An investigation or audit of a financial investment or transaction to confirm all material facts and details."
        },
        "Mark to Market": {
            "full_form": "Mark to Market",
            "plain_english": "An accounting method that values financial assets and liabilities based on their current, real-time market prices."
        },
        "Liquidity": {
            "full_form": "Liquidity",
            "plain_english": "The ease and speed with which an asset can be converted into cash without affecting its market price."
        },
        "Hedge": {
            "full_form": "Hedging",
            "plain_english": "An investment strategy designed to offset or reduce the risk of adverse price movements in an asset."
        },
        "Covenant": {
            "full_form": "Covenant",
            "plain_english": "A legally binding agreement or condition in a loan contract that the borrower must maintain (like a minimum debt ratio)."
        }
    }
}


def lookup(term: str, industry: str) -> dict | None:
    """
    Performs a case-insensitive lookup of a jargon term within a specific industry.
    Returns the entry dictionary {"full_form": "...", "plain_english": "..."} or None.
    """
    if not term or not industry:
        return None
        
    normalized_industry = industry.lower().replace(" ", "_")
    industry_db = JARGON_DB.get(normalized_industry)
    if not industry_db:
        return None
        
    # Case-insensitive term search
    term_upper = term.upper()
    for db_term, entry in industry_db.items():
        if db_term.upper() == term_upper:
            return entry
            
    return None


def scan_for_jargon(text: str, industry: str) -> list[dict]:
    """
    Scans the given transcript line for any known jargon terms in the specified industry.
    Returns a list of match dictionaries: [{"term": "...", "full_form": "...", "plain_english": "..."}]
    Uses regex word boundaries to prevent partial matches.
    """
    if not text or not industry:
        return []
        
    normalized_industry = industry.lower().replace(" ", "_")
    industry_db = JARGON_DB.get(normalized_industry)
    if not industry_db:
        return []
        
    matches = []
    # Sort terms by length in descending order to match multi-word terms (e.g. "Practical Completion") before single terms (e.g. "PC")
    sorted_terms = sorted(industry_db.keys(), key=len, reverse=True)
    
    for term in sorted_terms:
        # Regex matching for exact word boundaries
        pattern = re.compile(rf"\b{re.escape(term)}\b", re.IGNORECASE)
        if pattern.search(text):
            entry = industry_db[term]
            matches.append({
                "term": term,
                "full_form": entry["full_form"],
                "plain_english": entry["plain_english"]
            })
            
    return matches


def get_all_terms(industry: str) -> list[str]:
    """
    Returns all jargon terms registered for the specified industry.
    """
    if not industry:
        return []
        
    normalized_industry = industry.lower().replace(" ", "_")
    industry_db = JARGON_DB.get(normalized_industry)
    if not industry_db:
        return []
        
    return list(industry_db.keys())
