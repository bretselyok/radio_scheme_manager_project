from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from radio_scheme_manager.calculations import calculate_bom_cost, calculate_economic_effect, risk_level
from radio_scheme_manager.database import DatabaseManager
from radio_scheme_manager.exporters import ReportBuilder
from radio_scheme_manager.services import AccessDenied, ApplicationService


class CoreTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "test.db"
        self.export_dir = Path(self.tmp.name) / "exports"
        self.db = DatabaseManager(self.db_path)
        self.db.init_schema()
        self.service = ApplicationService(self.db, ReportBuilder(self.export_dir))

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_authentication_and_dashboard(self) -> None:
        login = self.service.login("admin", "admin123")
        self.assertIn("token", login)
        user = self.service.get_user(login["token"])
        self.assertEqual(user["role"], "admin")
        dashboard = self.service.dashboard(user)
        self.assertGreaterEqual(dashboard["projects_total"], 1)
        self.assertGreaterEqual(dashboard["schemes_total"], 1)

    def test_project_crud(self) -> None:
        auth = self.service.login("admin", "admin123")
        user = self.service.get_user(auth["token"])
        created = self.service.create_record(
            user,
            "projects",
            {
                "code": "UNIT-001",
                "title": "Тестовый проект",
                "customer": "Учебный заказчик",
                "status": "Планирование",
                "priority": "Средний",
            },
        )
        project_id = created["id"]
        project = self.service.get_record(user, "projects", project_id)
        self.assertEqual(project["code"], "UNIT-001")
        self.service.update_record(user, "projects", project_id, {"status": "Разработка"})
        project = self.service.get_record(user, "projects", project_id)
        self.assertEqual(project["status"], "Разработка")
        self.service.delete_record(user, "projects", project_id)
        with self.assertRaises(Exception):
            self.service.get_record(user, "projects", project_id)

    def test_role_restriction(self) -> None:
        auth = self.service.login("engineer", "engineer123")
        user = self.service.get_user(auth["token"])
        with self.assertRaises(AccessDenied):
            self.service.create_record(user, "projects", {"code": "NO", "title": "Запрещено"})

    def test_economic_calculation(self) -> None:
        result = calculate_economic_effect(
            {
                "hourly_rate": 1000,
                "dev_hours": 100,
                "implementation_hours": 20,
                "equipment_cost": 10000,
                "software_cost": 0,
                "indirect_rate": 0.2,
                "operation_cost_year": 50000,
                "effect_saving_year": 200000,
                "discount_rate": 0.1,
                "lifetime_years": 3,
            }
        )
        self.assertGreater(result.capital_costs, 0)
        self.assertGreater(result.annual_net_cashflow, 0)
        self.assertGreater(result.npv, 0)

    def test_bom_summary_and_risk_level(self) -> None:
        summary = calculate_bom_cost([
            {"quantity": 2, "price": 10, "stock_qty": 10, "part_number": "A"},
            {"quantity": 3, "price": 5, "stock_qty": 1, "part_number": "B"},
        ])
        self.assertEqual(summary["total_quantity"], 5)
        self.assertEqual(summary["total_cost"], 35)
        self.assertTrue(summary["has_stock_problems"])
        self.assertEqual(risk_level(16), "Критический")

    def test_report_generation(self) -> None:
        auth = self.service.login("admin", "admin123")
        user = self.service.get_user(auth["token"])
        result = self.service.export_report(user, "project_passport", {"project_id": 1})
        path = Path(result["path"])
        self.assertTrue(path.exists())
        self.assertGreater(path.stat().st_size, 1000)
        result = self.service.export_report(user, "bom", {"scheme_id": 1})
        path = Path(result["path"])
        self.assertTrue(path.exists())
        self.assertGreater(path.stat().st_size, 1000)

    def test_schematic_editor_data_and_svg_export(self) -> None:
        auth = self.service.login("engineer", "engineer123")
        user = self.service.get_user(auth["token"])
        initial = self.service.get_schematic(user, 1)
        self.assertGreaterEqual(len(initial["nodes"]), 1)
        result = self.service.save_schematic(
            user,
            1,
            {
                "nodes": [
                    {"node_key": "unit_r1", "symbol_type": "resistor", "refdes": "R1", "label": "10 кОм", "x": 120, "y": 120},
                    {"node_key": "unit_c1", "symbol_type": "capacitor", "refdes": "C1", "label": "100 нФ", "x": 260, "y": 120},
                ],
                "wires": [
                    {"wire_key": "unit_w1", "net_name": "+5V", "x1": 160, "y1": 120, "x2": 220, "y2": 120},
                ],
            },
        )
        self.assertEqual(result["nodes"], 2)
        saved = self.service.get_schematic(user, 1)
        self.assertEqual(len(saved["nodes"]), 2)
        export = self.service.export_schematic(user, 1)
        path = Path(export["path"])
        self.assertTrue(path.exists())
        self.assertIn("<svg", path.read_text(encoding="utf-8"))

    def test_controller_cannot_edit_schematic(self) -> None:
        auth = self.service.login("controller", "control123")
        user = self.service.get_user(auth["token"])
        self.service.get_schematic(user, 1)
        with self.assertRaises(AccessDenied):
            self.service.save_schematic(user, 1, {"nodes": [], "wires": []})


if __name__ == "__main__":
    unittest.main()
