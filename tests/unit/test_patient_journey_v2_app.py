from __future__ import annotations

from pathlib import Path

from streamlit.testing.v1 import AppTest

PROJECT_ROOT = Path(__file__).parents[2]


def _rendered_text(app: AppTest) -> str:
    groups = (
        app.title,
        app.header,
        app.subheader,
        app.markdown,
        app.caption,
        app.info,
        app.warning,
    )
    return "\n".join(str(element.value) for group in groups for element in group)


def test_v2_app_loads_offline_and_preserves_research_only_nonpromotion() -> None:
    app = AppTest.from_file(
        str(PROJECT_ROOT / "app" / "patient_journey_v2.py"),
        default_timeout=15,
    ).run()

    assert not app.exception
    assert app.selectbox(key="program_selector")
    rendered = _rendered_text(app).casefold()
    assert "no model promoted" in rendered
    assert "nonclinical and nonregulatory" in rendered
    assert "not officially risk adjusted" in rendered
    assert "no future forecast" in rendered
    assert "public aggregate" in rendered
    assert "not patient-level" in rendered
    assert "not causal decision support" in rendered
    assert "national leaderboard" not in rendered
    assert "composite score" not in rendered

    dataframe_columns = {
        str(column) for dataframe in app.dataframe for column in dataframe.value.columns
    }
    assert {
        "Prediction origin",
        "Target publication",
        "Published",
        "Included measurement segments",
    } <= dataframe_columns
    dataframe_text = "\n".join(
        dataframe.value.to_string(index=False) for dataframe in app.dataframe
    )
    assert "07/2019" in dataframe_text
    assert "2020-01-01 to 2020-03-12; 2020-06-13 to 2021-12-31" in dataframe_text
    provenance = app.table[0].value
    assert {"Bundle content SHA-256", "Build time (UTC)"} <= set(provenance["Field"])

    selector = app.selectbox(key="program_selector")
    missing_label = next(label for label in selector.options if "(ARBH:TX1)" in label)
    selector.select(missing_label).run()
    assert not app.exception
    selected_table_text = "\n".join(
        dataframe.value.to_string(index=False) for dataframe in app.dataframe
    )
    assert "Not reported" in selected_table_text
