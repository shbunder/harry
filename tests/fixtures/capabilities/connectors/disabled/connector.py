"""Never runs: the declaration says enabled: false, which is checked first."""

from pathlib import Path

Path(__file__).with_name('IT-RAN').write_text('it ran', encoding='utf-8')
