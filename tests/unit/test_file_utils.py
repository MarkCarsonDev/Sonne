"""Static file copying."""

from sonne.utils.file_utils import copy_static_files


def make_static_tree(static_dir):
    for rel_path in ["css/site.css", "images/a.png", ".hidden/x.txt", "robots.txt"]:
        path = static_dir / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(rel_path, encoding="utf-8")
    # A build always creates the output root before copying static files
    (static_dir.parent / "out").mkdir()


def copied_files(output_dir):
    return sorted(
        p.relative_to(output_dir).as_posix() for p in output_dir.rglob("*") if p.is_file()
    )


class TestCopyStaticFiles:
    def test_copies_everything_but_hidden_entries(self, tmp_path):
        make_static_tree(tmp_path / "static")

        copy_static_files(str(tmp_path / "static"), str(tmp_path / "out"))

        assert copied_files(tmp_path / "out") == ["css/site.css", "images/a.png", "robots.txt"]

    def test_skip_predicate_leaves_accepted_files_uncopied(self, tmp_path):
        make_static_tree(tmp_path / "static")

        copy_static_files(
            str(tmp_path / "static"),
            str(tmp_path / "out"),
            skip=lambda source: source.endswith(".png"),
        )

        assert copied_files(tmp_path / "out") == ["css/site.css", "robots.txt"]
