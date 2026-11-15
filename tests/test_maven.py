"""Тесты этапа 2: разбор POM, свойства, родители, dependencyManagement."""
import io
import unittest
from contextlib import redirect_stdout

from depviz.__main__ import print_direct
from depviz.config import Config
from depviz.maven import (MavenRepository, NotFoundError, RepositoryError,
                          pick_version, pom_url, substitute)

NS = 'xmlns="http://maven.apache.org/POM/4.0.0"'


def dep(group, artifact, version="", scope="", optional=""):
    """XML одной зависимости."""
    parts = [f"<groupId>{group}</groupId>",
             f"<artifactId>{artifact}</artifactId>"]
    if version:
        parts.append(f"<version>{version}</version>")
    if scope:
        parts.append(f"<scope>{scope}</scope>")
    if optional:
        parts.append(f"<optional>{optional}</optional>")
    return "<dependency>" + "".join(parts) + "</dependency>"


PARENT = (f"<project {NS}><groupId>org.ex</groupId><artifactId>parent"
          "</artifactId><version>1</version><properties><lib.version>2.5"
          "</lib.version></properties><dependencyManagement><dependencies>"
          + dep("org.ex", "managed", "3.0")
          + dep("org.ex", "bom", "1", "import")
          + "</dependencies></dependencyManagement><dependencies>"
          + dep("org.ex", "inherited", "1.1") + "</dependencies></project>")
BOM = (f"<project {NS}><groupId>org.ex</groupId><artifactId>bom</artifactId>"
       "<version>1</version><dependencyManagement><dependencies>"
       + dep("org.ex", "from-bom", "7.0")
       + "</dependencies></dependencyManagement></project>")
APP = (f"<project {NS}><parent><groupId>org.ex</groupId><artifactId>parent"
       "</artifactId><version>1</version></parent><artifactId>app"
       "</artifactId><version>2.0</version><dependencies>"
       + dep("org.ex", "lib", "${lib.version}")
       + dep("org.ex", "managed")
       + dep("org.ex", "from-bom")
       + dep("${project.groupId}", "self-group", "${project.version}")
       + dep("org.ex", "tests", "1", "test")
       + dep("org.ex", "maybe", "1", optional="true")
       + dep("org.ex", "rt", "[1.5,2.0)", "runtime")
       + "</dependencies></project>")
FILES = {
    "https://r.org/org/ex/parent/1/parent-1.pom": PARENT,
    "https://r.org/org/ex/bom/1/bom-1.pom": BOM,
    "https://r.org/org/ex/app/2.0/app-2.0.pom": APP,
}


def fake_fetch(url):
    """Подмена скачивания: данные из словаря FILES."""
    if url not in FILES:
        raise NotFoundError(url)
    return FILES[url]


class HelpersTest(unittest.TestCase):
    """Вспомогательные функции."""

    def test_url(self):
        """Путь к POM: точки в groupId становятся папками."""
        self.assertEqual(pom_url("https://r.org", "com.a.b", "lib", "1.0"),
                         "https://r.org/com/a/b/lib/1.0/lib-1.0.pom")

    def test_substitute(self):
        """Вложенные свойства подставляются."""
        props = {"a": "${b}", "b": "1.2"}
        self.assertEqual(substitute("v${a}", props), "v1.2")
        self.assertEqual(substitute("${x}", props), "${x}")

    def test_range(self):
        """Из диапазона берётся нижняя граница."""
        self.assertEqual(pick_version("[1.5,2.0)"), "1.5")
        self.assertEqual(pick_version("(,3.0]"), "3.0")
        self.assertEqual(pick_version("1.0"), "1.0")


class RepositoryTest(unittest.TestCase):
    """Прямые зависимости с учётом родителя и BOM."""

    registry = MavenRepository("https://r.org/", fake_fetch)

    def test_versions(self):
        """Версии из свойств, родителя, BOM и встроенных свойств."""
        deps = {d.name: d for d in
                self.registry.dependencies("org.ex", "app", "2.0")}
        self.assertEqual(deps["org.ex:lib"].version, "2.5")
        self.assertEqual(deps["org.ex:managed"].version, "3.0")
        self.assertEqual(deps["org.ex:from-bom"].version, "7.0")
        self.assertEqual(deps["org.ex:self-group"].version, "2.0")
        self.assertEqual(deps["org.ex:inherited"].version, "1.1")
        self.assertEqual(deps["org.ex:rt"].version, "1.5")

    def test_direct_filter(self):
        """test и optional пропускаются, runtime остаётся."""
        names = [d.name for d in
                 self.registry.direct_dependencies("org.ex", "app", "2.0")]
        self.assertNotIn("org.ex:tests", names)
        self.assertNotIn("org.ex:maybe", names)
        self.assertIn("org.ex:rt", names)

    def test_not_found(self):
        """Нет такой версии — понятная ошибка."""
        with self.assertRaises(RepositoryError) as ctx:
            self.registry.dependencies("org.ex", "app", "9.9")
        self.assertIn("not found in repository", str(ctx.exception))

    def test_bad_xml(self):
        """Испорченный POM — ошибка разбора."""
        broken = MavenRepository("https://r.org",
                                 lambda url: "<project><broken")
        with self.assertRaises(RepositoryError):
            broken.dependencies("a", "b", "1")

    def test_print(self):
        """Вывод прямых зависимостей на экран."""
        config = Config("org.ex:app", "https://r.org", False, "2.0", 1)
        out = io.StringIO()
        with redirect_stdout(out):
            print_direct(config, self.registry)
        self.assertIn("org.ex:app:2.0: direct dependencies (6)",
                      out.getvalue())
        self.assertIn("org.ex:rt:1.5 [runtime]", out.getvalue())


if __name__ == "__main__":
    unittest.main()
