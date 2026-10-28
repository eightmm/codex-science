import unittest

from codex_science.units_runtime import convert_value, parse_unit, run_dimension_check


class UnitsScaleValidityTests(unittest.TestCase):
    def conversion(self, value, source, target):
        return run_dimension_check({
            "schema_version": 1, "check_id": "d", "claim_id": "c", "variables": {"x": "m"},
            "conversions": [{"value": value, "from": source, "to": target}],
        })

    def test_cancelled_scale_underflow_is_recovered(self) -> None:
        expression = "nm^20*nm^20/nm^20/nm^20"
        self.assertEqual(1.0, parse_unit(expression).scale)
        result = self.conversion(1, expression, "1")
        self.assertEqual("passed", result["status"])
        self.assertEqual(1.0, result["conversions"][0]["converted"])

    def test_large_target_scale_preserves_representable_conversion(self) -> None:
        result = self.conversion(1e100, "m^64*m^64", "km^64*km^64")
        self.assertEqual("passed", result["status"])
        self.assertAlmostEqual(1.0, result["conversions"][0]["converted"] / 1e-284)

    def test_boolean_conversion_is_refused_before_coercion(self) -> None:
        for value in (True, False):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "conversion value must be numeric"):
                    convert_value(value, "m", "cm")
                with self.assertRaisesRegex(ValueError, "conversion value must be numeric"):
                    self.conversion(value, "m", "cm")

    def test_dimensionless_literal_refuses_boolean_and_float(self) -> None:
        for source in ("True", "False", "1.0", "0", ""):
            with self.subTest(source=source):
                with self.assertRaises(ValueError):
                    parse_unit(source)
        self.assertEqual(1.0, parse_unit("1").scale)

    def test_scale_range_failures_are_value_errors(self) -> None:
        for expression in (
            "nm^20*nm^20", "km^64*km^64", "m/nm^40", "nm^40/m",
            "(((km^64)^64)^64)^64", "(((nm^64)^64)^64)^64",
        ):
            with self.subTest(expression=expression):
                with self.assertRaises(ValueError):
                    parse_unit(expression)
        for value, source, target in ((1e308, "km", "nm"), (1e-320, "nm", "km")):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    convert_value(value, source, target)
                self.assertEqual("findings", self.conversion(value, source, target)["status"])

    def test_scale_range_edges_and_zero(self) -> None:
        self.assertEqual(1.0, convert_value(1, "(km^64*km^64)/(km^64*km^64)", "1"))
        self.assertEqual(0.0, convert_value(0, "km^64*km^64", "m^64*m^64"))
        self.assertEqual(0.0, convert_value(0, "m", "cm"))
        self.assertEqual(1e192, parse_unit("km^64").scale)
        self.assertEqual(1.0, parse_unit("nm^0").scale)
        self.assertGreater(convert_value(1e-308, "nm", "km"), 0)
        with self.assertRaises(ValueError):
            parse_unit("nm^65")
        with self.assertRaises(ValueError):
            parse_unit("nm*")


if __name__ == "__main__":
    unittest.main()
