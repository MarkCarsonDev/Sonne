"""
Custom footer generation for Sonne showcase site.

This script demonstrates how to create a custom footer that will be
inserted into all pages of the site.
"""

from datetime import datetime
import os

# Get the current year
current_year = datetime.now().year

# Count files to get a rough idea of site size
def count_files():
    """Count the number of content files."""
    try:
        content_dir = os.path.join(os.getcwd(), 'content')
        if not os.path.exists(content_dir):
            return 0
            
        count = 0
        for root, _, files in os.walk(content_dir):
            count += len(files)
                
        return count
    except Exception as e:
        print(f"Error counting files: {e}")
        return 0

# Get the last build time
build_time = datetime.now().strftime("%B %d, %Y at %H:%M")

# Get the Sonne version
try:
    import sonne
    version = getattr(sonne, '__version__', '0.2.0')
except ImportError:
    version = '0.2.0'

# Generate the custom footer HTML
footer_html = f"""
<div class="custom-footer">
    <div class="footer-info">
        <div class="footer-section">
            <h4>About This Site</h4>
            <p>This showcase site demonstrates the capabilities of Sonne {version}.</p>
            <p>Last built: {build_time}</p>
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
        <p>&copy; {current_year} Sonne Team. Built with <a href="https://github.com/MarkCarsonDev/Sonne">Sonne {version}</a>.</p>
        <p class="small">Contains approximately {count_files()} files and pages. All images are from Unsplash.</p>
    </div>
</div>
"""

# Set the custom footer
sonne_var("footer_custom", footer_html)