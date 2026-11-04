from app.agents.export import csv_document


def test_csv_guards_formulas_and_names_partial_files():
    text, filename = csv_document(
        [{"name": "=name"}, {"name": "value"}],
        [["=1", "ok"], [None, ""]],
        index=0,
        partial=True,
    )
    assert filename == "query-0-partial.csv"
    assert text.split("\r\n")[0] == "'=name,value"
    assert "'=1,ok" in text
    assert ",\r\n" in text or text.endswith(",\r\n")
