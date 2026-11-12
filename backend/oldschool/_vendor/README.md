# Vendored code

| File | Project | Version | Licence | Source |
| --- | --- | --- | --- | --- |
| `acefile.py` | acefile by Daniel Roethlisberger | 0.6.14 | BSD-2-Clause (header of the file) | sdist `acefile-0.6.14.tar.gz` from PyPI, sha256 `96957fd167136ef5bc1c133fe74da2453229ad19308d6b986cbcc3c76ed5511d` |

`acefile` is bundled as its pure-Python module because its PyPI package builds an optional C extension that needs a compiler. The module runs without that extension: ACE archives are small, so the slower path is fine.
