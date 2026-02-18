"""Tests for input validators."""
import pytest
from create_ontology_app.validators import (
    validate_project_name,
    validate_domain_name,
    validate_port,
    to_pascal_case,
    to_slug,
)


class TestProjectNameValidation:
    def test_valid_names(self):
        assert validate_project_name("my-clinic") == "my-clinic"
        assert validate_project_name("my_project") == "my_project"
        assert validate_project_name("app123") == "app123"
        assert validate_project_name("a1") == "a1"

    def test_invalid_starts_with_number(self):
        with pytest.raises(ValueError):
            validate_project_name("123app")

    def test_invalid_starts_with_hyphen(self):
        with pytest.raises(ValueError):
            validate_project_name("-app")

    def test_invalid_uppercase(self):
        with pytest.raises(ValueError):
            validate_project_name("MyApp")

    def test_invalid_spaces(self):
        with pytest.raises(ValueError):
            validate_project_name("my app")

    def test_invalid_single_char(self):
        with pytest.raises(ValueError):
            validate_project_name("a")


class TestDomainNameValidation:
    def test_valid_names(self):
        assert validate_domain_name("clinic") == "clinic"
        assert validate_domain_name("my_domain") == "my_domain"
        assert validate_domain_name("warehouse2") == "warehouse2"

    def test_invalid_hyphen(self):
        with pytest.raises(ValueError):
            validate_domain_name("my-domain")

    def test_invalid_uppercase(self):
        with pytest.raises(ValueError):
            validate_domain_name("MyDomain")


class TestPortValidation:
    def test_valid_ports(self):
        assert validate_port(8020) == 8020
        assert validate_port(3020) == 3020
        assert validate_port(1024) == 1024
        assert validate_port(65535) == 65535

    def test_invalid_low(self):
        with pytest.raises(ValueError):
            validate_port(80)

    def test_invalid_high(self):
        with pytest.raises(ValueError):
            validate_port(70000)


class TestToPascalCase:
    def test_single_word(self):
        assert to_pascal_case("clinic") == "Clinic"

    def test_multi_word(self):
        assert to_pascal_case("my_clinic") == "MyClinic"

    def test_already_single(self):
        assert to_pascal_case("warehouse") == "Warehouse"


class TestToSlug:
    def test_with_hyphens(self):
        assert to_slug("my-clinic") == "my_clinic"

    def test_without_hyphens(self):
        assert to_slug("my_clinic") == "my_clinic"
