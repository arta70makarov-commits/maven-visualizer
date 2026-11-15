"""Тесты этапа 3: BFS, глубина, циклы, тестовый репозиторий."""
import os
import unittest

from depviz.graph import build_graph, find_cycles
from depviz.maven import NotFoundError
from depviz.sources import FileSource, MavenSource, TestRepoError

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPOS = os.path.join(ROOT, "tests", "repos")


def graph_of(repo, root, depth):
    """Построить граф по файлу тестового репозитория."""
    source = FileSource(os.path.join(REPOS, repo + ".txt"))
    return build_graph(source.root(root, None), source.dependencies, depth)


class BfsTest(unittest.TestCase):
    """Обход в ширину."""

    def test_order_and_depth(self):
        """Вершины в порядке BFS, общая зависимость D один раз."""
        graph = graph_of("simple", "A", 5)
        self.assertEqual(list(graph.edges), ["A", "B", "C", "D", "E"])
        self.assertEqual(graph.depth["D"], 2)
        self.assertEqual(graph.edge_count(), 5)

    def test_max_depth(self):
        """Глубже max_depth не идём, обрезанные вершины помечены."""
        graph = graph_of("chain", "A", 2)
        self.assertEqual(list(graph.edges), ["A", "B", "C"])
        self.assertEqual(graph.cut, {"C"})

    def test_cycle_terminates(self):
        """Цикл не приводит к бесконечному обходу и находится."""
        graph = graph_of("cycle", "A", 10)
        self.assertEqual(len(graph.edges), 4)
        self.assertEqual(find_cycles(graph), [["A", "B", "C", "A"]])

    def test_self_loop(self):
        """Пакет, зависящий сам от себя."""
        self.assertEqual(find_cycles(graph_of("self", "A", 10)),
                         [["A", "A"]])

    def test_complex(self):
        """Большой граф с двумя циклами и неописанным листом."""
        graph = graph_of("complex", "A", 10)
        self.assertIn("K", graph.edges)
        cycles = find_cycles(graph)
        self.assertIn(["E", "G", "E"], cycles)
        self.assertEqual(len(cycles), 2)

    def test_no_cycles(self):
        """Граф без циклов."""
        self.assertEqual(find_cycles(graph_of("simple", "A", 5)), [])


class TestRepoTest(unittest.TestCase):
    """Ошибки файла тестового репозитория."""

    def test_errors(self):
        """Неверный формат, имя и неизвестный корень."""
        for repo in ("bad_format", "bad_name"):
            with self.subTest(repo=repo), self.assertRaises(TestRepoError):
                FileSource(os.path.join(REPOS, repo + ".txt"))
        with self.assertRaises(TestRepoError):
            FileSource(os.path.join(REPOS, "simple.txt")).root("Z", None)


NS = 'xmlns="http://maven.apache.org/POM/4.0.0"'


def pom(artifact, version, deps):
    """Маленький POM с зависимостями [(artifactId, version)]."""
    items = "".join(
        f"<dependency><groupId>g</groupId><artifactId>{name}</artifactId>"
        f"<version>{ver}</version></dependency>" for name, ver in deps)
    return (f"<project {NS}><groupId>g</groupId><artifactId>{artifact}"
            f"</artifactId><version>{version}</version><dependencies>"
            f"{items}</dependencies></project>")


FILES = {
    "https://r.org/g/app/1/app-1.pom": pom("app", "1", [("lib", "2"),
                                                        ("gone", "1")]),
    "https://r.org/g/lib/2/lib-2.pom": pom("lib", "2", [("app", "1")]),
}


def fake_fetch(url):
    """Подмена скачивания POM."""
    if url not in FILES:
        raise NotFoundError(url)
    return FILES[url]


class MavenSourceTest(unittest.TestCase):
    """Граф по репозиторию Maven."""

    def test_graph_cycle_and_missing(self):
        """Цикл app <-> lib; отсутствующий POM — предупреждение."""
        source = MavenSource("https://r.org", fake_fetch)
        graph = build_graph(source.root("g:app", "1"),
                            source.dependencies, 5)
        self.assertEqual(list(graph.edges)[:2],
                         [("g:app", "1"), ("g:lib", "2")])
        self.assertEqual(len(find_cycles(graph)), 1)
        self.assertEqual(source.label(("g:app", "1")), "g:app:1")
        self.assertTrue(any("gone" in w for w in source.warnings))


if __name__ == "__main__":
    unittest.main()
