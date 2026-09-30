"""
Custom footer for the Sonne showcase site.

Demonstrates building HTML in a data script: base.html renders the
`footer_custom` variable set here at the bottom of every page.
"""

from datetime import datetime
from pathlib import Path

import sonne
from sonne.script_api import sonne_var

content_file_count = sum(1 for path in (Path.cwd() / "content").rglob("*") if path.is_file())
now = datetime.now()

sonne_var(
    "footer_custom",
    f"""
<div class="custom-footer">
    <div class="footer-info">
        <div class="footer-section">
            <h4>About This Site</h4>
            <p>This showcase site demonstrates the capabilities of Sonne {sonne.__version__}.</p>
            <p>Last built: {now.strftime("%B %d, %Y at %H:%M")}</p>
        </div>

        <div class="footer-section">
            <h4>Connect</h4>
            <ul class="social-links">
                <li><a href="https://github.com/MarkCarsonDev/Sonne" target="_blank" rel="noopener">GitHub</a></li>
                <li><a href="https://twitter.com/sonne_ssg" target="_blank" rel="noopener">Twitter</a></li>
                <li><a href="/contact/">Contact Us</a></li>
            </ul>
        </div>

        <div class="footer-section">
            <h4>Resources</h4>
            <ul class="resource-links">
                <li><a href="/docs/">Documentation</a></li>
                <li><a href="/tutorials/">Tutorials</a></li>
                <li><a href="/showcase/">Example Sites</a></li>
            </ul>
        </div>
    </div>

    <div class="footer-credits">
        <p>&copy; {now.year} Sonne Team. Built with <a href="https://github.com/MarkCarsonDev/Sonne">Sonne {sonne.__version__}</a>.</p>
        <p class="small">Contains {content_file_count} content files. All images are from Unsplash.</p>
    </div>
</div>
""",
)
