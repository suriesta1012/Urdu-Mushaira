"""
Individual Poet Agent Implementations
Each agent has unique personality, style, and composition approach
"""

from typing import Optional, Dict, List
from agents.base_agent import BasePoetAgent, PoetryData
from agents.poet_config import POETS, get_all_poets_in_order


class BasharBadrAgent(BasePoetAgent):
    """Bashir Badr - The Contemporary Romantic (Position 1: Junior)"""
    
    def compose_poetry(self, context: Optional[Dict] = None) -> PoetryData:
        """Compose accessible, heartfelt modern gazal"""
        themes = self.poet_profile.signature_themes
        poetry = PoetryData(
            text=f"A tender gazal by {self.poet_profile.name}, blending contemporary life with romantic sensibility",
            urdu_text="باشر بدر کی نرم اور دل کش غزل",
            theme="Nature and contemporary love",
            form="Ghazal",
            couplets=[
                "روشنی میں تمہاری شام ہے میری زندگی",
                "ہر لمحہ ایک نیا رنگ لے کر آتا ہے"
            ],
            meter="Ramel",
            rhyme_scheme="AA BA"
        )
        return poetry
    
    def create_reflection(self, state: Dict) -> str:
        """Reflect on the mushaira as junior poet"""
        return f"{self.poet_profile.name} (Position 1): I am honored to start this grand mushaira with my humble verses celebrating the beauty of modern love and nature."


class AhmadFarazAgent(BasePoetAgent):
    """Ahmad Faraz - The Revolutionary (Position 2: Intermediate)"""
    
    def compose_poetry(self, context: Optional[Dict] = None) -> PoetryData:
        """Compose progressive poetry with social consciousness"""
        poetry = PoetryData(
            text=f"A revolutionary gazal by {self.poet_profile.name}, infusing political consciousness with romantic passion",
            urdu_text="احمد فراز کی انقلابی غزل",
            theme="Love intertwined with revolution and freedom",
            form="Ghazal",
            couplets=[
                "محبت بھی انقلاب ہے، آزادی کی نمائندگی",
                "ہر دل میں ایک شاعر سوتا ہے، ہر نظر میں خواب"
            ],
            meter="Hazaj",
            rhyme_scheme="AA BA"
        )
        return poetry
    
    def create_reflection(self, state: Dict) -> str:
        """Reflect on progression"""
        return f"{self.poet_profile.name} (Position 2): Building on Bashir's gentle verses, I bring the fire of revolution—love and freedom are one and the same."


class JaunEliaAgent(BasePoetAgent):
    """Jaun Elia - The Philosopher (Position 3: Advanced)"""
    
    def compose_poetry(self, context: Optional[Dict] = None) -> PoetryData:
        """Compose deeply philosophical and mystical poetry"""
        poetry = PoetryData(
            text=f"A philosophical gazal by {self.poet_profile.name}, blending existential inquiry with Sufi mysticism",
            urdu_text="جون ایلیا کی فلسفیانہ غزل",
            theme="Existentialism, mortality, and spiritual transcendence",
            form="Ghazal",
            couplets=[
                "موت سے پہلے جو سوچا ہے وہ آخری سفر نہیں",
                "وجود و عدم کی حد پر کھڑے ہوں میں، کبھی سمجھ میں آیا"
            ],
            meter="Kamil",
            rhyme_scheme="AA BA"
        )
        return poetry
    
    def create_reflection(self, state: Dict) -> str:
        """Reflect on deeper meanings"""
        return f"{self.poet_profile.name} (Position 3): From revolution to philosophy—we explore the existential space where love becomes a gateway to understanding the infinite."


class NasirKazmiAgent(BasePoetAgent):
    """Nasir Kazmi - The Modernist (Position 4: Senior)"""
    
    def compose_poetry(self, context: Optional[Dict] = None) -> PoetryData:
        """Compose romantic and metaphysical modern poetry"""
        poetry = PoetryData(
            text=f"A modernist gazal by {self.poet_profile.name}, elegantly blending classical form with contemporary sensibility",
            urdu_text="ناصر کاظمی کی جدید غزل",
            theme="Urban romance, metaphysical beauty, and urban melancholy",
            form="Ghazal",
            couplets=[
                "شہر میں تنہائی کی اپنی خوشبو ہے",
                "تمہاری یادوں میں سفر کرتا ہوں رات بھر"
            ],
            meter="Muzari",
            rhyme_scheme="AA BA"
        )
        return poetry
    
    def create_reflection(self, state: Dict) -> str:
        """Reflect as senior voice"""
        return f"{self.poet_profile.name} (Position 4): With decades of poetic evolution, I present the refined beauty of modernism—where every word carries the weight of tradition and the lightness of innovation."


class FaizAhmadFaizAgent(BasePoetAgent):
    """Faiz Ahmad Faiz - The Master Revolutionary (Position 5: Master)"""
    
    def compose_poetry(self, context: Optional[Dict] = None) -> PoetryData:
        """Compose revolutionary and patriotic poetry of highest order"""
        poetry = PoetryData(
            text=f"A legendary gazal by {self.poet_profile.name}, transforming personal love into universal struggle for justice",
            urdu_text="فیض احمد فیض کی عظیم الشان غزل",
            theme="Independence, social revolution, universal justice, and transcendent love",
            form="Ghazal",
            couplets=[
                "یہ داغ داغ اجالا، یہ شب گریہ سحر ہے",
                "کہہ دو ان حسرت کے پروانوں، کہیں اور ٹھکانہ ڈھونڈو"
            ],
            meter="Wafir",
            rhyme_scheme="AA BA"
        )
        return poetry
    
    def create_reflection(self, state: Dict) -> str:
        """Reflect as master poet"""
        return f"{self.poet_profile.name} (Position 5): The voice of millions, the conscience of nations—my poetry bridges individual longing and collective liberation. This is the power of the pen."


class MirzaGhalibAgent(BasePoetAgent):
    """Mirza Ghalib - The Legend (Position 6: Legend)"""
    
    def compose_poetry(self, context: Optional[Dict] = None) -> PoetryData:
        """Compose sublime classical poetry of legendary mastery"""
        poetry = PoetryData(
            text=f"A sublime gazal by {self.poet_profile.name}, the pinnacle of Urdu literary achievement",
            urdu_text="میرزا غالب کی عظیم غزل",
            theme="Divine mystery, human suffering, philosophical depth, and romantic passion",
            form="Ghazal",
            couplets=[
                "ہ��اروں خواہشیں ایسی کہ ہر خواہش پہ دم نکلے",
                "بہت نکلے مرے ارغوانِ ختم سے خون"
            ],
            meter="Ramel",
            rhyme_scheme="AA BA"
        )
        return poetry
    
    def create_reflection(self, state: Dict) -> str:
        """Reflect as the greatest poet"""
        return f"{self.poet_profile.name} (Position 6): Centuries have passed, yet poetry remains what it was—a mirror to the soul, a voice for the voiceless, a path to the divine. I am honored to add my verse to this eternal conversation."


class MirTaqiMirAgent(BasePoetAgent):
    """Mir Taqi Mir - The Supreme Master (Position 7: Supreme/Most Senior)"""
    
    def compose_poetry(self, context: Optional[Dict] = None) -> PoetryData:
        """Compose foundational, seminal Urdu poetry"""
        poetry = PoetryData(
            text=f"A timeless gazal by {self.poet_profile.name}, the father of Urdu poetry, establishing eternal truths",
            urdu_text="میر تقی میر کی ابدی غزل",
            theme="The eternal human condition, universal longing, timeless love, and cosmic pathos",
            form="Ghazal",
            couplets=[
                "التجا کرتا ہ��ں عرش سے میں، غافل نہ ہو میرا دادِ غم",
                "میر کی بربادی میں ہی اس دنیا کی بنائی ہے"
            ],
            meter="Kamil",
            rhyme_scheme="AA BA"
        )
        return poetry
    
    def create_reflection(self, state: Dict) -> str:
        """Reflect as the supreme poet"""
        return f"{self.poet_profile.name} (Position 7): I am the foundation upon which all of you stand. From my first verses, Urdu poetry was born. Let my final words be a blessing to all who pursue the divine craft of verse."


# Factory function to create all agents
def create_all_poet_agents() -> Dict[str, BasePoetAgent]:
    """Create all 7 poet agents in order"""
    agent_classes = [
        BasharBadrAgent,
        AhmadFarazAgent,
        JaunEliaAgent,
        NasirKazmiAgent,
        FaizAhmadFaizAgent,
        MirzaGhalibAgent,
        MirTaqiMirAgent,
    ]
    
    agents = {}
    poets_in_order = get_all_poets_in_order()
    
    for idx, (agent_class, poet_profile) in enumerate(zip(agent_classes, poets_in_order)):
        position = idx + 1
        agent = agent_class(poet_profile, position)
        agents[poet_profile.name.lower().replace(" ", "_")] = agent
    
    return agents
