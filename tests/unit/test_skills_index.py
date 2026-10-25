"""Unit tests for Neuri Tier-0 compact skills catalog index.

Validates skills/index.yaml YAML syntax, root metadata schema, the complete set
of 7 neuroscience skill packs, modality alignment with ModalityType enum,
trigger phrase validity, disjoint aliases, and strict token budget constraints.
"""

from pathlib import Path
import re
from typing import Any
import yaml

from neuri.core.schemas import ModalityType


class TestSkillsCatalogIndex:
    """Test suite validating skills/index.yaml against architectural invariants.

    Parameters
    ------------
    None

    Returns
    --------
        TestSkillsCatalogIndex: TestSkillsCatalogIndex instance
            Test suite instance for skills catalog verification.
    """

    EXPECTED_SKILL_IDS: tuple[str, ...] = (
        "bids-standard",
        "neuroimaging-preproc",
        "fmri-postproc",
        "dwi-tractography",
        "eeg-meg-pipeline",
        "remote-compute-slurm",
        "scientific-writing-neuro",
    )
    REQUIRED_SKILL_KEYS: tuple[str, ...] = (
        "id",
        "aliases",
        "name",
        "description",
        "modalities",
        "triggers",
    )
    MAX_WORD_BUDGET: int = 250
    MAX_TOKEN_BUDGET: int = 300
    MAX_CHAR_BUDGET: int = 2500
    MAX_LINE_BUDGET: int = 60
    KEBAB_CASE_PATTERN: str = r"^[a-z0-9]+(-[a-z0-9]+)*$"

    def get_catalog_path(self) -> Path:
        """Resolve path to skills/index.yaml from project repository root.

        Parameters
        ------------
        None

        Returns
        --------
            Path: Path object
                Absolute filesystem path to the skills index file.
        """
        catalog_path: Path = (
            Path(__file__).resolve().parent.parent.parent
            / "skills"
            / "index.yaml"
        )
        return catalog_path

    def load_catalog_data(self) -> dict[str, Any]:
        """Load and parse YAML data from skills/index.yaml.

        Parameters
        ------------
        None

        Returns
        --------
            dict[str, Any]: dict object
                Parsed YAML catalog structure as a dictionary.
        """
        path: Path = self.get_catalog_path()
        content: str = path.read_text(encoding="utf-8")
        parsed_data: dict[str, Any] = yaml.safe_load(content)
        return parsed_data

    def test_catalog_file_exists_and_is_non_empty(self) -> None:
        """Verify that skills/index.yaml exists on disk and contains data.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Asserts file presence and positive byte size.
        """
        path: Path = self.get_catalog_path()
        assert path.exists(), f"Skills catalog not found at: {path}"
        assert path.is_file(), f"Skills catalog path is not a file: {path}"
        assert path.stat().st_size > 0, "Skills catalog file is empty."
        return None

    def test_catalog_root_schema_metadata(self) -> None:
        """Verify catalog root version, identifier, and skills list.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Asserts version is 1.0, catalog is neuro_skills_tier0.
        """
        data: dict[str, Any] = self.load_catalog_data()
        assert data.get("version") == "1.0", (
            f"Unexpected catalog version: {data.get('version')}"
        )
        assert data.get("catalog") == "neuro_skills_tier0", (
            f"Unexpected catalog identifier: {data.get('catalog')}"
        )
        assert isinstance(data.get("skills"), list), (
            "Catalog 'skills' entry must be a YAML list."
        )
        return None

    def test_catalog_contains_exact_seven_neuro_skills(self) -> None:
        """Verify the catalog indexes exactly the 7 public neuro skill packs.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Asserts skills count is 7 and IDs match required set.
        """
        data: dict[str, Any] = self.load_catalog_data()
        skills: list[dict[str, Any]] = data.get("skills", [])
        assert len(skills) == 7, (
            f"Expected exactly 7 skill packs, found {len(skills)}"
        )

        actual_ids: list[str] = [str(s.get("id")) for s in skills]
        assert len(set(actual_ids)) == 7, (
            f"Duplicate skill IDs detected: {actual_ids}"
        )
        assert set(actual_ids) == set(self.EXPECTED_SKILL_IDS), (
            f"Skill IDs mismatch. Missing: "
            f"{set(self.EXPECTED_SKILL_IDS) - set(actual_ids)}, "
            f"Unexpected: {set(actual_ids) - set(self.EXPECTED_SKILL_IDS)}"
        )
        return None

    def test_catalog_skill_identifiers_kebab_case(self) -> None:
        """Verify that all skill IDs adhere to strict kebab-case format.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Asserts regex match on all skill identifiers.
        """
        data: dict[str, Any] = self.load_catalog_data()
        skills: list[dict[str, Any]] = data.get("skills", [])
        kebab_regex: re.Pattern[str] = re.compile(self.KEBAB_CASE_PATTERN)

        for skill in skills:
            skill_id: str = str(skill.get("id", ""))
            assert kebab_regex.match(skill_id), (
                f"Skill ID '{skill_id}' does not match kebab-case pattern."
            )
        return None

    def test_catalog_required_fields_present_per_skill(self) -> None:
        """Verify every skill dictionary contains all required contract keys.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Asserts presence of id, aliases, name, description,
                modalities, and triggers on all skill entries.
        """
        data: dict[str, Any] = self.load_catalog_data()
        skills: list[dict[str, Any]] = data.get("skills", [])

        for skill in skills:
            skill_id: str = str(skill.get("id", "unknown"))
            present_keys: set[str] = set(skill.keys())
            missing: set[str] = set(self.REQUIRED_SKILL_KEYS) - present_keys
            assert not missing, (
                f"Skill '{skill_id}' is missing required keys: {missing}"
            )
        return None

    def test_catalog_modalities_match_schema_enum(self) -> None:
        """Verify that all listed modalities belong to ModalityType enum.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Asserts every modality string is a valid ModalityType member.
        """
        data: dict[str, Any] = self.load_catalog_data()
        skills: list[dict[str, Any]] = data.get("skills", [])
        valid_modalities: set[str] = {m.value for m in ModalityType}

        for skill in skills:
            skill_id: str = str(skill.get("id", ""))
            modalities: list[str] = skill.get("modalities", [])
            assert isinstance(modalities, list), (
                f"Modalities for skill '{skill_id}' must be a list."
            )
            assert len(modalities) >= 1, (
                f"Skill '{skill_id}' must declare at least one modality."
            )
            for mod in modalities:
                assert mod in valid_modalities, (
                    f"Skill '{skill_id}' references unknown modality '{mod}'. "
                    f"Valid modalities: {sorted(valid_modalities)}"
                )
        return None

    def test_catalog_triggers_are_non_empty_phrases(self) -> None:
        """Verify that all triggers are non-empty meaningful intent phrases.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Asserts trigger count >= 1 and string length >= 3.
        """
        data: dict[str, Any] = self.load_catalog_data()
        skills: list[dict[str, Any]] = data.get("skills", [])

        for skill in skills:
            skill_id: str = str(skill.get("id", ""))
            triggers: list[str] = skill.get("triggers", [])
            assert isinstance(triggers, list), (
                f"Triggers for skill '{skill_id}' must be a list."
            )
            assert len(triggers) >= 1, (
                f"Skill '{skill_id}' must define at least one trigger."
            )
            for trigger in triggers:
                assert isinstance(trigger, str), (
                    f"Trigger in skill '{skill_id}' must be a string."
                )
                stripped: str = trigger.strip()
                assert len(stripped) >= 3, (
                    f"Trigger '{trigger}' in skill '{skill_id}' is too short."
                )
        return None

    def test_catalog_aliases_are_disjoint_across_skills(self) -> None:
        """Verify that aliases are unique and do not collide across skills.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Asserts zero duplicate aliases across all catalog skills.
        """
        data: dict[str, Any] = self.load_catalog_data()
        skills: list[dict[str, Any]] = data.get("skills", [])
        alias_to_skill: dict[str, str] = {}

        for skill in skills:
            skill_id: str = str(skill.get("id", ""))
            aliases: list[str] = skill.get("aliases", [])
            assert isinstance(aliases, list), (
                f"Aliases for skill '{skill_id}' must be a list."
            )
            assert len(aliases) >= 1, (
                f"Skill '{skill_id}' must declare at least one alias."
            )
            for alias in aliases:
                assert alias not in alias_to_skill, (
                    f"Alias collision: '{alias}' declared in both "
                    f"'{alias_to_skill[alias]}' and '{skill_id}'."
                )
                alias_to_skill[alias] = skill_id
        return None

    def test_catalog_descriptions_are_substantive(self) -> None:
        """Verify descriptions provide informative neuroscience workflow details.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Asserts descriptions exceed minimum length and contain no TODOs.
        """
        data: dict[str, Any] = self.load_catalog_data()
        skills: list[dict[str, Any]] = data.get("skills", [])

        for skill in skills:
            skill_id: str = str(skill.get("id", ""))
            description: str = str(skill.get("description", "")).strip()
            assert len(description) >= 20, (
                f"Description for skill '{skill_id}' is insufficiently detailed."
            )
            lower_desc: str = description.lower()
            assert "todo" not in lower_desc, (
                f"Skill '{skill_id}' contains unresolved TODO marker."
            )
            assert "placeholder" not in lower_desc, (
                f"Skill '{skill_id}' contains placeholder text."
            )
        return None

    def test_catalog_strict_token_and_word_budget(self) -> None:
        """Assert catalog respects the strict <300 token budget ceiling.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Asserts word count < 250, character count < 2500,
                line count <= 60, and estimated BPE tokens < 300.
        """
        path: Path = self.get_catalog_path()
        raw_text: str = path.read_text(encoding="utf-8")
        words: list[str] = raw_text.split()
        word_count: int = len(words)
        char_count: int = len(raw_text)
        line_count: int = len(raw_text.splitlines())

        # Strict R1 requirement: Tier-0 catalog must consume < 300 tokens
        # Target: < 250 words, < 2500 characters, <= 60 lines
        assert word_count < self.MAX_WORD_BUDGET, (
            f"Catalog word count ({word_count}) exceeds budget "
            f"({self.MAX_WORD_BUDGET})."
        )
        assert char_count < self.MAX_CHAR_BUDGET, (
            f"Catalog character count ({char_count}) exceeds budget "
            f"({self.MAX_CHAR_BUDGET})."
        )
        assert line_count <= self.MAX_LINE_BUDGET, (
            f"Catalog line count ({line_count}) exceeds budget "
            f"({self.MAX_LINE_BUDGET})."
        )

        # Conservative BPE token estimation: 1 word ~ 1.33 BPE tokens
        estimated_bpe_tokens: int = int(word_count * 1.45)
        assert estimated_bpe_tokens < self.MAX_TOKEN_BUDGET, (
            f"Estimated BPE tokens ({estimated_bpe_tokens}) exceeds budget "
            f"({self.MAX_TOKEN_BUDGET})."
        )
        return None

    def test_catalog_formatting_and_line_lengths(self) -> None:
        """Verify clean UTF-8 encoding and strict line length limits in YAML.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Asserts no BOM and no line exceeds 88 characters.
        """
        path: Path = self.get_catalog_path()
        raw_bytes: bytes = path.read_bytes()
        assert not raw_bytes.startswith(b"\xef\xbb\xbf"), (
            "skills/index.yaml contains unwanted UTF-8 Byte Order Mark (BOM)."
        )

        raw_text: str = raw_bytes.decode("utf-8")
        lines: list[str] = raw_text.splitlines()
        for idx, line in enumerate(lines, start=1):
            assert len(line) <= 88, (
                f"skills/index.yaml:{idx}: Line exceeds 88 characters "
                f"({len(line)} chars): {line}"
            )
        return None
