"""User personality tracking and adaptive prompting."""

from __future__ import annotations

from dataclasses import dataclass

from e_cli.memory.store import MemoryStore


@dataclass
class PersonalityTraits:
    """User personality traits tracked over time."""

    verbosity: float = 0.5  # 0.0 (concise) to 1.0 (detailed)
    technical_level: float = 0.5  # 0.0 (beginner) to 1.0 (expert)
    interaction_style: float = 0.5  # 0.0 (formal) to 1.0 (casual)
    patience_level: float = 0.5  # 0.0 (quick) to 1.0 (thorough)
    learning_mode: float = 0.5  # 0.0 (do it for me) to 1.0 (teach me)

    def to_dict(self) -> dict[str, float]:
        """Convert traits to dictionary."""
        return {
            "verbosity": self.verbosity,
            "technical_level": self.technical_level,
            "interaction_style": self.interaction_style,
            "patience_level": self.patience_level,
            "learning_mode": self.learning_mode,
        }

    @staticmethod
    def from_dict(data: dict[str, float]) -> PersonalityTraits:
        """Create PersonalityTraits from dictionary."""
        return PersonalityTraits(
            verbosity=data.get("verbosity", 0.5),
            technical_level=data.get("technical_level", 0.5),
            interaction_style=data.get("interaction_style", 0.5),
            patience_level=data.get("patience_level", 0.5),
            learning_mode=data.get("learning_mode", 0.5),
        )


@dataclass
class UserPreference:
    """A single user preference."""

    category: str
    key: str
    value: str
    frequency: int = 1


class PersonalityTracker:
    """Tracks and learns user personality and preferences."""

    def __init__(self, memory_store: MemoryStore, user_id: str = "default") -> None:
        """Initialize personality tracker.

        Args:
            memory_store: Memory store for persistence
            user_id: User identifier
        """
        self.memory_store = memory_store
        self.user_id = user_id
        self._ensure_tables()

    def _ensure_tables(self) -> None:
        """Ensure personality tracking tables exist."""
        conn = self.memory_store.conn

        # User profiles table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT UNIQUE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Personality traits table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS personality_traits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                trait_name TEXT NOT NULL,
                trait_value REAL NOT NULL,
                confidence REAL DEFAULT 0.5,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, trait_name)
            )
        """)

        # User preferences table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_preferences (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                category TEXT NOT NULL,
                preference_key TEXT NOT NULL,
                preference_value TEXT NOT NULL,
                frequency INTEGER DEFAULT 1,
                last_used TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, category, preference_key)
            )
        """)

        # Domain expertise table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS domain_expertise (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                domain TEXT NOT NULL,
                expertise_level REAL DEFAULT 0.5,
                evidence_count INTEGER DEFAULT 0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, domain)
            )
        """)

        conn.commit()

        # Ensure user profile exists
        conn.execute(
            "INSERT OR IGNORE INTO user_profiles (user_id) VALUES (?)",
            (self.user_id,),
        )
        conn.commit()

    def get_personality_traits(self) -> PersonalityTraits:
        """Get current personality traits for user.

        Returns:
            PersonalityTraits instance
        """
        conn = self.memory_store.conn
        cursor = conn.execute(
            """
            SELECT trait_name, trait_value
            FROM personality_traits
            WHERE user_id = ?
            """,
            (self.user_id,),
        )

        traits_dict = {}
        for row in cursor:
            traits_dict[row[0]] = row[1]

        return PersonalityTraits.from_dict(traits_dict)

    def update_trait(self, trait_name: str, value: float, confidence: float = 0.7) -> None:
        """Update a personality trait.

        Args:
            trait_name: Name of the trait
            value: New value (0.0 to 1.0)
            confidence: Confidence in this value (0.0 to 1.0)
        """
        conn = self.memory_store.conn
        conn.execute(
            """
            INSERT INTO personality_traits (user_id, trait_name, trait_value, confidence, updated_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id, trait_name)
            DO UPDATE SET
                trait_value = excluded.trait_value,
                confidence = excluded.confidence,
                updated_at = CURRENT_TIMESTAMP
            """,
            (self.user_id, trait_name, value, confidence),
        )
        conn.commit()

    def record_preference(self, category: str, key: str, value: str) -> None:
        """Record or update a user preference.

        Args:
            category: Preference category (e.g., 'tool_choice', 'response_style')
            key: Preference key
            value: Preference value
        """
        conn = self.memory_store.conn
        conn.execute(
            """
            INSERT INTO user_preferences (user_id, category, preference_key, preference_value, frequency, last_used)
            VALUES (?, ?, ?, ?, 1, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id, category, preference_key)
            DO UPDATE SET
                preference_value = excluded.preference_value,
                frequency = frequency + 1,
                last_used = CURRENT_TIMESTAMP
            """,
            (self.user_id, category, key, value),
        )
        conn.commit()

    def get_preferences(self, category: str | None = None) -> list[UserPreference]:
        """Get user preferences.

        Args:
            category: Optional category filter

        Returns:
            List of UserPreference objects
        """
        conn = self.memory_store.conn

        if category:
            cursor = conn.execute(
                """
                SELECT category, preference_key, preference_value, frequency
                FROM user_preferences
                WHERE user_id = ? AND category = ?
                ORDER BY frequency DESC
                """,
                (self.user_id, category),
            )
        else:
            cursor = conn.execute(
                """
                SELECT category, preference_key, preference_value, frequency
                FROM user_preferences
                WHERE user_id = ?
                ORDER BY frequency DESC
                """,
                (self.user_id,),
            )

        return [
            UserPreference(category=row[0], key=row[1], value=row[2], frequency=row[3])
            for row in cursor
        ]

    def update_domain_expertise(self, domain: str, level: float) -> None:
        """Update expertise level in a domain.

        Args:
            domain: Domain name (e.g., 'python', 'linux', 'docker')
            level: Expertise level (0.0 to 1.0)
        """
        conn = self.memory_store.conn
        conn.execute(
            """
            INSERT INTO domain_expertise (user_id, domain, expertise_level, evidence_count, updated_at)
            VALUES (?, ?, ?, 1, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id, domain)
            DO UPDATE SET
                expertise_level = excluded.expertise_level,
                evidence_count = evidence_count + 1,
                updated_at = CURRENT_TIMESTAMP
            """,
            (self.user_id, domain, level),
        )
        conn.commit()

    def get_top_domains(self, limit: int = 5) -> list[tuple[str, float]]:
        """Get top domains by expertise level.

        Args:
            limit: Maximum number of domains to return

        Returns:
            List of (domain, expertise_level) tuples
        """
        conn = self.memory_store.conn
        cursor = conn.execute(
            """
            SELECT domain, expertise_level
            FROM domain_expertise
            WHERE user_id = ?
            ORDER BY expertise_level DESC, evidence_count DESC
            LIMIT ?
            """,
            (self.user_id, limit),
        )

        return [(row[0], row[1]) for row in cursor]

    def generate_adaptive_prompt(self, base_prompt: str) -> str:
        """Generate an adaptive system prompt based on user personality.

        Args:
            base_prompt: Base system prompt

        Returns:
            Enhanced prompt with personality adaptations
        """
        traits = self.get_personality_traits()
        enhancements = []

        # Verbosity adaptation
        if traits.verbosity < 0.3:
            enhancements.append("User prefers concise, direct answers without extra explanation.")
        elif traits.verbosity > 0.7:
            enhancements.append("User appreciates detailed explanations and thorough responses.")

        # Technical level adaptation
        if traits.technical_level > 0.7:
            enhancements.append("User is technically advanced. Use precise terminology and assume knowledge of concepts.")
        elif traits.technical_level < 0.3:
            enhancements.append("User is learning. Provide helpful explanations for technical terms.")

        # Interaction style
        if traits.interaction_style > 0.6:
            enhancements.append("User prefers a casual, friendly tone.")
        elif traits.interaction_style < 0.4:
            enhancements.append("User prefers a professional, formal tone.")

        # Learning mode
        if traits.learning_mode > 0.6:
            enhancements.append("User wants to learn. Explain reasoning and provide educational context.")
        elif traits.learning_mode < 0.4:
            enhancements.append("User wants results. Focus on solving the task efficiently.")

        # Add domain expertise
        domains = self.get_top_domains(limit=3)
        if domains:
            domain_str = ", ".join([f"{d[0]} ({d[1]:.0%})" for d in domains])
            enhancements.append(f"User has expertise in: {domain_str}")

        if enhancements:
            enhanced_prompt = base_prompt + "\n\n" + "\n".join(enhancements)
            return enhanced_prompt

        return base_prompt
