from app.config import Settings, _pick


def test_account_alias():
    assert _pick({"ACCOUNT": "acct"}, "SNOWFLAKE_ACCOUNT", "ACCOUNT") == "acct"
    assert _pick({"SNOWFLAKE_USER": "person"}, "SNOWFLAKE_USER", "USER") == "person"


def test_qualified_name_rejects_sql():
    settings = Settings(
        snowflake_account="account",
        snowflake_user="user",
        snowflake_password="secret",
        snowflake_database="METRICS_ANALYZER",
        snowflake_schema="DQ",
    )
    assert settings.qualified("DQ_RESULTS") == "METRICS_ANALYZER.DQ.DQ_RESULTS"
    try:
        settings.qualified("DQ_RESULTS;drop")
    except ValueError:
        return
    raise AssertionError("unsafe identifier was accepted")
