"""Hand-written ground-truth queries for testing retrieval quality before
the retrieval pipeline itself exists. Each entry names the product a
correct top-result chunk should come from, plus a keyword that must appear
in that chunk's text - both taken directly from
aurora_product_information_catalog.pdf.
"""

from dataclasses import dataclass


@dataclass
class GoldenQuery:
    query: str
    expected_product: str
    expected_keyword: str


GOLDEN_QUERIES: list[GoldenQuery] = [
    GoldenQuery(
        query="Is AuroraBuds Pro 2 compatible with the original AuroraCharge case?",
        expected_product="AuroraBuds Pro 2",
        expected_keyword="NOT compatible",
    ),
    GoldenQuery(
        query="What Bluetooth version does AuroraBuds Pro 2 support?",
        expected_product="AuroraBuds Pro 2",
        expected_keyword="5.3",
    ),
    GoldenQuery(
        query="What is the battery life of AuroraWatch Fit 3 with the always-on display?",
        expected_product="AuroraWatch Fit 3",
        expected_keyword="5 days",
    ),
    GoldenQuery(
        query="Can I reply to text messages from AuroraWatch Fit 3 on an iPhone?",
        expected_product="AuroraWatch Fit 3",
        expected_keyword="Android-only",
    ),
    GoldenQuery(
        query="What is the product ID for AuroraWatch Fit 3?",
        expected_product="AuroraWatch Fit 3",
        expected_keyword="AUR-WT-FIT3",
    ),
    GoldenQuery(
        query="What is the water and dust resistance rating of AuroraSound Go?",
        expected_product="AuroraSound Go",
        expected_keyword="IP67",
    ),
    GoldenQuery(
        query="Can I pair an AuroraSound Go with a different Aurora speaker model for stereo?",
        expected_product="AuroraSound Go",
        expected_keyword="not cross-compatible",
    ),
    GoldenQuery(
        query="What is the maximum load capacity of the AuroraDesk Rise laptop stand?",
        expected_product="AuroraDesk Rise",
        expected_keyword="10 kg",
    ),
    GoldenQuery(
        query="Does hot-swapping switches on AuroraType K5 void the entire warranty?",
        expected_product="AuroraType K5",
        expected_keyword="electrical/PCB warranty remains valid",
    ),
    GoldenQuery(
        query="Which firmware version fixes Bluetooth dropout issues on AuroraType K5?",
        expected_product="AuroraType K5",
        expected_keyword="1.2",
    ),
]
