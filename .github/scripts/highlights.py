"""Print the '## Highlights' section for a release from HIGHLIGHTS.md (3-6 '- ' bullets) or exit 1."""
import sys
lines = [l.rstrip() for l in open("HIGHLIGHTS.md", encoding="utf-8")]
bullets = [l for l in lines if l.startswith("- ")]
if not 3 <= len(bullets) <= 6:
    sys.exit("HIGHLIGHTS.md needs 3-6 '- ' bullets, found %d" % len(bullets))
print("## Highlights\n\n" + "\n".join(bullets) + "\n")
