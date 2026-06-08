"""
Poet Configuration and Hierarchy
Defines the 7 Urdu poets and their recitation order (junior to senior)
"""

from dataclasses import dataclass
from enum import Enum
from typing import List

class PoetRank(Enum):
    """Hierarchy level (1 = most junior, 7 = most senior)"""
    JUNIOR = 1
    INTERMEDIATE = 2
    ADVANCED = 3
    SENIOR = 4
    MASTER = 5
    LEGEND = 6
    SUPREME = 7


@dataclass
class PoetProfile:
    """Profile for each poet agent"""
    name: str
    urdu_name: str
    birth_year: int
    death_year: int
    rank: PoetRank
    order_position: int  # Recitation order (1 = first, 7 = last)
    specialty: str
    signature_themes: List[str]
    historical_period: str
    key_works: List[str]
    biographical_summary: str


# Poet definitions in recitation order (junior to senior)
POETS = {
    "bashir_badr": PoetProfile(
        name="Bashir Badr",
        urdu_name="باشر بدر",
        birth_year=1935,
        death_year=2016,
        rank=PoetRank.JUNIOR,
        order_position=1,
        specialty="Ghazal and modern Urdu poetry",
        signature_themes=["Nature", "Love", "Separation", "Contemporary life"],
        historical_period="Modern Era (1950s-2010s)",
        key_works=["Shola-e-Gul", "Noor-e-Nazar"],
        biographical_summary="A renowned contemporary poet known for accessible, heartfelt gazals blending classical form with modern sensibility."
    ),
    
    "ahmad_faraz": PoetProfile(
        name="Ahmad Faraz",
        urdu_name="احمد فراز",
        birth_year=1931,
        death_year=2008,
        rank=PoetRank.INTERMEDIATE,
        order_position=2,
        specialty="Progressive poetry and social commentary",
        signature_themes=["Love", "Revolution", "Social justice", "Freedom"],
        historical_period="Modern Era (1950s-2000s)",
        key_works=["Sath Sath", "Do Malhar"],
        biographical_summary="A revolutionary poet who infused political consciousness into romantic verses, bridging classical and progressive traditions."
    ),
    
    "jaun_elia": PoetProfile(
        name="Jaun Elia",
        urdu_name="جون ایلیا",
        birth_year=1931,
        death_year=2002,
        rank=PoetRank.ADVANCED,
        order_position=3,
        specialty="Philosophical and mystical Urdu poetry",
        signature_themes=["Existentialism", "Philosophy", "Love", "Mortality", "Spirituality"],
        historical_period="Modern Era (1950s-2000s)",
        key_works=["Jaun Elia ki Gazals", "Complete Diwan"],
        biographical_summary="A deeply philosophical poet blending Sufi mysticism with existential inquiry, known for profound introspection and linguistic mastery."
    ),
    
    "nasir_kazmi": PoetProfile(
        name="Nasir Kazmi",
        urdu_name="ناصر کاظمی",
        birth_year=1925,
        death_year=1976,
        rank=PoetRank.SENIOR,
        order_position=4,
        specialty="Romantic and metaphysical poetry",
        signature_themes=["Love", "Beauty", "Metaphysics", "Urban melancholy"],
        historical_period="Modern Era (1950s-1970s)",
        key_works=["Choti Si Khushiyan", "Ghar Aur Safar"],
        biographical_summary="An innovator who modernized classical Urdu poetry while maintaining its elegance, known for romantic and introspective verses."
    ),
    
    "faiz_ahmad_faiz": PoetProfile(
        name="Faiz Ahmad Faiz",
        urdu_name="فیض احمد فیض",
        birth_year=1911,
        death_year=1984,
        rank=PoetRank.MASTER,
        order_position=5,
        specialty="Revolutionary and patriotic poetry",
        signature_themes=["Independence", "Justice", "Social revolution", "Love", "Freedom"],
        historical_period="Independence & Post-colonial Era (1940s-1980s)",
        key_works=["Naqsh-e-Faryadi", "Dum-e-Akhir"],
        biographical_summary="A legendary poet who transformed Urdu poetry into a vehicle for social revolution and anti-colonial struggle, earning the Lenin Peace Prize."
    ),
    
    "mirza_ghalib": PoetProfile(
        name="Mirza Ghalib",
        urdu_name="میرزا غالب",
        birth_year=1797,
        death_year=1869,
        rank=PoetRank.LEGEND,
        order_position=6,
        specialty="Classical Urdu and Persian poetry",
        signature_themes=["Love", "Separation", "Philosophy", "Divine mystery", "Human suffering"],
        historical_period="Mughal & British Raj Era (1820s-1860s)",
        key_works=["Divan-e-Ghalib", "Urdu Ghazals"],
        biographical_summary="Arguably the greatest Urdu poet ever, Ghalib elevated the ghazal form to sublime artistic heights with philosophical depth and linguistic genius."
    ),
    
    "mir_taqi_mir": PoetProfile(
        name="Mir Taqi Mir",
        urdu_name="میر تقی میر",
        birth_year=1723,
        death_year=1810,
        rank=PoetRank.SUPREME,
        order_position=7,
        specialty="Foundational Urdu ghazal poetry",
        signature_themes=["Love", "Longing", "Pathos", "Human condition"],
        historical_period="Mughal Era (1740s-1800s)",
        key_works=["Kulliyat-e-Mir", "Historic Ghazals"],
        biographical_summary="The father of Urdu poetry, Mir Taqi Mir established the ghazal as the supreme poetic form and created the emotional vocabulary of Urdu verse."
    ),
}

# Recitation order (from position 1 to 7)
RECITATION_ORDER: List[str] = [
    "bashir_badr",      # Position 1 (Junior)
    "ahmad_faraz",      # Position 2
    "jaun_elia",        # Position 3
    "nasir_kazmi",      # Position 4
    "faiz_ahmad_faiz",  # Position 5
    "mirza_ghalib",     # Position 6
    "mir_taqi_mir",     # Position 7 (Supreme/Most Senior)
]


def get_poet_by_position(position: int) -> PoetProfile:
    """Get poet profile by recitation position (1-7)"""
    if 1 <= position <= 7:
        poet_key = RECITATION_ORDER[position - 1]
        return POETS[poet_key]
    raise ValueError(f"Invalid position: {position}. Must be between 1 and 7.")


def get_all_poets_in_order() -> List[PoetProfile]:
    """Get all poets in recitation order"""
    return [POETS[key] for key in RECITATION_ORDER]

