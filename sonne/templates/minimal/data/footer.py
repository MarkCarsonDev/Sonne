from datetime import datetime

# Define custom footer content
footer_html = f'''
<p>© {datetime.now().year} - Built with <a href="https://github.com/MarkCarsonDev/Sonne">Sonne</a>, a minimalist static site generator</p>
<p>Designed to be lightweight and environmentally friendly</p>
<p>Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
'''

# Set the variable that will be available for substitution
sonne_var("footer_custom", footer_html)