
import unittest

from backend.change_manager import validate_python_file


class TestChangeManager(unittest.TestCase):
    """Pruebas iniciales del gestor de cambios."""

    def test_archivo_python_valido(self):
        result = validate_python_file("backend/change_manager.py")

        self.assertTrue(result["ok"])
        self.assertEqual(result["message"], "Sintaxis Python correcta.")

    def test_rechaza_archivo_que_no_es_python(self):
        result = validate_python_file("README.md")

        self.assertFalse(result["ok"])
        self.assertEqual(
            result["message"],
            "Solo se admiten archivos Python."
        )

    def test_rechaza_archivo_inexistente(self):
        result = validate_python_file(
            "backend/archivo_que_no_existe.py"
        )

        self.assertFalse(result["ok"])
        self.assertEqual(
            result["message"],
            "El archivo no existe."
        )

    def test_rechaza_ruta_fuera_del_proyecto(self):
        result = validate_python_file("../archivo_externo.py")

        self.assertFalse(result["ok"])
        self.assertEqual(
            result["message"],
            "La ruta esta fuera del proyecto."
        )


if __name__ == "__main__":
    unittest.main()
