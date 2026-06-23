import config

REQUIRED_ACCOUNT_KEYS = {"id", "bank", "type"}
VALID_BANKS = {"CA", "Bourso"}
VALID_TYPES = {"courant", "carte"}
VALID_PROFILES = {"jeremy", "manon", "commun"}


def test_profiles_keys():
    assert set(config.PROFILES.keys()) == VALID_PROFILES


def test_each_profile_has_label_and_accounts():
    for name, profile in config.PROFILES.items():
        assert "label" in profile, f"{name} missing 'label'"
        assert "accounts" in profile, f"{name} missing 'accounts'"
        assert len(profile["accounts"]) > 0, f"{name} has no accounts"


def test_account_structure():
    for name, profile in config.PROFILES.items():
        for acc in profile["accounts"]:
            missing = REQUIRED_ACCOUNT_KEYS - acc.keys()
            assert not missing, f"{name}: account missing keys {missing}"
            assert acc["bank"] in VALID_BANKS, f"{name}: unknown bank {acc['bank']}"
            assert acc["type"] in VALID_TYPES, f"{name}: unknown type {acc['type']}"


def test_no_duplicate_account_ids_across_profiles():
    seen = {}
    for name, profile in config.PROFILES.items():
        for acc in profile["accounts"]:
            aid = acc["id"]
            assert aid not in seen, (
                f"Account {aid} appears in both '{seen[aid]}' and '{name}'"
            )
            seen[aid] = name


def test_sheets_config_present():
    assert config.GOOGLE_SHEETS_ID
    assert config.GOOGLE_SERVICE_ACCOUNT_JSON
    assert config.OPENROUTER_API_KEY
    assert config.OPENROUTER_MODEL
