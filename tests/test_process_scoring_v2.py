"""
tests/test_process_scoring_v2.py
--------------------------------
Pruebas unitarias para el script de procesamiento por lote de Scoring V2 (scripts/process_scoring_v2.py).
Utiliza mocks para aislar la base de datos y evitar llamadas externas a APIs.
"""

import os
from unittest.mock import MagicMock, call, patch
import pytest

from scripts.process_scoring_v2 import (
    ejecutar_dry_run,
    imprimir_resumen_lote,
    obtener_delay_configurado,
    obtener_estadisticas_dry_run,
    obtener_leads_pendientes_v2,
    procesar_lead_individual,
    procesar_lote_v2,
)


class TestProcessScoringV2:

    def test_1_deteccion_leads_pendientes(self):
        """1. Prueba que obtener_leads_pendientes_v2 ejecuta la consulta SQL adecuada y retorna los IDs."""
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cur
        mock_cur.fetchall.return_value = [("LD-00001",), ("LD-00002",), ("LD-00003",)]

        leads = obtener_leads_pendientes_v2(mock_conn)

        assert leads == ["LD-00001", "LD-00002", "LD-00003"]
        mock_cur.execute.assert_called_once()
        query_executed = mock_cur.execute.call_args[0][0]
        assert "version_scoring = 'v2.0'" in query_executed
        assert "WHERE p.lead_id IS NULL" in query_executed

    def test_2_lead_con_v2_no_aparece_como_pendiente(self):
        """2. Prueba que si todos los leads tienen V2, la consulta retorna lista vacía."""
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cur
        mock_cur.fetchall.return_value = []

        leads = obtener_leads_pendientes_v2(mock_conn)

        assert leads == []

    def test_3_dry_run_no_modifica_datos(self):
        """3. Prueba que --dry-run consulta estadísticas sin invocar scoring ni modificar PostgreSQL."""
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cur

        # Simula respuestas de conteos: total, con_v2, pendientes, muestra
        mock_cur.fetchone.side_effect = [(1509,), (10,), (1499,)]
        mock_cur.fetchall.return_value = [("LD-00001",), ("LD-00002",)]

        with patch("scripts.process_scoring_v2.evaluar_y_guardar_scoring_v2_lead") as mock_scoring:
            stats = ejecutar_dry_run(conn=mock_conn, limit_sample=2)

            assert stats["total_leads"] == 1509
            assert stats["leads_con_v2"] == 10
            assert stats["leads_pendientes"] == 1499
            assert stats["muestra_pendientes"] == ["LD-00001", "LD-00002"]

            # Verificar que NO se invocó la función de scoring ni de guardado
            mock_scoring.assert_not_called()

    def test_4_limit_funciona_correctamente(self):
        """4. Prueba que el parámetro limit se incluye en la consulta SQL y restringe el lote."""
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cur
        mock_cur.fetchall.return_value = [("LD-00001",), ("LD-00002",)]

        leads = obtener_leads_pendientes_v2(mock_conn, limit=2)

        assert len(leads) == 2
        query_executed = mock_cur.execute.call_args[0][0]
        assert "LIMIT 2" in query_executed

    @patch("scripts.process_scoring_v2.get_mensajes_lead", return_value=[])
    @patch("scripts.process_scoring_v2.obtener_leads_pendientes_v2")
    @patch("scripts.process_scoring_v2.evaluar_y_guardar_scoring_v2_lead")
    def test_5_error_en_un_lead_no_detiene_los_siguientes(self, mock_scoring, mock_get_pendientes, mock_msgs):
        """5. Prueba que un fallo en un lead es aislado y permite que los demás se procesen."""
        mock_conn = MagicMock()
        mock_get_pendientes.return_value = ["LD-00001", "LD-00002", "LD-00003"]

        # LD-00001: OK, LD-00002: Error/Excepción, LD-00003: OK
        mock_scoring.side_effect = [
            {
                "lead_id": "LD-00001",
                "puntaje_prioridad": 75.0,
                "temperatura": "Alto",
                "modelo_scoring": "hybrid_gemini",
                "version_scoring": "v2.0",
                "razones": {"modelo_extraccion": "gemini"},
            },
            RuntimeError("Simulated DB connection timeout on lead 2"),
            {
                "lead_id": "LD-00003",
                "puntaje_prioridad": 60.0,
                "temperatura": "Medio",
                "modelo_scoring": "hybrid_gemini",
                "version_scoring": "v2.0",
                "razones": {"modelo_extraccion": "reglas"},
            },
        ]

        resumen = procesar_lote_v2(conn=mock_conn)

        assert resumen["pendientes_detectados"] == 3
        assert resumen["procesados_correctamente"] == 2
        assert resumen["errores"] == 1
        assert len(resumen["errores_detalle"]) == 1
        assert resumen["errores_detalle"][0]["lead_id"] == "LD-00002"
        assert "Simulated DB connection timeout" in resumen["errores_detalle"][0]["error"]
        assert mock_scoring.call_count == 3

    @patch("scripts.process_scoring_v2.get_mensajes_lead")
    @patch("scripts.process_scoring_v2.obtener_leads_pendientes_v2")
    @patch("scripts.process_scoring_v2.evaluar_y_guardar_scoring_v2_lead")
    def test_6_resumen_contabiliza_correctamente_y_desglosa_fallbacks(
        self, mock_scoring, mock_get_pendientes, mock_get_msgs
    ):
        """6. Prueba que el resumen consolida con precisión los conteos y desglosa llamadas Gemini vs Fallbacks."""
        mock_conn = MagicMock()
        mock_get_pendientes.return_value = ["LD-1", "LD-2", "LD-3"]

        # LD-1: Con mensajes, Gemini OK
        # LD-2: Sin mensajes, fallback por falta de conversación
        # LD-3: Con mensajes, fallback por error en Gemini
        mock_get_msgs.side_effect = [
            [{"texto": "Hola, precio?"}],
            [],
            [{"texto": "Quiero info"}],
        ]

        mock_scoring.side_effect = [
            {
                "lead_id": "LD-1",
                "puntaje_prioridad": 80.5,
                "temperatura": "Alto",
                "modelo_scoring": "hybrid_gemini",
                "version_scoring": "v2.0",
                "razones": '{"modelo_extraccion": "gemini"}',
            },
            {
                "lead_id": "LD-2",
                "puntaje_prioridad": 45.0,
                "temperatura": "Medio",
                "modelo_scoring": "hybrid_gemini",
                "version_scoring": "v2.0",
                "razones": {"modelo_extraccion": "reglas"},
            },
            {
                "lead_id": "LD-3",
                "puntaje_prioridad": 30.0,
                "temperatura": "Bajo",
                "modelo_scoring": "hybrid_gemini",
                "version_scoring": "v2.0",
                "razones": {"modelo_extraccion": "reglas"},
            },
        ]

        resumen = procesar_lote_v2(conn=mock_conn)

        assert resumen["pendientes_detectados"] == 3
        assert resumen["procesados_correctamente"] == 3
        assert resumen["con_llamadas_gemini"] == 1
        assert resumen["fallback_sin_conversacion"] == 1
        assert resumen["fallback_error_gemini"] == 1
        assert resumen["fallback_reglas"] == 2
        assert resumen["errores"] == 0
        assert resumen["detalles"][0]["categoria_extraccion"] == "gemini_ok"
        assert resumen["detalles"][1]["categoria_extraccion"] == "fallback_sin_conversacion"
        assert resumen["detalles"][2]["categoria_extraccion"] == "fallback_error_gemini"

    @patch("scripts.process_scoring_v2.get_mensajes_lead", return_value=[])
    @patch("scripts.process_scoring_v2.evaluar_y_guardar_scoring_v2_lead")
    def test_7_proceso_utiliza_evaluar_y_guardar_scoring_v2_lead(self, mock_evaluar_v2, mock_msgs):
        """7. Prueba que procesar_lead_individual delega a evaluar_y_guardar_scoring_v2_lead sin duplicar lógica."""
        mock_conn = MagicMock()
        mock_evaluar_v2.return_value = {
            "lead_id": "LD-999",
            "puntaje_prioridad": 68.25,
            "temperatura": "Alto",
            "modelo_scoring": "hybrid_gemini",
            "version_scoring": "v2.0",
            "razones": {"modelo_extraccion": "gemini"},
        }

        res = procesar_lead_individual(mock_conn, "LD-999")

        mock_evaluar_v2.assert_called_once_with(conn=mock_conn, lead_id="LD-999", mensajes=[])
        assert res["lead_id"] == "LD-999"
        assert res["puntaje_prioridad"] == 68.25
        assert res["temperatura"] == "Alto"
        assert res["modelo_scoring"] == "hybrid_gemini"
        assert res["modelo_extraccion"] == "gemini"
        assert res["version_scoring"] == "v2.0"

    def test_8_delay_precedencia_cli_sobre_env_y_default(self):
        """8. Prueba la precedencia de delay: CLI > SCORING_V2_DELAY > default 0.0s."""
        # 1. Sin CLI ni variable de entorno -> 0.0
        with patch.dict(os.environ, {}, clear=True):
            assert obtener_delay_configurado(None) == 0.0

        # 2. Variable de entorno configurada -> valor de entorno
        with patch.dict(os.environ, {"SCORING_V2_DELAY": "3.5"}, clear=True):
            assert obtener_delay_configurado(None) == 3.5

        # 3. CLI especificado -> prevalece sobre variable de entorno
        with patch.dict(os.environ, {"SCORING_V2_DELAY": "5.0"}, clear=True):
            assert obtener_delay_configurado(1.5) == 1.5

        # 4. CLI con 0.0 explícito -> prevalece sobre variable de entorno
        with patch.dict(os.environ, {"SCORING_V2_DELAY": "5.0"}, clear=True):
            assert obtener_delay_configurado(0.0) == 0.0

    @patch("time.sleep")
    @patch("scripts.process_scoring_v2.get_mensajes_lead")
    @patch("scripts.process_scoring_v2.evaluar_y_guardar_scoring_v2_lead")
    def test_9_delay_aplica_sleep_unicamente_cuando_hay_conversacion(
        self, mock_evaluar_v2, mock_get_msgs, mock_sleep
    ):
        """9. Prueba que time.sleep se aplica únicamente a llamadas exitosas con Gemini y no a fallbacks ni sin mensajes."""
        mock_conn = MagicMock()

        # Caso A: Lead con llamada exitosa a Gemini -> DUERME
        mock_evaluar_v2.return_value = {
            "lead_id": "LD-1",
            "puntaje_prioridad": 50.0,
            "temperatura": "Medio",
            "modelo_scoring": "hybrid_gemini",
            "version_scoring": "v2.0",
            "razones": {"modelo_extraccion": "gemini"},
        }
        mock_get_msgs.return_value = [{"texto": "Hola"}]
        procesar_lead_individual(mock_conn, "LD-1", delay=2.5)
        mock_sleep.assert_called_once_with(2.5)

        mock_sleep.reset_mock()

        # Caso B: Lead sin mensajes conversacionales (fallback directo) -> NO DUERME
        mock_evaluar_v2.return_value = {
            "lead_id": "LD-2",
            "puntaje_prioridad": 50.0,
            "temperatura": "Medio",
            "modelo_scoring": "hybrid_gemini",
            "version_scoring": "v2.0",
            "razones": {"modelo_extraccion": "reglas"},
        }
        mock_get_msgs.return_value = []
        procesar_lead_individual(mock_conn, "LD-2", delay=2.5)
        mock_sleep.assert_not_called()

        # Caso C: Lead con fallback por error 429 de Gemini -> NO DUERME
        mock_evaluar_v2.return_value = {
            "lead_id": "LD-3",
            "puntaje_prioridad": 50.0,
            "temperatura": "Medio",
            "modelo_scoring": "hybrid_gemini",
            "version_scoring": "v2.0",
            "razones": {"modelo_extraccion": "reglas"},
        }
        mock_get_msgs.return_value = [{"texto": "Hola"}]
        procesar_lead_individual(mock_conn, "LD-3", delay=2.5)
        mock_sleep.assert_not_called()

    @patch("time.sleep")
    @patch("scripts.process_scoring_v2.get_mensajes_lead", return_value=[{"texto": "Hola"}])
    @patch("scripts.process_scoring_v2.evaluar_y_guardar_scoring_v2_lead")
    def test_10_delay_cero_no_duerme(self, mock_evaluar_v2, mock_get_msgs, mock_sleep):
        """10. Prueba que un delay de 0.0 segundos no invoca time.sleep."""
        mock_conn = MagicMock()
        mock_evaluar_v2.return_value = {
            "lead_id": "LD-1",
            "puntaje_prioridad": 50.0,
            "temperatura": "Medio",
            "modelo_scoring": "hybrid_gemini",
            "version_scoring": "v2.0",
            "razones": {"modelo_extraccion": "gemini"},
        }

        procesar_lead_individual(mock_conn, "LD-1", delay=0.0)
        mock_sleep.assert_not_called()

