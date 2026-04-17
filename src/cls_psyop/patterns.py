"""Known psyop pattern registry.

Defines PsyopPattern instances covering major psychological operation
tactics, techniques, and procedures (TTPs).
"""

from __future__ import annotations

from cls_psyop.schemas import PsyopPattern

# Registry of known psyop patterns
PATTERNS: list[PsyopPattern] = [
    PsyopPattern(
        pattern_id="P001",
        name="Fear Amplification",
        description="Exaggerates threats to induce fear and paralysis in target audience.",
        indicators=[
            "catastrophic", "imminent threat", "inevitable", "no way to stop",
            "millions will die", "total collapse", "end of civilization",
            "unprecedented danger", "existential threat",
        ],
        threat_level="HIGH",
        category="fear",
    ),
    PsyopPattern(
        pattern_id="P002",
        name="False Flag Narrative",
        description="Attributes an action to a party other than the actual perpetrator.",
        indicators=[
            "false flag", "staged", "crisis actor", "government orchestrated",
            "false flag operation", "fake attack", "manufactured incident",
            "deep state", "inside job",
        ],
        threat_level="HIGH",
        category="disinformation",
    ),
    PsyopPattern(
        pattern_id="P003",
        name="Social Wedge",
        description="Exploits existing societal divisions to deepen fractures.",
        indicators=[
            "they hate you", "them vs us", "your kind", "real americans",
            "elites vs ordinary", "globalists", "patriots vs traitors",
            "civil war", "revolution is coming", "take our country back",
        ],
        threat_level="HIGH",
        category="wedge",
    ),
    PsyopPattern(
        pattern_id="P004",
        name="Coordinated Amplification",
        description="Artificially boosts a message through bot/sock-puppet networks.",
        indicators=[
            "trending", "viral", "everyone is saying", "across social media",
            "thousands of accounts", "astroturfing", "coordinated inauthentic",
            "bot network", "sock puppet",
        ],
        threat_level="HIGH",
        category="amplification",
    ),
    PsyopPattern(
        pattern_id="P005",
        name="Enemy Framing",
        description="Frames a target group as an existential enemy.",
        indicators=[
            "enemy of the people", "traitors", "fifth column", "saboteurs",
            "enemies within", "enemy agent", "foreign operatives",
            "spies", "infiltrators",
        ],
        threat_level="HIGH",
        category="framing",
    ),
    PsyopPattern(
        pattern_id="P006",
        name="Malinformation Injection",
        description="True information used out of context to mislead.",
        indicators=[
            "out of context", "leaked document", "classified proof",
            "they don't want you to know", "hidden truth", "what they're hiding",
            "suppressed", "censored by mainstream",
        ],
        threat_level="MEDIUM",
        category="disinformation",
    ),
    PsyopPattern(
        pattern_id="P007",
        name="Authority Impersonation",
        description="Impersonates or falsely attributes statements to authorities.",
        indicators=[
            "official sources say", "anonymous government source",
            "insider reveals", "senior official confirmed",
            "leaked from pentagon", "classified report shows",
        ],
        threat_level="MEDIUM",
        category="framing",
    ),
    PsyopPattern(
        pattern_id="P008",
        name="Firehose of Falsehoods",
        description="Overwhelms audience with high volume of contradictory claims.",
        indicators=[
            "multiple sources confirm", "conflicting reports",
            "impossible to know what's real", "information overload",
            "nobody knows the truth", "all sides are lying",
        ],
        threat_level="MEDIUM",
        category="disinformation",
    ),
    PsyopPattern(
        pattern_id="P009",
        name="Whataboutism",
        description="Deflects criticism by pointing to unrelated wrongdoing elsewhere.",
        indicators=[
            "what about", "but what about", "you did it first",
            "double standard", "they do it too", "western hypocrisy",
            "who are you to say", "your country also",
        ],
        threat_level="LOW",
        category="framing",
    ),
    PsyopPattern(
        pattern_id="P010",
        name="Manufactured Consensus",
        description="Creates illusion of widespread agreement where none exists.",
        indicators=[
            "everyone agrees", "nobody believes", "polls show 90%",
            "experts unanimously", "consensus is clear",
            "undeniable fact", "universally accepted",
        ],
        threat_level="LOW",
        category="amplification",
    ),
    PsyopPattern(
        pattern_id="P011",
        name="Dehumanization",
        description="Strips target group of humanity to justify hostility.",
        indicators=[
            "vermin", "cockroaches", "animals", "parasites", "infestation",
            "plague", "disease", "subhuman", "degenerates", "filth",
        ],
        threat_level="HIGH",
        category="wedge",
    ),
    PsyopPattern(
        pattern_id="P012",
        name="Victimhood Narrative",
        description="Portrays an aggressor as a victim to gain sympathy.",
        indicators=[
            "we are being persecuted", "our people are under attack",
            "systematic discrimination", "they want to destroy us",
            "targeted by the media", "silenced",
        ],
        threat_level="MEDIUM",
        category="framing",
    ),
]

# Index by pattern_id
PATTERN_INDEX: dict[str, PsyopPattern] = {p.pattern_id: p for p in PATTERNS}


def get_pattern(pattern_id: str) -> PsyopPattern | None:
    """Look up a pattern by ID."""
    return PATTERN_INDEX.get(pattern_id)


def get_patterns_by_category(category: str) -> list[PsyopPattern]:
    """Return all patterns of a given category."""
    return [p for p in PATTERNS if p.category == category]


def get_patterns_by_threat(threat_level: str) -> list[PsyopPattern]:
    """Return all patterns of a given threat level."""
    return [p for p in PATTERNS if p.threat_level == threat_level]
