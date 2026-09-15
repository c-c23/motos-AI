"""Pruebas unitarias para adaptadores de lectura usados por el dashboard."""

from queries.leads_queries import factores_score_desde_db, valor_ia_para_ui


def test_factores_score_se_leen_desde_razones_persistidas():
    razones = {"factores_clave": ["Solicitó cita", "Declaró cuota inicial"]}
    assert factores_score_desde_db(razones) == ["Solicitó cita", "Declaró cuota inicial"]


def test_factores_score_admite_json_persistido():
    assert factores_score_desde_db('{"factores_clave": ["Espera elevada"]}') == ["Espera elevada"]


def test_null_ia_no_se_convierte_en_no():
    assert valor_ia_para_ui(None) is None
    assert valor_ia_para_ui(False) == "No"
